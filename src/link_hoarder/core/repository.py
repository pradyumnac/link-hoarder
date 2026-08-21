"""SQLite bookmark repository."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import String, cast, func
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, col, create_engine, select

from link_hoarder.core.backend import BookmarkStorageError, DuplicateBookmarkError
from link_hoarder.core.models import (
    BookmarkCreate,
    BookmarkRead,
    BookmarkRecord,
    BookmarkUpdate,
)

__all__ = ["BookmarkRepository", "BookmarkStorageError", "DuplicateBookmarkError"]


class BookmarkRepository:
    """Store bookmarks in SQLite."""

    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )

    @classmethod
    def from_path(cls, path: Path) -> BookmarkRepository:
        """Create a repository for a database path."""
        resolved = path.expanduser().resolve()
        return cls(f"sqlite:///{resolved.as_posix()}")

    def initialize(self) -> None:
        """Create the database directory and tables."""
        database = self._engine.url.database
        if database and database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        SQLModel.metadata.create_all(self._engine)
        with self._engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_bookmarks_url ON bookmarks (url)"
            )

    def close(self) -> None:
        """Release database engine resources."""
        self._engine.dispose()

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Provide one database session."""
        with Session(self._engine) as session:
            yield session

    def create(self, bookmark: BookmarkCreate) -> BookmarkRead:
        """Create one bookmark."""
        record = BookmarkRecord.model_validate(bookmark)
        with self.session() as session:
            session.add(record)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise DuplicateBookmarkError(bookmark.url) from error
            except SQLAlchemyError as error:
                session.rollback()
                raise BookmarkStorageError(
                    "The bookmark could not be stored."
                ) from error
            session.refresh(record)
            return self._read(record)

    def get(self, bookmark_id: int) -> BookmarkRead | None:
        """Get one bookmark by identifier."""
        with self.session() as session:
            record = session.get(BookmarkRecord, bookmark_id)
            return self._read(record) if record is not None else None

    def find_by_url(self, url: str) -> BookmarkRead | None:
        """Get the first bookmark with a URL."""
        with self.session() as session:
            result = session.exec(
                select(BookmarkRecord).where(BookmarkRecord.url == url)
            )
            try:
                record = result.first()
                return self._read(record) if record is not None else None
            finally:
                result.close()

    def list(
        self, *, query: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[BookmarkRead]:
        """List bookmarks, with an optional text query."""
        statement = (
            select(BookmarkRecord)
            .order_by(col(BookmarkRecord.id))
            .offset(offset)
            .limit(limit)
        )
        if query:
            statement = statement.where(
                col(BookmarkRecord.title).contains(query)
                | col(BookmarkRecord.url).contains(query)
                | cast(col(BookmarkRecord.tags), String).contains(query)
            )
        with self.session() as session:
            result = session.exec(statement)
            try:
                return [self._read(record) for record in result.all()]
            finally:
                result.close()

    def count(self, *, query: str | None = None) -> int:
        """Count bookmarks that match an optional text query."""
        statement = select(func.count(col(BookmarkRecord.id)))
        if query:
            statement = statement.where(
                col(BookmarkRecord.title).contains(query)
                | col(BookmarkRecord.url).contains(query)
                | cast(col(BookmarkRecord.tags), String).contains(query)
            )
        with self.session() as session:
            return session.exec(statement).one()

    def update(self, bookmark_id: int, update: BookmarkUpdate) -> BookmarkRead | None:
        """Update one bookmark."""
        with self.session() as session:
            record = session.get(BookmarkRecord, bookmark_id)
            if record is None:
                return None
            values = update.model_dump(exclude_unset=True)
            record.sqlmodel_update(values)
            record.updated_at = datetime.now(UTC)
            session.add(record)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                duplicate_url = update.url or record.url
                raise DuplicateBookmarkError(duplicate_url) from error
            except SQLAlchemyError as error:
                session.rollback()
                raise BookmarkStorageError(
                    "The bookmark could not be updated."
                ) from error
            session.refresh(record)
            return self._read(record)

    def delete(self, bookmark_id: int) -> bool:
        """Delete one bookmark."""
        with self.session() as session:
            record = session.get(BookmarkRecord, bookmark_id)
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True

    @staticmethod
    def _read(record: BookmarkRecord) -> BookmarkRead:
        return BookmarkRead.model_validate(record)
