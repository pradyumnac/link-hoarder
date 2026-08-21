"""Bookmark backend interface and shared errors."""

from typing import Protocol

from link_hoarder.core.models import BookmarkCreate, BookmarkRead, BookmarkUpdate


class BookmarkBackendError(Exception):
    """A bookmark backend request failed."""


class BookmarkStorageError(BookmarkBackendError):
    """The bookmark backend could not complete a write."""


class DuplicateBookmarkError(BookmarkStorageError):
    """A bookmark already uses the normalized URL."""

    def __init__(self, url: str) -> None:
        super().__init__(f"A bookmark already uses URL {url}.")
        self.url = url


class BookmarkBackend(Protocol):
    """Provide bookmark operations to interface adapters and import services."""

    def create(self, bookmark: BookmarkCreate) -> BookmarkRead:
        """Create one bookmark."""
        ...

    def get(self, bookmark_id: int) -> BookmarkRead | None:
        """Get one bookmark by identifier."""
        ...

    def find_by_url(self, url: str) -> BookmarkRead | None:
        """Get one bookmark by its normalized URL."""
        ...

    def list(
        self, *, query: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[BookmarkRead]:
        """List bookmarks with optional search and pagination."""
        ...

    def update(self, bookmark_id: int, update: BookmarkUpdate) -> BookmarkRead | None:
        """Update one bookmark."""
        ...

    def delete(self, bookmark_id: int) -> bool:
        """Delete one bookmark."""
        ...

    def close(self) -> None:
        """Release backend resources."""
        ...
