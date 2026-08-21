"""Bookmark export tests."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from link_hoarder.core.exporters import ExportExistsError, export_bookmarks
from link_hoarder.core.importers import read_html_export
from link_hoarder.core.models import BookmarkRead, BookmarkSource


def _bookmark(
    bookmark_id: int,
    *,
    folder: str | None,
    title: str,
    url: str,
) -> BookmarkRead:
    timestamp = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    return BookmarkRead(
        id=bookmark_id,
        created_at=timestamp,
        updated_at=timestamp,
        folder=folder,
        source=BookmarkSource.MANUAL,
        tags=["export"],
        title=title,
        url=url,
    )


def test_export_writes_html_and_json_subdirectories(tmp_path: Path) -> None:
    """Given bookmarks, export writes both formats and preserves nested folders."""
    bookmarks = [
        _bookmark(
            1,
            folder="Research/Reading",
            title="Example & guide",
            url="https://example.com/?a=1&b=2",
        ),
        _bookmark(
            2,
            folder="Tools",
            title="Reader",
            url="javascript:alert('hello')",
        ),
    ]

    result = export_bookmarks(bookmarks, tmp_path / "exports")
    parsed = read_html_export(result.html_path)
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))

    assert result.bookmarks == 2
    assert result.html_path == tmp_path / "exports/html/bookmarks.html"
    assert result.json_path == tmp_path / "exports/json/bookmarks.json"
    assert [bookmark.folder for bookmark in parsed.bookmarks] == [
        "Research/Reading",
        "Tools",
    ]
    assert [bookmark.url for bookmark in parsed.bookmarks] == [
        "https://example.com/?a=1&b=2",
        "javascript:alert('hello')",
    ]
    assert payload[0]["title"] == "Example & guide"
    assert payload[1]["tags"] == ["export"]


def test_export_refuses_existing_files_without_overwrite(tmp_path: Path) -> None:
    """Given an existing export, export requires explicit overwrite permission."""
    directory = tmp_path / "exports"
    export_bookmarks([], directory)

    with pytest.raises(ExportExistsError):
        export_bookmarks([], directory)

    result = export_bookmarks([], directory, overwrite=True)

    assert json.loads(result.json_path.read_text(encoding="utf-8")) == []
    assert "NETSCAPE-Bookmark-file-1" in result.html_path.read_text(encoding="utf-8")
