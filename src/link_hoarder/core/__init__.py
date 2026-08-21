"""Core bookmark behavior."""

from link_hoarder.core.models import BookmarkCreate, BookmarkRead, BookmarkUpdate
from link_hoarder.core.repository import BookmarkRepository

__all__ = ["BookmarkCreate", "BookmarkRead", "BookmarkRepository", "BookmarkUpdate"]
