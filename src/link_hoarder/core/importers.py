"""Native browser profile importers."""

import os
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import structlog
from pydantic import BaseModel, Field, ValidationError

from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkSource,
    Browser,
    ImportResult,
    ImportWarning,
    ImportWarningCode,
)
from link_hoarder.core.repository import (
    BookmarkRepository,
    BookmarkStorageError,
    DuplicateBookmarkError,
)

logger = structlog.get_logger(__name__)


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


class ProfileReadResult(BaseModel):
    """Validated bookmarks and warnings from one browser profile."""

    bookmarks: list[BookmarkCreate] = Field(default_factory=list)
    discovered: int = 0
    warnings: list[ImportWarning] = Field(default_factory=list)


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


def read_profile(browser: Browser, path: Path) -> ProfileReadResult:
    """Read bookmarks and entry warnings from one browser data file."""
    if browser is Browser.FIREFOX:
        return _read_firefox(path)
    return _read_chromium(browser, path)


def import_profiles(
    repository: BookmarkRepository,
    browser: Browser,
    profile: Path | None = None,
) -> ImportResult:
    """Import new URLs and report failures from native browser profiles."""
    profiles = [profile] if profile is not None else discover_profiles(browser)
    discovered = 0
    imported = 0
    skipped = 0
    warnings: list[ImportWarning] = []
    for current in profiles:
        try:
            profile_result = read_profile(browser, current)
        except OSError as error:
            logger.warning(
                "browser_profile_unreadable",
                profile=str(current),
                error_type=type(error).__name__,
            )
            warnings.append(
                _warning(
                    ImportWarningCode.PROFILE_UNREADABLE,
                    "The browser profile could not be read.",
                    current,
                )
            )
            continue
        except (UnicodeError, ValidationError, sqlite3.DatabaseError) as error:
            logger.warning(
                "browser_profile_invalid",
                profile=str(current),
                error_type=type(error).__name__,
            )
            warnings.append(
                _warning(
                    ImportWarningCode.PROFILE_INVALID,
                    "The browser profile format is invalid.",
                    current,
                )
            )
            continue

        discovered += profile_result.discovered
        warnings.extend(profile_result.warnings)
        for bookmark in profile_result.bookmarks:
            if repository.find_by_url(bookmark.url) is not None:
                skipped += 1
                continue
            try:
                repository.create(bookmark)
            except DuplicateBookmarkError:
                skipped += 1
                continue
            except BookmarkStorageError as error:
                logger.warning(
                    "bookmark_import_store_failed",
                    profile=str(current),
                    title=_short_title(bookmark.title),
                    error_type=type(error).__name__,
                )
                warnings.append(
                    _warning(
                        ImportWarningCode.BOOKMARK_STORE_FAILED,
                        f"The bookmark '{_short_title(bookmark.title)}' could not be stored.",
                        current,
                    )
                )
                continue
            imported += 1
    return ImportResult(
        browser=browser,
        profiles=len(profiles),
        discovered=discovered,
        imported=imported,
        skipped=skipped,
        warnings=warnings,
    )


def _read_chromium(browser: Browser, path: Path) -> ProfileReadResult:
    data = ChromeFile.model_validate_json(path.read_text(encoding="utf-8"))
    source = BookmarkSource(browser.value)
    result = ProfileReadResult()
    for root in data.roots.values():
        _walk_chrome(root, source, (), path, result)
    return result


def _walk_chrome(
    node: ChromeNode,
    source: BookmarkSource,
    parents: tuple[str, ...],
    profile: Path,
    result: ProfileReadResult,
) -> None:
    if node.type == "url" and node.url:
        result.discovered += 1
        folder = "/".join(parents) or None
        try:
            bookmark = BookmarkCreate(
                url=node.url,
                title=node.name or node.url,
                folder=folder,
                source=source,
            )
        except ValidationError:
            result.warnings.append(
                _warning(
                    ImportWarningCode.BOOKMARK_INVALID,
                    f"The bookmark '{_short_title(node.name)}' is invalid.",
                    profile,
                )
            )
            return
        result.bookmarks.append(bookmark)
        return
    next_parents = (*parents, node.name) if node.name else parents
    for child in node.children:
        _walk_chrome(child, source, next_parents, profile, result)


def _read_firefox(path: Path) -> ProfileReadResult:
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
                WHERE b.type = 1
                ORDER BY b.id
                """
            ).fetchall()

    result = ProfileReadResult(discovered=len(rows))
    for row in rows:
        title = cast(str, row[1])
        try:
            bookmark = BookmarkCreate(
                url=cast(str, row[0]),
                title=title,
                folder=cast(str | None, row[2]),
                source=BookmarkSource.FIREFOX,
            )
        except ValidationError:
            result.warnings.append(
                _warning(
                    ImportWarningCode.BOOKMARK_INVALID,
                    f"The bookmark '{_short_title(title)}' is invalid.",
                    path,
                )
            )
            continue
        result.bookmarks.append(bookmark)
    return result


def _warning(code: ImportWarningCode, message: str, profile: Path) -> ImportWarning:
    return ImportWarning(code=code, message=message, profile=str(profile))


def _short_title(title: str) -> str:
    cleaned = title.strip() or "Untitled"
    return f"{cleaned[:77]}..." if len(cleaned) > 80 else cleaned


def chromium_time(value: str | None) -> datetime | None:
    """Convert a Chromium timestamp for callers that need metadata."""
    if not value:
        return None
    return datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=int(value))
