"""Shared test fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from link_hoarder.core.repository import BookmarkRepository


@pytest.fixture
def repository(tmp_path: Path) -> Iterator[BookmarkRepository]:
    """Provide an initialized isolated repository."""
    current = BookmarkRepository.from_path(tmp_path / "bookmarks.db")
    current.initialize()
    try:
        yield current
    finally:
        current.close()
