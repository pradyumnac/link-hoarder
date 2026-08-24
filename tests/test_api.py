"""FastAPI integration tests."""

import time
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr, ValidationError

from link_hoarder.api.app import create_app
from link_hoarder.api.openapi import contract_json
from link_hoarder.core.config import Settings
from link_hoarder.core.metadata import FetchedMetadata
from link_hoarder.core.repository import BookmarkRepository

_API_PREFIX = "/api/v1"
_API_KEY_VALUE = "test-key-value-with-at-least-32-characters"
_HEADERS = {"X-API-Key": _API_KEY_VALUE}


class StaticMetadataFetcher:
    """Return one deterministic image without outbound network access."""

    def __init__(self) -> None:
        image = Image.new("RGB", (20, 10), "#245c4a")
        output = BytesIO()
        image.save(output, format="PNG")
        self._content = output.getvalue()

    def fetch(self, url: str) -> FetchedMetadata:
        """Return the local fixture as a favicon and thumbnail."""
        del url
        return FetchedMetadata(favicon=self._content, thumbnail=self._content)


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=tmp_path / "api.db",
        metadata_cache_path=tmp_path / "metadata-cache",
        metadata_refresh_enabled=False,
        api_key=SecretStr(_API_KEY_VALUE),
    )
    return TestClient(create_app(settings))


def test_openapi_contract_is_current() -> None:
    """Given the committed contract, generated OpenAPI output matches it."""
    assert Path("docs/openapi.json").read_text(encoding="utf-8") == contract_json()


def test_settings_reject_short_api_key() -> None:
    """Given a short API key, settings reject insecure authentication data."""
    with pytest.raises(ValidationError):
        Settings(api_key=SecretStr("short-key"))


