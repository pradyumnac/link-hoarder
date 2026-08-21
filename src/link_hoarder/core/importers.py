"""Native browser profile importers."""

import os
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field, ValidationError

from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkSource,
    Browser,
    ImportResult,
)
from link_hoarder.core.repository import BookmarkRepository


class ChromeNode(BaseModel):
    """Validated Chromium bookmark tree node."""

    name: str = ""
    type: str = "folder"
    url: str | None = None
    date_added: str | None = None
    children: list[ChromeNode] = Field(default_factory=list)


class ChromeFile(BaseModel):
    """Validated Chromium bookmarks file."""

    roots: dict[str, ChromeNode]


def discover_profiles(browser: Browser) -> list[Path]:
    """Discover native browser profile data files."""
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA", home))
    roaming = Path(os.environ.get("APPDATA", home))

    roots: dict[Browser, list[Path]] = {
        Browser.CHROME: [
            home / ".config/google-chrome",
            local / "Google/Chrome/User Data",
        ],
        Browser.CHROMIUM: [home / ".config/chromium", local / "Chromium/User Data"],
        Browser.EDGE: [
            home / ".config/microsoft-edge",
            local / "Microsoft/Edge/User Data",
        ],
        Browser.FIREFOX: [
            home / ".mozilla/firefox",
            roaming / "Mozilla/Firefox/Profiles",
        ],
    }
    filename = "places.sqlite" if browser is Browser.FIREFOX else "Bookmarks"
    found = {
        path.resolve()
        for root in roots[browser]
        if root.exists()
        for path in root.glob(f"*/{filename}")
        if path.is_file()
    }
    return sorted(found)


def read_profile(browser: Browser, path: Path) -> list[BookmarkCreate]:
    """Read bookmarks from one browser data file."""
    if browser is Browser.FIREFOX:
        return _read_firefox(path)
    return _read_chromium(browser, path)


def import_profiles(
    repository: BookmarkRepository,
    browser: Browser,
    profile: Path | None = None,
) -> ImportResult:
    """Import new URLs from native browser profiles."""
    profiles = [profile] if profile is not None else discover_profiles(browser)
    discovered = 0
    imported = 0
    skipped = 0
    for current in profiles:
        bookmarks = read_profile(browser, current)
        discovered += len(bookmarks)
        for bookmark in bookmarks:
            if repository.find_by_url(bookmark.url) is not None:
                skipped += 1
                continue
            repository.create(bookmark)
            imported += 1
    return ImportResult(
        browser=browser,
        profiles=len(profiles),
        discovered=discovered,
        imported=imported,
        skipped=skipped,
    )


def _read_chromium(browser: Browser, path: Path) -> list[BookmarkCreate]:
    data = ChromeFile.model_validate_json(path.read_text(encoding="utf-8"))
    source = BookmarkSource(browser.value)
    bookmarks: list[BookmarkCreate] = []
    for root in data.roots.values():
        bookmarks.extend(_walk_chrome(root, source, ()))
    return bookmarks


def _walk_chrome(
    node: ChromeNode,
    source: BookmarkSource,
    parents: tuple[str, ...],
) -> list[BookmarkCreate]:
    if node.type == "url" and node.url:
        folder = "/".join(parents) or None
        try:
            bookmark = BookmarkCreate(
                url=node.url,
                title=node.name or node.url,
                folder=folder,
                source=source,
            )
        except ValidationError:
            return []
        return [bookmark]
    next_parents = (*parents, node.name) if node.name else parents
    return [
        bookmark
        for child in node.children
        for bookmark in _walk_chrome(child, source, next_parents)
    ]


def _read_firefox(path: Path) -> list[BookmarkCreate]:
    with tempfile.TemporaryDirectory() as temporary:
        copied = Path(temporary) / "places.sqlite"
        shutil.copy2(path, copied)
        wal = path.with_name(f"{path.name}-wal")
        if wal.exists():
            shutil.copy2(wal, copied.with_name(f"{copied.name}-wal"))
        with sqlite3.connect(copied) as connection:
            rows = connection.execute(
                """
                SELECT p.url, COALESCE(b.title, p.title, p.url), f.title
                FROM moz_bookmarks AS b
                JOIN moz_places AS p ON p.id = b.fk
                LEFT JOIN moz_bookmarks AS f ON f.id = b.parent
                WHERE b.type = 1 AND p.url LIKE 'http%'
                ORDER BY b.id
                """
            ).fetchall()
    return [
        BookmarkCreate(
            url=cast(str, row[0]),
            title=cast(str, row[1]),
            folder=cast(str | None, row[2]),
            source=BookmarkSource.FIREFOX,
        )
        for row in rows
    ]


def chromium_time(value: str | None) -> datetime | None:
    """Convert a Chromium timestamp for callers that need metadata."""
    if not value:
        return None
    return datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=int(value))
