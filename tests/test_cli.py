"""CLI integration tests."""

import importlib
import json
from pathlib import Path

import pytest
from pydantic import HttpUrl, SecretStr
from typer.testing import CliRunner

from link_hoarder.cli.app import app
from link_hoarder.core.repository import BookmarkRepository

cli_module = importlib.import_module("link_hoarder.cli.app")

runner = CliRunner()


def test_cli_crud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given an isolated database, CLI create and list commands share data."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))

    created = runner.invoke(
        app,
        ["create", "https://example.com", "--title", "Example", "--tag", "docs"],
    )
    listed = runner.invoke(app, ["list"])

    assert created.exit_code == 0
    assert listed.exit_code == 0
    assert json.loads(created.stdout)["title"] == "Example"
    assert json.loads(listed.stdout)[0]["tags"] == ["docs"]


def test_cli_creates_javascript_bookmarklet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a JavaScript URL, the CLI stores it without executing it."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))

    result = runner.invoke(
        app,
        ["create", "javascript:alert('hello')", "--title", "Bookmarklet"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["url"] == "javascript:alert('hello')"
    assert json.loads(result.stdout)["tags"] == ["bookmarklet"]


def test_cli_update_delete_and_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a browser profile, CLI import, update, and delete complete a workflow."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))
    profile = tmp_path / "Bookmarks"
    profile.write_text(
        json.dumps(
            {
                "roots": {
                    "other": {
                        "children": [
                            {
                                "name": "Imported",
                                "type": "url",
                                "url": "https://example.com",
                            },
                            {
                                "name": "Invalid",
                                "type": "url",
                                "url": "ftp://example.com",
                            },
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    imported = runner.invoke(
        app, ["import-browser", "chrome", "--profile", str(profile)]
    )
    updated = runner.invoke(app, ["update", "1", "--title", "Updated"])
    deleted = runner.invoke(app, ["delete", "1"])

    assert json.loads(imported.stdout)["imported"] == 1
    assert json.loads(imported.stdout)["warnings"][0]["code"] == "bookmark_invalid"
    assert "Warning [bookmark_invalid]" in imported.stderr
    assert json.loads(updated.stdout)["title"] == "Updated"
    assert deleted.exit_code == 0


def test_cli_lists_brave_and_zen_import_choices() -> None:
    """Given import help, the CLI lists Brave and Zen as browser choices."""
    result = runner.invoke(app, ["import-browser", "--help"])

    assert result.exit_code == 0
    assert "brave" in result.stdout
    assert "zen" in result.stdout


def test_cli_imports_bookmark_html_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a bookmark HTML export, the CLI imports it as an additional workflow."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))
    export = tmp_path / "bookmarks.html"
    export.write_text(
        """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p><DT><A HREF="https://example.com">Example</A></DL><p>
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["import-file", str(export)])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["format"] == "netscape_html"
    assert json.loads(result.stdout)["imported"] == 1


def test_cli_api_backend_crud_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given API mode, the same CLI commands complete a remote-style workflow."""
    repository = BookmarkRepository.from_path(tmp_path / "api.db")
    repository.initialize()
    monkeypatch.setenv("LINK_HOARDER_API_URL", "https://links.example")
    monkeypatch.setenv("LINK_HOARDER_API_KEY", "a" * 32)

    def api_backend(
        api_url: HttpUrl, api_key: SecretStr, timeout: float
    ) -> BookmarkRepository:
        del api_url, api_key, timeout
        return repository

    monkeypatch.setattr(cli_module, "ApiBookmarkBackend", api_backend)

    created = runner.invoke(
        app,
        [
            "--backend",
            "api",
            "create",
            "https://example.com",
            "--title",
            "Example",
        ],
    )
    listed = runner.invoke(app, ["--backend", "api", "list"])

    assert created.exit_code == 0
    assert listed.exit_code == 0
    assert json.loads(created.stdout)["title"] == "Example"
    assert json.loads(listed.stdout)[0]["url"] == "https://example.com/"


def test_cli_get_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given an unknown identifier, the CLI reports a not-found exit."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))

    result = runner.invoke(app, ["get", "999"])

    assert result.exit_code == 1
    assert "was not found" in result.stderr