def test_api_closes_repository_during_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given an application shutdown, the API closes its database engine."""
    closed = False
    original_close = BookmarkRepository.close

    def record_close(repository: BookmarkRepository) -> None:
        nonlocal closed
        closed = True
        original_close(repository)

    monkeypatch.setattr(BookmarkRepository, "close", record_close)

    with _client(tmp_path) as client:
        assert client.get("/health", headers=_HEADERS).status_code == 200

    assert closed


def test_api_requires_key(tmp_path: Path) -> None:
    """Given no API key header, the API rejects the request."""
    response = _client(tmp_path).get("/health")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "APIKey"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_api_hides_runtime_documentation(tmp_path: Path) -> None:
    """Given an authenticated request, runtime API schemas remain disabled."""
    client = _client(tmp_path)

    assert client.get("/docs", headers=_HEADERS).status_code == 404
    assert client.get("/openapi.json", headers=_HEADERS).status_code == 404


def test_api_crud(tmp_path: Path) -> None:
    """Given a valid API key, versioned CRUD operations share stored data."""
    client = _client(tmp_path)

    created = client.post(
        f"{_API_PREFIX}/bookmarks",
        headers=_HEADERS,
        json={"url": "https://example.com", "title": "Example"},
    )
    bookmark_id = created.json()["id"]
    updated = client.patch(
        f"{_API_PREFIX}/bookmarks/{bookmark_id}",
        headers=_HEADERS,
        json={"title": "Updated"},
    )
    listed = client.get(f"{_API_PREFIX}/bookmarks", headers=_HEADERS)
    deleted = client.delete(f"{_API_PREFIX}/bookmarks/{bookmark_id}", headers=_HEADERS)

    assert created.status_code == 201
    assert updated.json()["title"] == "Updated"
    assert listed.json() == {
        "items": [
            {
                **updated.json(),
                "favicon_url": f"{_API_PREFIX}/bookmarks/{bookmark_id}/favicon",
                "thumbnail_url": None,
            }
        ],
        "total": 1,
        "limit": 100,
        "offset": 0,
    }
    assert deleted.status_code == 204


def test_api_serves_only_local_presentation_assets(tmp_path: Path) -> None:
    """Given fetched metadata, the API serves sanitized images from same-origin routes."""
    settings = Settings(
        database_path=tmp_path / "metadata.db",
        metadata_cache_path=tmp_path / "metadata-cache",
        metadata_refresh_enabled=True,
        api_key=SecretStr(_API_KEY_VALUE),
    )
    with TestClient(create_app(settings, StaticMetadataFetcher())) as client:
        client.post(
            f"{_API_PREFIX}/bookmarks",
            headers=_HEADERS,
            json={"url": "https://example.com/path", "title": "Example"},
        )
        deadline = time.monotonic() + 2
        listed = client.get(f"{_API_PREFIX}/bookmarks", headers=_HEADERS)
        while listed.json()["items"][0]["thumbnail_url"] is None:
            if time.monotonic() >= deadline:
                pytest.fail("Metadata refresh did not finish.")
            time.sleep(0.01)
            listed = client.get(f"{_API_PREFIX}/bookmarks", headers=_HEADERS)

        item = listed.json()["items"][0]
        favicon = client.get(item["favicon_url"], headers=_HEADERS)
        thumbnail = client.get(item["thumbnail_url"], headers=_HEADERS)

    assert item["favicon_url"].startswith(f"{_API_PREFIX}/")
    assert item["thumbnail_url"].startswith(f"{_API_PREFIX}/")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"] == "image/png"
    assert thumbnail.status_code == 200
    assert thumbnail.headers["content-type"] == "image/png"


def test_api_uses_a_generated_icon_without_cached_metadata(tmp_path: Path) -> None:
    """Given no cached favicon, the API serves a local generated domain icon."""
    client = _client(tmp_path)
    created = client.post(
        f"{_API_PREFIX}/bookmarks",
        headers=_HEADERS,
        json={"url": "https://example.com", "title": "Example"},
    )

    response = client.get(
        f"{_API_PREFIX}/bookmarks/{created.json()['id']}/favicon",
        headers=_HEADERS,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert b">E</text>" in response.content


def test_api_paginates_filtered_bookmarks(tmp_path: Path) -> None:
    """Given matching bookmarks, list returns page metadata and a bounded page."""
    client = _client(tmp_path)
    for number in range(3):
        client.post(
            f"{_API_PREFIX}/bookmarks",
            headers=_HEADERS,
            json={
                "url": f"https://example.com/{number}",
                "title": f"Match {number}",
            },
        )

    response = client.get(
        f"{_API_PREFIX}/bookmarks",
        headers=_HEADERS,
        params={"query": "Match", "limit": 1, "offset": 1},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 1
    assert len(response.json()["items"]) == 1


def test_api_rejects_duplicate_normalized_url(tmp_path: Path) -> None:
    """Given an existing normalized URL, create and update return HTTP 409."""
    client = _client(tmp_path)
    first = client.post(
        f"{_API_PREFIX}/bookmarks",
        headers=_HEADERS,
        json={"url": "https://example.com", "title": "First"},
    )
    second = client.post(
        f"{_API_PREFIX}/bookmarks",
        headers=_HEADERS,
        json={"url": "https://example.com/", "title": "Second"},
    )
    other = client.post(
        f"{_API_PREFIX}/bookmarks",
        headers=_HEADERS,
        json={"url": "https://other.example", "title": "Other"},
    )
    updated = client.patch(
        f"{_API_PREFIX}/bookmarks/{other.json()['id']}",
        headers=_HEADERS,
        json={"url": first.json()["url"]},
    )

    assert second.status_code == 409
    assert "https://example.com" not in second.text
    assert updated.status_code == 409


def test_api_creates_javascript_bookmarklet(tmp_path: Path) -> None:
    """Given a JavaScript URL, the API stores it without executing it."""
    response = _client(tmp_path).post(
        f"{_API_PREFIX}/bookmarks",
        headers=_HEADERS,
        json={"url": "javascript:alert('hello')", "title": "Bookmarklet"},
    )

    assert response.status_code == 201
    assert response.json()["url"] == "javascript:alert('hello')"
    assert response.json()["tags"] == ["bookmarklet"]


def test_api_imports_uploaded_bookmark_html(tmp_path: Path) -> None:
    """Given an uploaded HTML export, the API imports its valid bookmarks."""
    export = b"""<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p><DT><A HREF="https://example.com">Example</A></DL><p>
