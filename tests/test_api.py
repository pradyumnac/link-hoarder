"""FastAPI integration tests."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from link_hoarder.api.app import create_app
from link_hoarder.api.openapi import contract_json
from link_hoarder.core.config import Settings

_API_PREFIX = "/api/v1"
_HEADERS = {"X-API-Key": "test-key"}


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=tmp_path / "api.db",
        api_key=SecretStr("test-key"),
    )
    return TestClient(create_app(settings))


def test_openapi_contract_is_current() -> None:
    """Given the committed contract, generated OpenAPI output matches it."""
    assert Path("docs/openapi.json").read_text(encoding="utf-8") == contract_json()


def test_api_requires_key(tmp_path: Path) -> None:
    """Given no API key header, the API rejects the request."""
    response = _client(tmp_path).get("/health")

    assert response.status_code == 401


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
        "items": [updated.json()],
        "total": 1,
        "limit": 100,
        "offset": 0,
    }
    assert deleted.status_code == 204


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


def test_api_imports_uploaded_chromium_file(tmp_path: Path) -> None:
    """Given an uploaded Chromium file, the API imports its valid bookmarks."""
    profile = json.dumps(
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
    ).encode()

    response = _client(tmp_path).post(
        f"{_API_PREFIX}/imports/browser-file",
        headers={**_HEADERS, "Content-Type": "application/octet-stream"},
        params={"browser": "chrome"},
        content=profile,
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1


def test_api_warns_for_invalid_uploaded_profile(tmp_path: Path) -> None:
    """Given an invalid uploaded profile, the API returns a structured warning."""
    response = _client(tmp_path).post(
        f"{_API_PREFIX}/imports/browser-file",
        headers={**_HEADERS, "Content-Type": "application/octet-stream"},
        params={"browser": "chrome"},
        content=b"not-json",
    )

    assert response.status_code == 200
    assert response.json()["warnings"][0]["code"] == "profile_invalid"


def test_api_import_rejects_missing_profile(tmp_path: Path) -> None:
    """Given a missing profile file, the API returns a validation response."""
    response = _client(tmp_path).post(
        f"{_API_PREFIX}/imports/browser",
        headers=_HEADERS,
        json={"browser": "firefox", "profile": str(tmp_path / "missing.sqlite")},
    )

    assert response.status_code == 422
