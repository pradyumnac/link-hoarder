"""Bookmark repository tests."""

import pytest
from pydantic import ValidationError

from link_hoarder.core.models import BookmarkCreate, BookmarkUpdate
from link_hoarder.core.repository import BookmarkRepository


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


def test_repository_unknown_identifier(repository: BookmarkRepository) -> None:
    """Given an unknown identifier, update and delete return not-found values."""
    assert repository.update(999, BookmarkUpdate(title="Missing")) is None
    assert not repository.delete(999)


def test_bookmark_rejects_invalid_url() -> None:
    """Given a non-HTTP URL, bookmark validation rejects the input."""
    with pytest.raises(ValidationError):
        BookmarkCreate(url="not-a-url", title="Invalid")