"""

    response = _client(tmp_path).post(
        f"{_API_PREFIX}/imports/bookmarks-file",
        headers={**_HEADERS, "Content-Type": "text/html"},
        content=export,
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert response.json()["format"] == "netscape_html"


def test_api_warns_for_invalid_uploaded_export(tmp_path: Path) -> None:
    """Given an invalid HTML export, the API returns a structured warning."""
    response = _client(tmp_path).post(
        f"{_API_PREFIX}/imports/bookmarks-file",
        headers={**_HEADERS, "Content-Type": "text/html"},
        content=b"not-bookmark-html",
    )

    assert response.status_code == 200
    assert response.json()["warnings"][0]["code"] == "profile_invalid"
    assert response.json()["warnings"][0]["profile"] == "bookmarks.html"
    assert str(tmp_path) not in response.text


def test_api_rejects_native_profile_imports(tmp_path: Path) -> None:
    """Given a native profile request, the web API does not expose that route."""
    client = _client(tmp_path)
    path_import = client.post(
        f"{_API_PREFIX}/imports/browser",
        headers=_HEADERS,
        json={"browser": "firefox", "profile": "/etc/passwd"},
    )
    file_import = client.post(
        f"{_API_PREFIX}/imports/browser-file",
        headers={**_HEADERS, "Content-Type": "application/octet-stream"},
        content=b"profile",
    )

    assert path_import.status_code == 404
    assert file_import.status_code == 404


def test_api_rejects_oversized_profile(tmp_path: Path) -> None:
    """Given an export over 16 MiB, the API rejects the request body."""
    response = _client(tmp_path).post(
        f"{_API_PREFIX}/imports/bookmarks-file",
        headers={**_HEADERS, "Content-Type": "text/html"},
        content=b"x" * (16 * 1024 * 1024 + 1),
    )

    assert response.status_code == 422


def test_api_does_not_echo_invalid_input(tmp_path: Path) -> None:
    """Given invalid secret input, validation omits the rejected value."""
    response = _client(tmp_path).post(
        f"{_API_PREFIX}/bookmarks",
        headers=_HEADERS,
        json={"url": "sensitive-invalid-value", "title": "Invalid"},
    )

    assert response.status_code == 422
    assert "sensitive-invalid-value" not in response.text


# Test plan: api-metadata-query-load
#   primary: a page of bookmarks issues the same bounded number of metadata
#     queries regardless of how many bookmarks are on the page.
#   alternate: covered by existing CRUD and presentation tests, which already
#     assert the response shape (favicon_url/thumbnail_url) is unchanged.


def test_api_list_bookmarks_metadata_query_count_does_not_grow_with_page_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given pages of different sizes, list_bookmarks issues a bounded query count."""
    client = _client(tmp_path)
    for number in range(50):
        client.post(
            f"{_API_PREFIX}/bookmarks",
            headers=_HEADERS,
            json={"url": f"https://example.com/{number}", "title": f"Match {number}"},
        )

    calls: list[int] = []
    original_list_metadata = BookmarkRepository.list_metadata
    original_get_metadata = BookmarkRepository.get_metadata

    def counted_list_metadata(self: BookmarkRepository, bookmark_ids: object) -> object:
        calls.append(1)
        return original_list_metadata(self, bookmark_ids)  # type: ignore[arg-type]

    def counted_get_metadata(self: BookmarkRepository, bookmark_id: int) -> object:
        calls.append(1)
        return original_get_metadata(self, bookmark_id)

    monkeypatch.setattr(BookmarkRepository, "list_metadata", counted_list_metadata)
    monkeypatch.setattr(BookmarkRepository, "get_metadata", counted_get_metadata)

    calls.clear()
    small = client.get(
        f"{_API_PREFIX}/bookmarks", headers=_HEADERS, params={"limit": 1}
    )
    small_calls = len(calls)

    calls.clear()
    large = client.get(
        f"{_API_PREFIX}/bookmarks", headers=_HEADERS, params={"limit": 50}
    )
    large_calls = len(calls)

    assert small.status_code == 200
    assert large.status_code == 200
    assert len(small.json()["items"]) == 1
    assert len(large.json()["items"]) == 50
    assert small_calls == large_calls
