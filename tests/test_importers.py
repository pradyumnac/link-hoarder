"""Native browser importer tests."""

import json
import sqlite3
from pathlib import Path

import pytest

from link_hoarder.core import importers
from link_hoarder.core.importers import discover_profiles, import_profiles, read_profile
from link_hoarder.core.models import BookmarkCreate, BookmarkRead, Browser
from link_hoarder.core.repository import BookmarkRepository, BookmarkStorageError


@pytest.mark.parametrize(
    ("browser", "environment", "relative"),
    [
        (Browser.CHROME, "LOCALAPPDATA", "Google/Chrome/User Data/Default/Bookmarks"),
        (Browser.FIREFOX, "APPDATA", "Mozilla/Firefox/Profiles/default/places.sqlite"),
    ],
)
def test_discover_windows_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    browser: Browser,
    environment: str,
    relative: str,
) -> None:
    """Given Windows data environment paths, profile discovery finds native files."""
    monkeypatch.setenv(environment, str(tmp_path))
    profile = tmp_path / relative
    profile.parent.mkdir(parents=True)
    profile.touch()

    assert profile.resolve() in discover_profiles(browser)


def test_read_chromium_nested_bookmark(tmp_path: Path) -> None:
    """Given a nested Chromium file, the importer keeps the folder path."""
    profile = tmp_path / "Bookmarks"
    profile.write_text(
        json.dumps(
            {
                "roots": {
                    "bookmark_bar": {
                        "name": "Bookmarks bar",
                        "type": "folder",
                        "children": [
                            {
                                "name": "Python",
                                "type": "folder",
                                "children": [
                                    {
                                        "name": "Python",
                                        "type": "url",
                                        "url": "https://python.org",
                                    }
                                ],
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = read_profile(Browser.CHROME, profile)

    assert len(result.bookmarks) == 1
    assert result.bookmarks[0].folder == "Bookmarks bar/Python"
    assert result.bookmarks[0].url == "https://python.org/"
    assert result.warnings == []


def test_read_chromium_imports_bookmarklet(tmp_path: Path) -> None:
    """Given a Chromium bookmarklet, the importer preserves its JavaScript URL."""
    profile = tmp_path / "Bookmarks"
    profile.write_text(
        json.dumps(
            {
                "roots": {
                    "bookmark_bar": {
                        "children": [
                            {
                                "name": "Bookmarklet",
                                "type": "url",
                                "url": "javascript:alert('unsupported')",
                            },
                            {
                                "name": "Example",
                                "type": "url",
                                "url": "https://example.com",
                            },
                            {
                                "name": "Unsupported",
                                "type": "url",
                                "url": "ftp://example.com",
                            },
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = read_profile(Browser.CHROME, profile)

    assert [bookmark.url for bookmark in result.bookmarks] == [
        "javascript:alert('unsupported')",
        "https://example.com/",
    ]
    assert result.bookmarks[0].tags == ["bookmarklet"]
    assert result.bookmarks[1].tags == []
    assert result.discovered == 3
    assert result.warnings[0].code == "bookmark_invalid"


def test_read_firefox_bookmark(tmp_path: Path) -> None:
    """Given a Firefox places database, the importer reads HTTP bookmarks."""
    profile = tmp_path / "places.sqlite"
    with sqlite3.connect(profile) as connection:
        connection.executescript(
            """
            CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT, title TEXT);
            CREATE TABLE moz_bookmarks (
                id INTEGER PRIMARY KEY, fk INTEGER, type INTEGER, title TEXT, parent INTEGER
            );
            INSERT INTO moz_places VALUES (1, 'https://example.com', 'Example');
            INSERT INTO moz_bookmarks VALUES (10, NULL, 2, 'Toolbar', 0);
            INSERT INTO moz_bookmarks VALUES (11, 1, 1, NULL, 10);
            """
        )

    result = read_profile(Browser.FIREFOX, profile)

    assert len(result.bookmarks) == 1
    assert result.bookmarks[0].title == "Example"
    assert result.bookmarks[0].folder == "Toolbar"


def test_import_skips_existing_url(
    tmp_path: Path, repository: BookmarkRepository
) -> None:
    """Given duplicate profile URLs, a second import skips stored bookmarks."""
    profile = tmp_path / "Bookmarks"
    profile.write_text(
        json.dumps(
            {
                "roots": {
                    "other": {
                        "children": [
                            {
                                "name": "Example",
                                "type": "url",
                                "url": "https://example.com",
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    first = import_profiles(repository, Browser.CHROMIUM, profile)
    second = import_profiles(repository, Browser.CHROMIUM, profile)

    assert first.imported == 1
    assert second.imported == 0
    assert second.skipped == 1


def test_import_warns_for_malformed_profile(
    tmp_path: Path, repository: BookmarkRepository
) -> None:
    """Given malformed profile data, import returns a profile warning."""
    profile = tmp_path / "Bookmarks"
    profile.write_text("not-json", encoding="utf-8")

    result = import_profiles(repository, Browser.CHROME, profile)

    assert result.imported == 0
    assert result.warnings[0].code == "profile_invalid"


def test_import_warns_for_unreadable_profile(
    tmp_path: Path,
    repository: BookmarkRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given an unreadable profile, import returns a profile warning."""
    profile = tmp_path / "Bookmarks"

    def fail_read(browser: Browser, path: Path) -> importers.ProfileReadResult:
        raise PermissionError(path)

    monkeypatch.setattr(importers, "read_profile", fail_read)

    result = import_profiles(repository, Browser.CHROME, profile)

    assert result.imported == 0
    assert result.warnings[0].code == "profile_unreadable"


def test_import_continues_after_storage_failure(
    tmp_path: Path,
    repository: BookmarkRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given one storage failure, import warns and stores later bookmarks."""
    profile = tmp_path / "Bookmarks"
    profile.write_text(
        json.dumps(
            {
                "roots": {
                    "other": {
                        "children": [
                            {
                                "name": "Fail",
                                "type": "url",
                                "url": "https://fail.example",
                            },
                            {
                                "name": "Keep",
                                "type": "url",
                                "url": "https://keep.example",
                            },
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    original_create = repository.create

    def fail_one(bookmark: BookmarkCreate) -> BookmarkRead:
        if bookmark.url == "https://fail.example/":
            raise BookmarkStorageError("storage unavailable")
        return original_create(bookmark)

    monkeypatch.setattr(repository, "create", fail_one)

    result = import_profiles(repository, Browser.CHROME, profile)

    assert result.imported == 1
    assert result.discovered == 2
    assert result.warnings[0].code == "bookmark_store_failed"
    assert repository.find_by_url("https://keep.example/") is not None
