"""Authenticated FastAPI application."""

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
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from link_hoarder.core.config import Settings
from link_hoarder.core.importers import import_html_export
from link_hoarder.core.logging import configure_logging
from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkPage,
    BookmarkRead,
    BookmarkUpdate,
    HtmlImportResult,
)
from link_hoarder.core.repository import BookmarkRepository, DuplicateBookmarkError

_API_KEY = APIKeyHeader(name="X-API-Key", auto_error=False)
_API_PREFIX = "/api/v1"
_MAX_PROFILE_BYTES = 16 * 1024 * 1024


class Health(BaseModel):
    """API health response."""

    status: str = "ok"


class ErrorDetail(BaseModel):
    """API error response."""

    detail: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an API application with initialized storage."""
    current = settings or Settings()
    configure_logging(current.log_level)
    if current.api_key is None:
        raise RuntimeError("LINK_HOARDER_API_KEY is required.")
    repository = BookmarkRepository(current.database_url)
    repository.initialize()
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
            return repository.create(bookmark)
        except DuplicateBookmarkError as error:
            raise _duplicate() from error

    @router.get("/bookmarks", tags=["bookmarks"])
    def list_bookmarks(
        query: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> BookmarkPage:
        return BookmarkPage(
            items=repository.list(query=query, limit=limit, offset=offset),
            total=repository.count(query=query),
            limit=limit,
            offset=offset,
        )

    @router.get("/bookmarks/{bookmark_id}", tags=["bookmarks"])
    def get_bookmark(bookmark_id: int) -> BookmarkRead:
        bookmark = repository.get(bookmark_id)
        if bookmark is None:
            raise _not_found(bookmark_id)
        return bookmark

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
        return bookmark

    @router.delete(
        "/bookmarks/{bookmark_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["bookmarks"],
    )
    def delete_bookmark(bookmark_id: int) -> Response:
        if not repository.delete(bookmark_id):
            raise _not_found(bookmark_id)
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
            result = import_html_export(repository, profile)
            warnings = [
                warning.model_copy(update={"profile": filename})
                for warning in result.warnings
            ]
            return result.model_copy(update={"warnings": warnings})

    api.include_router(router)
    return api


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
