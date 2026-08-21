"""HTTP CLI backend tests."""

import io
import json
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import Message
from types import TracebackType
from typing import Self
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest
from pydantic import HttpUrl, SecretStr

from link_hoarder.cli import api_backend
from link_hoarder.cli.api_backend import ApiBookmarkBackend
from link_hoarder.core.backend import BookmarkBackendError, DuplicateBookmarkError
from link_hoarder.core.models import BookmarkCreate, BookmarkUpdate


class FakeResponse:
    """Provide the urlopen response context used by the backend."""

    def __init__(self, payload: object | None) -> None:
        self._content = b"" if payload is None else json.dumps(payload).encode()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback

    def read(self) -> bytes:
        return self._content


def _bookmark(bookmark_id: int = 1, title: str = "Example") -> dict[str, object]:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    return {
        "id": bookmark_id,
        "url": "https://example.com/",
        "title": title,
        "folder": None,
        "tags": [],
        "source": "manual",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _backend() -> ApiBookmarkBackend:
    return ApiBookmarkBackend(
        HttpUrl("https://links.example"),
        SecretStr("a" * 32),
        5.0,
    )


def test_api_backend_crud_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given valid API responses, the HTTP backend completes one CRUD workflow."""
    responses = iter(
        [
            FakeResponse(_bookmark()),
            FakeResponse(
                {"items": [_bookmark()], "total": 1, "limit": 100, "offset": 0}
            ),
            FakeResponse(_bookmark()),
            FakeResponse(_bookmark(title="Updated")),
            FakeResponse(None),
        ]
    )
    requests: list[Request] = []

    def open_response(request: Request, timeout: float) -> FakeResponse:
        assert timeout == 5.0
        requests.append(request)
        return next(responses)

    monkeypatch.setattr(api_backend, "urlopen", open_response)
    backend = _backend()

    created = backend.create(BookmarkCreate(url="https://example.com", title="Example"))
    listed = backend.list()
    fetched = backend.get(1)
    updated = backend.update(1, BookmarkUpdate(title="Updated"))
    deleted = backend.delete(1)

    assert created.id == 1
    assert listed == [created]
    assert fetched == created
    assert updated is not None and updated.title == "Updated"
    assert deleted is True
    assert [request.get_method() for request in requests] == [
        "POST",
        "GET",
        "GET",
        "PATCH",
        "DELETE",
    ]
    assert all(request.get_header("X-api-key") == "a" * 32 for request in requests)


def test_api_backend_encodes_url_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a URL with query data, the HTTP backend encodes the lookup parameter."""
    captured: list[str] = []

    def open_response(request: Request, timeout: float) -> FakeResponse:
        del timeout
        captured.append(request.full_url)
        return FakeResponse(_bookmark())

    monkeypatch.setattr(api_backend, "urlopen", open_response)

    result = _backend().find_by_url("https://example.com/?a=1&b=two")

    assert result is not None
    assert captured == [
        "https://links.example/api/v1/bookmarks/by-url?url=https%3A%2F%2Fexample.com%2F%3Fa%3D1%26b%3Dtwo"
    ]


@pytest.mark.parametrize(
    ("operation", "status_code", "expected"),
    [
        (lambda backend: backend.get(99), 404, None),
        (lambda backend: backend.delete(99), 404, False),
    ],
)
def test_api_backend_maps_not_found(
    monkeypatch: pytest.MonkeyPatch,
    operation: Callable[[ApiBookmarkBackend], object],
    status_code: int,
    expected: object,
) -> None:
    """Given an API not-found response, read and delete return local semantics."""

    def open_response(request: Request, timeout: float) -> FakeResponse:
        del request, timeout
        raise HTTPError(
            "https://links.example",
            status_code,
            "Not Found",
            Message(),
            io.BytesIO(b'{"detail":"missing"}'),
        )

    monkeypatch.setattr(api_backend, "urlopen", open_response)

    assert operation(_backend()) == expected


def test_api_backend_maps_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given an API conflict, create raises the shared duplicate error."""

    def open_response(request: Request, timeout: float) -> FakeResponse:
        del request, timeout
        raise HTTPError(
            "https://links.example",
            409,
            "Conflict",
            Message(),
            io.BytesIO(b'{"detail":"duplicate"}'),
        )

    monkeypatch.setattr(api_backend, "urlopen", open_response)

    with pytest.raises(DuplicateBookmarkError):
        _backend().create(BookmarkCreate(url="https://example.com", title="Example"))


def test_api_backend_reports_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given a network failure, the HTTP backend raises a stable backend error."""

    def open_response(request: Request, timeout: float) -> FakeResponse:
        del request, timeout
        raise URLError("connection refused")

    monkeypatch.setattr(api_backend, "urlopen", open_response)

    with pytest.raises(BookmarkBackendError, match="API is unavailable"):
        _backend().list()
