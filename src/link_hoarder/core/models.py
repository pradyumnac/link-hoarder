"""Validated bookmark models."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import HttpUrl, TypeAdapter, field_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

_URL_ADAPTER = TypeAdapter(HttpUrl)


class Browser(StrEnum):
    """Supported browser families."""

    CHROME = "chrome"
    CHROMIUM = "chromium"
    EDGE = "edge"
    FIREFOX = "firefox"


class BookmarkSource(StrEnum):
    """Bookmark origin."""

    MANUAL = "manual"
    CHROME = "chrome"
    CHROMIUM = "chromium"
    EDGE = "edge"
    FIREFOX = "firefox"


class BookmarkFields(SQLModel):
    """Fields shared by bookmark input and storage models."""

    url: str = Field(index=True, min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=512)
    folder: str | None = Field(default=None, max_length=1024)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source: BookmarkSource = BookmarkSource.MANUAL

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Require an HTTP or HTTPS URL."""
        return str(_URL_ADAPTER.validate_python(value))


class BookmarkRecord(BookmarkFields, table=True):
    """SQLite bookmark row."""

    __tablename__ = "bookmarks"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BookmarkCreate(BookmarkFields):
    """Bookmark creation input."""


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
        return str(_URL_ADAPTER.validate_python(value))


class BookmarkRead(BookmarkFields):
    """Bookmark output."""

    id: int
    created_at: datetime
    updated_at: datetime


class ImportRequest(SQLModel):
    """Native browser import request."""

    browser: Browser
    profile: str | None = None


class ImportResult(SQLModel):
    """Browser import result."""

    browser: Browser
    profiles: int
    discovered: int
    imported: int
    skipped: int
