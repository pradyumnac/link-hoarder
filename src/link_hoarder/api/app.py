"""Authenticated FastAPI application."""

import hashlib
import secrets
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    Security,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from link_hoarder.core.config import Settings
from link_hoarder.core.importers import import_html_export_detailed
from link_hoarder.core.logging import configure_logging
from link_hoarder.core.metadata import (
    BookmarkAssetAvailability,
    BookmarkMetadataService,
    MetadataFetcher,
    generated_domain_icon,
)
from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkPresentationPage,
    BookmarkPresentationRead,
    BookmarkPreview,
    BookmarkRead,
    BookmarkSort,
    BookmarkUpdate,
    HtmlImportResult,
    ImportWarning,
    ImportWarningCode,
    JsonImportResult,
    MetadataStatus,
)
from link_hoarder.core.repository import BookmarkRepository, DuplicateBookmarkError

_API_KEY = APIKeyHeader(name="X-API-Key", auto_error=False)
_API_PREFIX = "/api/v1"
_MAX_PROFILE_BYTES = 16 * 1024 * 1024
_MAX_JSON_ITEMS = 50_000
_JSON_IMPORT_PROFILE = "bookmarks.json"
_ASSET_CACHE_CONTROL = "private, max-age=3600, must-revalidate"


class Health(BaseModel):
    """API health response."""

    status: str = "ok"


class ErrorDetail(BaseModel):
    """API error response."""

    detail: str


