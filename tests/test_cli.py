"""CLI integration tests."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from link_hoarder.cli.app import app

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
                            }
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
    assert json.loads(updated.stdout)["title"] == "Updated"
    assert deleted.exit_code == 0


def test_cli_get_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given an unknown identifier, the CLI reports a not-found exit."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))

    result = runner.invoke(app, ["get", "999"])

    assert result.exit_code == 1
    assert "was not found" in result.stderr
