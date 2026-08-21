"""Native browser importer tests."""

import json
import sqlite3
from pathlib import Path

import pytest

from link_hoarder.core import importers
from link_hoarder.core.importers import (
    discover_profiles,
    import_html_export,
    import_profiles,
    read_html_export,
    read_profile,
)
from link_hoarder.core.models import BookmarkCreate, BookmarkRead, Browser
from link_hoarder.core.repository import BookmarkRepository, BookmarkStorageError


@pytest.mark.parametrize(
    ("browser", "environment", "relative"),
    [
        (Browser.CHROME, "LOCALAPPDATA", "Google/Chrome/User Data/Default/Bookmarks"),
        (
            Browser.BRAVE,
            "LOCALAPPDATA",
            "BraveSoftware/Brave-Browser/User Data/Default/Bookmarks",
        ),
        (Browser.FIREFOX, "APPDATA", "Mozilla/Firefox/Profiles/default/places.sqlite"),
        (Browser.ZEN, "APPDATA", "zen/Profiles/default/places.sqlite"),
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


@pytest.mark.parametrize(
    ("browser", "relative"),
    [
        (
            Browser.BRAVE,
            ".config/BraveSoftware/Brave-Browser/Default/Bookmarks",
        ),
        (Browser.ZEN, ".zen/default/places.sqlite"),
    ],
)
def test_discover_linux_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    browser: Browser,
    relative: str,
) -> None:
    """Given Linux home paths, discovery finds Brave and Zen profile files."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    profile = tmp_path / relative
    profile.parent.mkdir(parents=True)
    profile.touch()

    assert profile.resolve() in discover_profiles(browser)


@pytest.mark.parametrize(
    ("browser", "source"),
    [(Browser.CHROME, "chrome"), (Browser.BRAVE, "brave")],
)
def test_read_chromium_nested_bookmark(
    tmp_path: Path, browser: Browser, source: str
) -> None:
    """Given a nested Chromium file, the importer keeps its source and folder."""
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

    result = read_profile(browser, profile)

    assert len(result.bookmarks) == 1
    assert result.bookmarks[0].source == source
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


def test_import_html_export_preserves_folders_and_bookmarklets(
    tmp_path: Path, repository: BookmarkRepository
) -> None:
    """Given an HTML export, import preserves folders and skips duplicate URLs."""
    export = tmp_path / "bookmarks.html"
    export.write_text(
        """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p>
  <DT><H3>Tools</H3>
  <DL><p>
    <DT><A HREF="https://example.com">Example</A>
    <DT><A HREF="javascript:void(0)">Reader</A>
    <DT><A HREF="ftp://example.com">Invalid</A>
  </DL><p>
</DL><p>
""",
        encoding="utf-8",
    )

    parsed = read_html_export(export)
    first = import_html_export(repository, export)
    second = import_html_export(repository, export)

    assert parsed.discovered == 3
    assert [bookmark.folder for bookmark in parsed.bookmarks] == ["Tools", "Tools"]
    assert parsed.bookmarks[1].tags == ["bookmarklet"]
    assert first.imported == 2
    assert first.warnings[0].code == "bookmark_invalid"
    assert second.imported == 0
    assert second.skipped == 2


@pytest.mark.parametrize(
    ("browser", "source"),
    [(Browser.FIREFOX, "firefox"), (Browser.ZEN, "zen")],
)
def test_read_firefox_bookmark(tmp_path: Path, browser: Browser, source: str) -> None:
    """Given a Firefox-family database, the importer keeps its browser source."""
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

    result = read_profile(browser, profile)

    assert len(result.bookmarks) == 1
    assert result.bookmarks[0].source == source
    assert result.bookmarks[0].title == "Example"
    assert result.bookmarks[0].folder == "Toolbar"


def test_read_zen_uses_a_stable_live_snapshot(tmp_path: Path) -> None:
    """Given a live Zen database, each import reads one stable committed snapshot."""
    profile = tmp_path / "places.sqlite"
    writer = sqlite3.connect(profile)
    try:
        writer.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA wal_autocheckpoint=0;
            CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT, title TEXT);
            CREATE TABLE moz_bookmarks (
                id INTEGER PRIMARY KEY, fk INTEGER, type INTEGER, title TEXT, parent INTEGER
            );
            INSERT INTO moz_bookmarks VALUES (10, NULL, 2, 'Toolbar', 0);
            INSERT INTO moz_places VALUES (1, 'https://one.example', 'One');
            INSERT INTO moz_bookmarks VALUES (11, 1, 1, NULL, 10);
            """
        )
        writer.commit()
        writer.executescript(
            """
            INSERT INTO moz_places VALUES (2, 'https://two.example', 'Two');
            INSERT INTO moz_bookmarks VALUES (12, 2, 1, NULL, 10);
            """
        )
        writer.commit()

        first = read_profile(Browser.ZEN, profile)

        writer.executescript(
            """
            INSERT INTO moz_places VALUES (3, 'https://three.example', 'Three');
            INSERT INTO moz_bookmarks VALUES (13, 3, 1, NULL, 10);
            """
        )
        writer.commit()
        second = read_profile(Browser.ZEN, profile)
    finally:
        writer.close()

    assert [bookmark.title for bookmark in first.bookmarks] == ["One", "Two"]
    assert [bookmark.title for bookmark in second.bookmarks] == ["One", "Two", "Three"]


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
    assert second.warnings[0].code == "bookmark_duplicate"
    assert "already exists" in second.warnings[0].message


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