def create_app(
    settings: Settings | None = None,
    metadata_fetcher: MetadataFetcher | None = None,
) -> FastAPI:
    """Create an API application with initialized storage."""
    current = settings or Settings()
    configure_logging(current.log_level)
    if current.api_key is None:
        raise RuntimeError("LINK_HOARDER_API_KEY is required.")
    repository = BookmarkRepository(current.database_url)
    repository.initialize()
    metadata = BookmarkMetadataService(
        repository,
        current.metadata_cache_path,
        fetcher=metadata_fetcher,
        enabled=current.metadata_refresh_enabled,
    )
    expected_key = current.api_key.get_secret_value()

    def require_api_key(provided: Annotated[str | None, Security(_API_KEY)]) -> None:
        if provided is None or not secrets.compare_digest(provided, expected_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid API key is required.",
                headers={"WWW-Authenticate": "APIKey"},
            )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        del application
        try:
            yield
        finally:
            metadata.close()
            repository.close()

    authorized = [Depends(require_api_key)]
    api = FastAPI(
        title="Link Hoarder API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    router = APIRouter(prefix=_API_PREFIX, dependencies=authorized)

    @api.exception_handler(RequestValidationError)
    def validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del request
        details = [
            {key: value for key, value in item.items() if key in {"loc", "msg", "type"}}
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": details},
        )

    @api.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @api.get("/health", dependencies=authorized, tags=["system"])
    def health() -> Health:
        return Health()

    @router.post(
        "/bookmarks",
        response_model=BookmarkRead,
        status_code=status.HTTP_201_CREATED,
        responses={status.HTTP_409_CONFLICT: {"model": ErrorDetail}},
        tags=["bookmarks"],
    )
    def create_bookmark(bookmark: BookmarkCreate) -> BookmarkRead:
        try:
            created = repository.create(bookmark)
        except DuplicateBookmarkError as error:
            raise _duplicate() from error
        metadata.queue_refresh(created)
        return created

    @router.get("/bookmarks", tags=["bookmarks"])
    def list_bookmarks(
        query: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
        sort: Annotated[BookmarkSort | None, Query()] = None,
    ) -> BookmarkPresentationPage:
        bookmarks = repository.list(query=query, limit=limit, offset=offset, sort=sort)
        metadata.queue_refresh_many(bookmarks)
        availability = metadata.asset_availability(bookmarks)
        return BookmarkPresentationPage(
            items=[
                _present_bookmark(bookmark, availability.get(bookmark.id))
                for bookmark in bookmarks
            ],
            total=repository.count(query=query),
            limit=limit,
            offset=offset,
        )

    @router.get("/bookmarks/by-url", tags=["bookmarks"])
    def get_bookmark_by_url(url: Annotated[str, Query(min_length=1)]) -> BookmarkRead:
        bookmark = repository.find_by_url(url)
        if bookmark is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="A bookmark with this URL was not found.",
            )
        return bookmark

    @router.get("/bookmarks/{bookmark_id}", tags=["bookmarks"])
    def get_bookmark(bookmark_id: int) -> BookmarkRead:
        bookmark = repository.get(bookmark_id)
        if bookmark is None:
            raise _not_found(bookmark_id)
        return bookmark

    @router.get("/bookmarks/{bookmark_id}/favicon", tags=["bookmarks"])
    def get_bookmark_favicon(bookmark_id: int, request: Request) -> Response:
        bookmark = repository.get(bookmark_id)
        if bookmark is None:
            raise _not_found(bookmark_id)
        metadata.queue_refresh(bookmark)
        path = metadata.asset_path(bookmark_id, "favicon")
        if path is not None:
            media_type = "image/svg+xml" if path.suffix == ".svg" else "image/png"
            return _cached_file_response(request, path, media_type=media_type)
        return _cached_content_response(
            request,
            generated_domain_icon(bookmark.url),
            media_type="image/svg+xml",
        )

    @router.get("/bookmarks/{bookmark_id}/thumbnail", tags=["bookmarks"])
    def get_bookmark_thumbnail(bookmark_id: int, request: Request) -> Response:
        bookmark = repository.get(bookmark_id)
        if bookmark is None:
            raise _not_found(bookmark_id)
        metadata.queue_refresh(bookmark)
        path = metadata.asset_path(bookmark_id, "thumbnail")
        if path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The bookmark has no cached thumbnail.",
            )
        return _cached_file_response(request, path, media_type="image/png")

    @router.get("/bookmarks/{bookmark_id}/preview", tags=["bookmarks"])
    def get_bookmark_preview(bookmark_id: int) -> BookmarkPreview:
        bookmark = repository.get(bookmark_id)
        if bookmark is None:
            raise _not_found(bookmark_id)
        cached = repository.get_metadata(bookmark_id)
        if cached is None or (
            cached.preview_text is None and cached.status is MetadataStatus.READY
        ):
            # The popup fetches on demand when the background cache has
            # no excerpt yet; the refresh stores the row for later opens.
            # Failed rows stay on the async backoff path instead, so a
            # doomed fetch never blocks the popup twice.
            metadata.refresh(bookmark)
            cached = repository.get_metadata(bookmark_id)
        else:
            metadata.queue_refresh(bookmark)
        image_url = None
        if (
            cached is not None
            and cached.thumbnail_file is not None
            and metadata.asset_path(bookmark_id, "thumbnail") is not None
        ):
            image_url = f"{_API_PREFIX}/bookmarks/{bookmark_id}/thumbnail"
        if cached is None:
            return BookmarkPreview(bookmark_id=bookmark_id, image_url=image_url)
        return BookmarkPreview(
            bookmark_id=bookmark_id,
            title=cached.preview_title,
            description=cached.preview_description,
            site_name=cached.preview_site,
            excerpt=cached.preview_text,
            image_url=image_url,
        )

    @router.patch(
        "/bookmarks/{bookmark_id}",
        responses={status.HTTP_409_CONFLICT: {"model": ErrorDetail}},
        tags=["bookmarks"],
    )
    def update_bookmark(bookmark_id: int, update: BookmarkUpdate) -> BookmarkRead:
        try:
            bookmark = repository.update(bookmark_id, update)
        except DuplicateBookmarkError as error:
            raise _duplicate() from error
        if bookmark is None:
            raise _not_found(bookmark_id)
        metadata.queue_refresh(bookmark)
        return bookmark

    @router.delete(
        "/bookmarks/{bookmark_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["bookmarks"],
    )
    def delete_bookmark(bookmark_id: int) -> Response:
        if repository.get(bookmark_id) is None:
            raise _not_found(bookmark_id)
        metadata.purge_assets(bookmark_id)
        repository.delete(bookmark_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/imports/bookmarks-file", tags=["imports"])
    def import_bookmarks_file(
        content: Annotated[
            bytes,
            Body(
                media_type="text/html",
                min_length=1,
                max_length=_MAX_PROFILE_BYTES,
            ),
        ],
    ) -> HtmlImportResult:
        filename = "bookmarks.html"
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / filename
            profile.write_bytes(content)
            detail = import_html_export_detailed(repository, profile)
            # An import is bulk backlog work. It must not consume the
            # capacity reserved for bookmarks the user is looking at.
            metadata.queue_backfill(detail.created)
            warnings = [
                warning.model_copy(update={"profile": filename})
                for warning in detail.result.warnings
            ]
            return detail.result.model_copy(update={"warnings": warnings})

    @router.post("/imports/bookmarks-json", tags=["imports"])
    def import_bookmarks_json(
        bookmarks: Annotated[
            list[BookmarkCreate],
            Body(min_length=1, max_length=_MAX_JSON_ITEMS),
        ],
    ) -> JsonImportResult:
        imported = 0
        skipped = 0
        warnings: list[ImportWarning] = []
        created: list[BookmarkRead] = []
        for bookmark in bookmarks:
            if repository.find_by_url(bookmark.url) is not None:
                skipped += 1
                warnings.append(
                    ImportWarning(
                        code=ImportWarningCode.BOOKMARK_DUPLICATE,
                        message=(
                            f"The bookmark '{bookmark.title}' was skipped "
                            "because it already exists."
                        ),
                        profile=_JSON_IMPORT_PROFILE,
                    )
                )
                continue
            try:
                stored = repository.create(bookmark)
            except DuplicateBookmarkError:
                skipped += 1
                warnings.append(
                    ImportWarning(
                        code=ImportWarningCode.BOOKMARK_DUPLICATE,
                        message=(
                            f"The bookmark '{bookmark.title}' was skipped "
                            "because it already exists."
                        ),
                        profile=_JSON_IMPORT_PROFILE,
                    )
                )
                continue
            imported += 1
            created.append(stored)
        # An import is bulk backlog work. It must not consume the
        # capacity reserved for bookmarks the user is looking at.
        metadata.queue_backfill(created)
        return JsonImportResult(
            profiles=1,
            discovered=len(bookmarks),
            imported=imported,
            skipped=skipped,
            warnings=warnings,
        )

    api.include_router(router)
    return api


def _present_bookmark(
    bookmark: BookmarkRead, availability: BookmarkAssetAvailability | None
) -> BookmarkPresentationRead:
    favicon_url = None
    thumbnail_url = None
    if not bookmark.url.lower().startswith("javascript:"):
        favicon_url = f"{_API_PREFIX}/bookmarks/{bookmark.id}/favicon"
        if availability is not None and availability.has_thumbnail:
            thumbnail_url = f"{_API_PREFIX}/bookmarks/{bookmark.id}/thumbnail"
    return BookmarkPresentationRead.model_validate(
        {
            **bookmark.model_dump(),
            "favicon_url": favicon_url,
            "thumbnail_url": thumbnail_url,
        }
    )


def _cached_file_response(request: Request, path: Path, *, media_type: str) -> Response:
    # The ETag comes from the cached file's size and modification time, not
    # a content hash. Assets are up to 5 MiB, and this route can serve them
    # on every bookmark render, so hashing the full file on each request
    # would repeat the same I/O the cache is meant to avoid. `queue_refresh`
    # always replaces a cached file through a write-then-rename, so the
    # modification time changes on every content update.
    try:
        stat = path.stat()
    except OSError as error:
        # A concurrent purge or refresh can remove the file after the
        # service verified it. Report a missing asset, not a server fault.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The bookmark asset is no longer cached.",
        ) from error
    etag = f'"{stat.st_size:x}-{int(stat.st_mtime_ns):x}"'
    not_modified = _not_modified_response(request, etag)
    if not_modified is not None:
        return not_modified
    response: Response = FileResponse(path, media_type=media_type)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = _ASSET_CACHE_CONTROL
    return response


