"""Bookmark repository tests."""

import pytest
from pydantic import ValidationError

from link_hoarder.core.models import BookmarkCreate, BookmarkUpdate
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
