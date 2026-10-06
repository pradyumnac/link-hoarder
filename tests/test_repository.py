"""Bookmark repository tests.

Test plan
=========

core-metadata-backfill.sweep (bookmarks needing metadata):
- primary: a bookmark with no metadata row and one with an elapsed
  `retry_after` are both returned; a bookmark with fresh metadata is not.
- edge: `limit` bounds the number of rows returned even when more
  bookmarks need metadata.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkMetadataRecord,
    BookmarkSort,
    BookmarkUpdate,
    MetadataStatus,
)
from link_hoarder.core.repository import BookmarkRepository, DuplicateBookmarkError


def test_repository_crud(repository: BookmarkRepository) -> None:
    """Given one bookmark, CRUD operations preserve each validated field."""
    created = repository.create(
        BookmarkCreate(url="https://example.com", title="Example", tags=["docs"])
    )

    assert repository.get(created.id) == created
    assert repository.find_by_url("https://example.com/") == created
    assert repository.list(query="Exam") == [created]

    updated = repository.update(created.id, BookmarkUpdate(title="Updated"))
    assert updated is not None
    assert updated.title == "Updated"
    assert repository.delete(created.id)
    assert repository.get(created.id) is None


def test_repository_repeated_update_preserves_timestamp(
    repository: BookmarkRepository,
) -> None:
    """Given an unchanged update, the repository returns the existing state."""
    created = repository.create(
        BookmarkCreate(url="https://example.com", title="Example")
    )

    updated = repository.update(created.id, BookmarkUpdate(title="Example"))

    assert updated == created


def test_repository_unknown_identifier(repository: BookmarkRepository) -> None:
    """Given an unknown identifier, update and delete return not-found values."""
    assert repository.update(999, BookmarkUpdate(title="Missing")) is None
    assert not repository.delete(999)


def test_bookmark_tags_javascript_url() -> None:
    """Given a JavaScript bookmarklet, validation adds its identifying tag once."""
    bookmark = BookmarkCreate(
        url="javascript:alert('hello')",
        title="Bookmarklet",
        tags=["tools", "bookmarklet"],
    )

    assert bookmark.url == "javascript:alert('hello')"
    assert bookmark.tags == ["tools", "bookmarklet"]
    uppercase = BookmarkCreate(url="JAVASCRIPT:void(0)", title="Uppercase")
    assert uppercase.url == "javascript:void(0)"
    assert uppercase.tags == ["bookmarklet"]
    assert BookmarkUpdate(url="JAVASCRIPT:void(0)").url == "javascript:void(0)"


def test_repository_rejects_duplicate_url(repository: BookmarkRepository) -> None:
    """Given a normalized URL conflict, create and update preserve unique URLs."""
    first = repository.create(BookmarkCreate(url="https://example.com", title="First"))
    second = repository.create(
        BookmarkCreate(url="https://other.example", title="Second")
    )

    with pytest.raises(DuplicateBookmarkError):
        repository.create(BookmarkCreate(url="https://example.com/", title="Duplicate"))
    with pytest.raises(DuplicateBookmarkError):
        repository.update(second.id, BookmarkUpdate(url=first.url))

    assert repository.count() == 2
    assert repository.get(second.id) == second


def test_repository_searches_tags(repository: BookmarkRepository) -> None:
    """Given a tagged bookmark, a list query finds its tag."""
    created = repository.create(
        BookmarkCreate(url="javascript:alert('hello')", title="Bookmarklet")
    )

    assert repository.list(query="bookmarklet") == [created]


def test_bookmark_rejects_invalid_url() -> None:
    """Given a non-URL string, bookmark validation rejects the input."""
    with pytest.raises(ValidationError):
        BookmarkCreate(url="not-a-url", title="Invalid")


def test_repository_create_preserves_explicit_created_at(
    repository: BookmarkRepository,
) -> None:
    """Given an explicit save time, create stores it instead of the import time."""
    saved = datetime(2015, 6, 30, 12, 0, tzinfo=UTC)

    created = repository.create(
        BookmarkCreate(url="https://example.com", title="Example", created_at=saved)
    )

    # SQLite drops the UTC offset on write, so stored times read back naive.
    assert created.created_at == saved.replace(tzinfo=None)
    assert created.updated_at == saved.replace(tzinfo=None)


def test_repository_create_defaults_created_at_to_now(
    repository: BookmarkRepository,
) -> None:
    """Given no save time, create stamps the bookmark with the current time."""
    before = datetime.now(UTC).replace(tzinfo=None)

    created = repository.create(
        BookmarkCreate(url="https://example.com", title="Example")
    )

    assert created.created_at is not None
    assert before <= created.created_at <= datetime.now(UTC).replace(tzinfo=None)


def test_repository_list_sorts_by_save_time(repository: BookmarkRepository) -> None:
    """Given newest and oldest sorts, list orders by original save time."""
    repository.create(
        BookmarkCreate(
            url="https://old.example",
            title="Old",
            created_at=datetime(2015, 6, 30, tzinfo=UTC),
        )
    )
    repository.create(
        BookmarkCreate(
            url="https://new.example",
            title="New",
            created_at=datetime(2020, 1, 15, tzinfo=UTC),
        )
    )
    repository.create(
        BookmarkCreate(
            url="https://middle.example",
            title="Middle",
            created_at=datetime(2018, 3, 10, tzinfo=UTC),
        )
    )

    assert [item.title for item in repository.list()] == ["Old", "New", "Middle"]
    assert [item.title for item in repository.list(sort=BookmarkSort.NEWEST)] == [
        "New",
        "Middle",
        "Old",
    ]
    assert [item.title for item in repository.list(sort=BookmarkSort.OLDEST)] == [
        "Old",
        "Middle",
        "New",
    ]


def test_repository_list_sort_is_stable_for_equal_save_times(
    repository: BookmarkRepository,
) -> None:
    """Given equal save times, sorted lists keep identifier order."""
    saved = datetime(2019, 5, 1, tzinfo=UTC)
    repository.create(
        BookmarkCreate(url="https://a.example", title="A", created_at=saved)
    )
    repository.create(
        BookmarkCreate(url="https://b.example", title="B", created_at=saved)
    )

    assert [item.title for item in repository.list(sort=BookmarkSort.NEWEST)] == [
        "A",
        "B",
    ]
    assert [item.title for item in repository.list(sort=BookmarkSort.OLDEST)] == [
        "A",
        "B",
    ]


def test_repository_list_sort_combines_with_query_and_pagination(
    repository: BookmarkRepository,
) -> None:
    """Given a query and page window, sort applies before pagination."""
    for index in range(4):
        repository.create(
            BookmarkCreate(
                url=f"https://tool-{index}.example",
                title=f"Tool {index}",
                created_at=datetime(2020, 1, index + 1, tzinfo=UTC),
            )
        )

    page = repository.list(query="tool", limit=2, offset=1, sort=BookmarkSort.NEWEST)

    assert [item.title for item in page] == ["Tool 2", "Tool 1"]


def test_list_needing_metadata_finds_missing_and_stale_rows(
    repository: BookmarkRepository,
) -> None:
    """Given mixed metadata states, the query returns only bookmarks needing a refresh."""
    missing = repository.create(
        BookmarkCreate(url="https://missing.example/", title="Missing")
    )
    fresh = repository.create(
        BookmarkCreate(url="https://fresh.example/", title="Fresh")
    )
    stale = repository.create(
        BookmarkCreate(url="https://stale.example/", title="Stale")
    )
    incomplete = repository.create(
        BookmarkCreate(url="https://incomplete.example/", title="Incomplete")
    )
    now = datetime.now(UTC)
    repository.save_metadata(
        BookmarkMetadataRecord(
            bookmark_id=fresh.id,
            source_url=fresh.url,
            status=MetadataStatus.READY,
            refreshed_at=now,
            retry_after=now + timedelta(days=7),
            preview_title="Fresh Title",
            preview_text="Fresh article excerpt.",
        )
    )
    repository.save_metadata(
        BookmarkMetadataRecord(
            bookmark_id=stale.id,
            source_url=stale.url,
            status=MetadataStatus.FAILED,
            refreshed_at=now - timedelta(hours=2),
            retry_after=now - timedelta(hours=1),
        )
    )
    repository.save_metadata(
        BookmarkMetadataRecord(
            bookmark_id=incomplete.id,
            source_url=incomplete.url,
            status=MetadataStatus.READY,
            refreshed_at=now,
            retry_after=now + timedelta(days=7),
        )
    )

    needing = repository.list_needing_metadata(limit=10)

    ids = {bookmark.id for bookmark in needing}
    assert missing.id in ids
    assert stale.id in ids
    assert incomplete.id in ids
    assert fresh.id not in ids


def test_list_needing_metadata_respects_the_limit(
    repository: BookmarkRepository,
) -> None:
    """Given more missing-metadata bookmarks than the limit, only the limit is returned."""
    for index in range(5):
        repository.create(
            BookmarkCreate(url=f"https://example.com/{index}", title=f"B{index}")
        )

    needing = repository.list_needing_metadata(limit=2)

    assert len(needing) == 2


def test_repository_initialize_adds_preview_columns_to_existing_table(
    tmp_path: Path,
) -> None:
    """Given a metadata table from an older release, init adds preview columns."""
    import sqlite3

    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE bookmarks (id INTEGER PRIMARY KEY, url TEXT, title TEXT)"
    )
    connection.execute(
        "CREATE TABLE bookmark_metadata ("
        "bookmark_id INTEGER PRIMARY KEY, source_url TEXT, status TEXT, "
        "favicon_file TEXT, thumbnail_file TEXT, "
        "refreshed_at TEXT, retry_after TEXT)"
    )
    connection.commit()
    connection.close()
    repository = BookmarkRepository.from_path(path)

    repository.initialize()

    columns = {
        row[1]
        for row in sqlite3.connect(path).execute("PRAGMA table_info(bookmark_metadata)")
    }
    repository.close()

    assert {"preview_title", "preview_description", "preview_site"} <= columns