def _cached_content_response(
    request: Request, content: str, *, media_type: str
) -> Response:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    etag = f'"{digest}"'
    not_modified = _not_modified_response(request, etag)
    if not_modified is not None:
        return not_modified
    return Response(
        content=content,
        media_type=media_type,
        headers={"ETag": etag, "Cache-Control": _ASSET_CACHE_CONTROL},
    )


def _not_modified_response(request: Request, etag: str) -> Response | None:
    if not _matches_if_none_match(request.headers.get("if-none-match"), etag):
        return None
    return Response(
        status_code=status.HTTP_304_NOT_MODIFIED,
        headers={"ETag": etag, "Cache-Control": _ASSET_CACHE_CONTROL},
    )


def _matches_if_none_match(header: str | None, etag: str) -> bool:
    """Compare an If-None-Match header with one entity tag.

    RFC 9110 permits `*` and a list of entity tags. Comparison is weak, so
    a `W/` prefix on either side does not prevent a match.
    """
    if header is None:
        return False
    candidate = etag.removeprefix("W/")
    for item in header.split(","):
        value = item.strip()
        if value == "*" or value.removeprefix("W/") == candidate:
            return True
    return False


def _not_found(bookmark_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Bookmark {bookmark_id} was not found.",
    )


def _duplicate() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A bookmark already uses this URL.",
    )
