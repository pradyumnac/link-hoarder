"""Authenticated FastAPI application."""

import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from link_hoarder.core.config import Settings
from link_hoarder.core.importers import import_profiles
from link_hoarder.core.logging import configure_logging
from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkRead,
    BookmarkUpdate,
    ImportRequest,
    ImportResult,
)
from link_hoarder.core.repository import BookmarkRepository

_API_KEY = APIKeyHeader(name="X-API-Key", auto_error=False)


class Health(BaseModel):
    """API health response."""

    status: str = "ok"


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
    api = FastAPI(
        title="Link Hoarder API",
        version="0.1.0",
        dependencies=authorized,
    )

    @api.get("/health", response_model=Health, tags=["system"])
    def health() -> Health:
        return Health()

    @api.post(
        "/bookmarks",
        response_model=BookmarkRead,
        status_code=status.HTTP_201_CREATED,
        tags=["bookmarks"],
    )
    def create_bookmark(bookmark: BookmarkCreate) -> BookmarkRead:
        return repository.create(bookmark)

    @api.get("/bookmarks", response_model=list[BookmarkRead], tags=["bookmarks"])
    def list_bookmarks(
        query: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[BookmarkRead]:
        return repository.list(query=query, limit=limit, offset=offset)

    @api.get(
        "/bookmarks/{bookmark_id}", response_model=BookmarkRead, tags=["bookmarks"]
    )
    def get_bookmark(bookmark_id: int) -> BookmarkRead:
        bookmark = repository.get(bookmark_id)
        if bookmark is None:
            raise _not_found(bookmark_id)
        return bookmark

    @api.patch(
        "/bookmarks/{bookmark_id}", response_model=BookmarkRead, tags=["bookmarks"]
    )
    def update_bookmark(bookmark_id: int, update: BookmarkUpdate) -> BookmarkRead:
        bookmark = repository.update(bookmark_id, update)
        if bookmark is None:
            raise _not_found(bookmark_id)
        return bookmark

    @api.delete(
        "/bookmarks/{bookmark_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["bookmarks"],
    )
    def delete_bookmark(bookmark_id: int) -> Response:
        if not repository.delete(bookmark_id):
            raise _not_found(bookmark_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @api.post("/imports/browser", response_model=ImportResult, tags=["imports"])
    def import_browser(request: ImportRequest) -> ImportResult:
        profile = Path(request.profile) if request.profile else None
        if profile is not None and not profile.is_file():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The browser profile file does not exist.",
            )
        return import_profiles(repository, request.browser, profile)

    return api


def _not_found(bookmark_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Bookmark {bookmark_id} was not found.",
    )
