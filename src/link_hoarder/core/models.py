"""Validated bookmark models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import HttpUrl, TypeAdapter, field_validator, model_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

_URL_ADAPTER = TypeAdapter(HttpUrl)


def _is_bookmarklet(value: str) -> bool:
    """Return whether a URL is a JavaScript bookmarklet."""
    return value.lower().startswith("javascript:")


def _validate_bookmark_url(value: str) -> str:
    """Validate an HTTP, HTTPS, or JavaScript bookmark URL."""
    if _is_bookmarklet(value):
        return f"javascript:{value[11:]}"
    return str(_URL_ADAPTER.validate_python(value))


class Browser(StrEnum):
    """Supported browser families."""

    BRAVE = "brave"
    CHROME = "chrome"
    CHROMIUM = "chromium"
    EDGE = "edge"
    FIREFOX = "firefox"
    ZEN = "zen"


class BookmarkSource(StrEnum):
    """Bookmark origin."""

    MANUAL = "manual"
    BRAVE = "brave"
    CHROME = "chrome"
    CHROMIUM = "chromium"
    EDGE = "edge"
    FIREFOX = "firefox"
    HTML = "html"
    ZEN = "zen"


class BookmarkSort(StrEnum):
    """Bookmark list sort order by original save time."""

    NEWEST = "newest"
    OLDEST = "oldest"


class PreviewProvider(StrEnum):
    """Link preview backend."""

    BUILTIN = "builtin"
    SIDECAR = "sidecar"


class BookmarkFields(SQLModel):
    """Fields shared by bookmark input and storage models."""

    url: str = Field(index=True, unique=True, min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=512)
    folder: str | None = Field(default=None, max_length=1024)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source: BookmarkSource = BookmarkSource.MANUAL

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Require an HTTP, HTTPS, or JavaScript URL."""
        return _validate_bookmark_url(value)


class BookmarkRecord(BookmarkFields, table=True):
    """SQLite bookmark row."""

    __tablename__ = "bookmarks"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BookmarkCreate(BookmarkFields):
    """Bookmark creation input."""

    created_at: datetime | None = Field(default=None)
    """Original save time. Importers set this; creation time is the default."""

    @model_validator(mode="after")
    def tag_bookmarklet(self) -> BookmarkCreate:
        """Add the bookmarklet tag to JavaScript URLs."""
        if _is_bookmarklet(self.url) and "bookmarklet" not in self.tags:
            self.tags.append("bookmarklet")
        return self


class BookmarkUpdate(SQLModel):
    """Partial bookmark update input."""

    url: str | None = Field(default=None, min_length=1, max_length=2048)
    title: str | None = Field(default=None, min_length=1, max_length=512)
    folder: str | None = Field(default=None, max_length=1024)
    tags: list[str] | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        """Validate a URL when the update includes one."""
        if value is None:
            return None
        return _validate_bookmark_url(value)


class BookmarkRead(BookmarkFields):
    """Bookmark output."""

    id: int
    created_at: datetime
    updated_at: datetime


class BookmarkPage(SQLModel):
    """Paginated bookmark output."""

    items: list[BookmarkRead]
    total: int
    limit: int
    offset: int


class BookmarkPresentationRead(BookmarkRead):
    """Bookmark output with same-origin presentation assets."""

    favicon_url: str | None = None
    thumbnail_url: str | None = None


class BookmarkPresentationPage(SQLModel):
    """Paginated bookmark presentation output."""

    items: list[BookmarkPresentationRead]
    total: int
    limit: int
    offset: int


class MetadataStatus(StrEnum):
    """Bookmark metadata refresh result."""

    READY = "ready"
    FAILED = "failed"
    BLOCKED = "blocked"


class BookmarkMetadataRecord(SQLModel, table=True):
    """SQLite bookmark metadata cache row."""

    __tablename__ = "bookmark_metadata"

    bookmark_id: int = Field(primary_key=True, foreign_key="bookmarks.id")
    source_url: str = Field(max_length=2048)
    status: MetadataStatus
    favicon_file: str | None = Field(default=None, max_length=255)
    thumbnail_file: str | None = Field(default=None, max_length=255)
    preview_title: str | None = Field(default=None, max_length=300)
    preview_description: str | None = Field(default=None, max_length=500)
    preview_site: str | None = Field(default=None, max_length=255)
    refreshed_at: datetime
    retry_after: datetime


class BookmarkPreview(SQLModel):
    """Cached link preview for one bookmark."""

    bookmark_id: int
    title: str | None = None
    description: str | None = None
    site_name: str | None = None
    image_url: str | None = None


class ImportWarningCode(StrEnum):
    """Bookmark import warning category."""

    BOOKMARK_INVALID = "bookmark_invalid"
    BOOKMARK_DUPLICATE = "bookmark_duplicate"
    BOOKMARK_STORE_FAILED = "bookmark_store_failed"
    PROFILE_INVALID = "profile_invalid"
    PROFILE_UNREADABLE = "profile_unreadable"


class ImportWarning(SQLModel):
    """One import failure that did not stop the full import."""

    code: ImportWarningCode
    message: str
    profile: str


class ImportSummary(SQLModel):
    """Fields shared by bookmark import results."""

    profiles: int
    discovered: int
    imported: int
    skipped: int
    warnings: list[ImportWarning] = Field(default_factory=list)


class ImportResult(ImportSummary):
    """Native browser profile import result."""

    browser: Browser


class HtmlImportResult(ImportSummary):
    """Bookmark HTML export import result."""

    format: Literal["netscape_html"] = "netscape_html"


class JsonImportResult(ImportSummary):
    """Bookmark JSON export import result."""

    format: Literal["link_hoarder_json"] = "link_hoarder_json"
