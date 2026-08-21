"""Authenticated FastAPI application."""

import secrets
import sqlite3
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    Security,
    status,
)
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ValidationError

from link_hoarder.core.config import Settings
from link_hoarder.core.importers import import_profiles
from link_hoarder.core.logging import configure_logging
from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkPage,
    BookmarkRead,
    BookmarkUpdate,
    Browser,
    ImportRequest,
    ImportResult,
)
from link_hoarder.core.repository import BookmarkRepository, DuplicateBookmarkError

_API_KEY = APIKeyHeader(name="X-API-Key", auto_error=False)
_API_PREFIX = "/api/v1"


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
            )

    authorized = [Depends(require_api_key)]
    api = FastAPI(title="Link Hoarder API", version="0.1.0")
    router = APIRouter(prefix=_API_PREFIX, dependencies=authorized)

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
            raise _duplicate(error.url) from error

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
            raise _duplicate(error.url) from error
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

    @router.post("/imports/browser", tags=["imports"])
    def import_browser(request: ImportRequest) -> ImportResult:
        profile = Path(request.profile) if request.profile else None
        if profile is not None and not profile.is_file():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The browser profile file does not exist.",
            )
        return import_profiles(repository, request.browser, profile)

    @router.post("/imports/browser-file", tags=["imports"])
    def import_browser_file(
        browser: Annotated[Browser, Query()],
        content: Annotated[
            bytes,
            Body(media_type="application/octet-stream", min_length=1),
        ],
    ) -> ImportResult:
        filename = "places.sqlite" if browser is Browser.FIREFOX else "Bookmarks"
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / filename
            profile.write_bytes(content)
            try:
                return import_profiles(repository, browser, profile)
            except (
                OSError,
                UnicodeError,
                ValidationError,
                sqlite3.DatabaseError,
            ) as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The uploaded browser profile is not valid.",
                ) from error

    api.include_router(router)
    return api


def _not_found(bookmark_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Bookmark {bookmark_id} was not found.",
    )


def _duplicate(url: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"A bookmark already uses URL {url}.",
    )
