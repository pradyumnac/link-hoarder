"""FastAPI integration tests."""

from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from link_hoarder.api.app import create_app
from link_hoarder.core.config import Settings


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=tmp_path / "api.db",
        api_key=SecretStr("test-key"),
    )
    return TestClient(create_app(settings))


def test_api_requires_key(tmp_path: Path) -> None:
    """Given no API key header, the API rejects the request."""
    response = _client(tmp_path).get("/health")

    assert response.status_code == 401


def test_api_crud(tmp_path: Path) -> None:
    """Given a valid API key, API CRUD operations share stored data."""
    client = _client(tmp_path)
    headers = {"X-API-Key": "test-key"}

    created = client.post(
        "/bookmarks",
        headers=headers,
        json={"url": "https://example.com", "title": "Example"},
    )
    bookmark_id = created.json()["id"]
    updated = client.patch(
        f"/bookmarks/{bookmark_id}",
        headers=headers,
        json={"title": "Updated"},
    )
    listed = client.get("/bookmarks", headers=headers)
    deleted = client.delete(f"/bookmarks/{bookmark_id}", headers=headers)

    assert created.status_code == 201
    assert updated.json()["title"] == "Updated"
    assert len(listed.json()) == 1
    assert deleted.status_code == 204


def test_api_import_rejects_missing_profile(tmp_path: Path) -> None:
    """Given a missing profile file, the API returns a validation response."""
    response = _client(tmp_path).post(
        "/imports/browser",
        headers={"X-API-Key": "test-key"},
        json={"browser": "firefox", "profile": str(tmp_path / "missing.sqlite")},
    )

    assert response.status_code == 422
