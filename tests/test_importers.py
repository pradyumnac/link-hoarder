"""Native browser importer tests."""

import json
import sqlite3
from pathlib import Path

import pytest

from link_hoarder.core.importers import discover_profiles, import_profiles, read_profile
from link_hoarder.core.models import Browser
from link_hoarder.core.repository import BookmarkRepository


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

    bookmarks = read_profile(Browser.CHROME, profile)

    assert len(bookmarks) == 1
    assert bookmarks[0].folder == "Bookmarks bar/Python"
    assert bookmarks[0].url == "https://python.org/"


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

    bookmarks = read_profile(Browser.FIREFOX, profile)

    assert len(bookmarks) == 1
    assert bookmarks[0].title == "Example"
    assert bookmarks[0].folder == "Toolbar"


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
