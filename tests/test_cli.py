"""CLI integration tests."""

import importlib
import json
from pathlib import Path

import pytest
from pydantic import HttpUrl, SecretStr
from typer.testing import CliRunner

from link_hoarder.cli.app import app
from link_hoarder.core.config import SavedCliConfig
from link_hoarder.core.models import ImportResult
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
    listed = runner.invoke(app, ["list", "--json"])

    assert created.exit_code == 0
    assert "Created bookmark 1" in created.stderr
    assert "DEBUG" not in created.stderr
    assert listed.exit_code == 0
    assert json.loads(created.stdout)["title"] == "Example"
    assert json.loads(listed.stdout)[0]["tags"] == ["docs"]


def test_cli_create_and_delete_are_safely_repeatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given repeated create and delete actions, matching state returns success."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))
    create_args = ["create", "https://example.com", "--title", "Example"]

    first_create = runner.invoke(app, create_args)
    second_create = runner.invoke(app, create_args)
    conflicting_create = runner.invoke(
        app,
        ["create", "https://example.com", "--title", "Different"],
    )
    first_delete = runner.invoke(app, ["delete", "1"])
    second_delete = runner.invoke(app, ["delete", "1"])

    assert first_create.exit_code == 0
    assert second_create.exit_code == 0
    assert json.loads(second_create.stdout)["id"] == 1
    assert "already exists; no changes" in second_create.stderr
    assert conflicting_create.exit_code == 1
    assert "different metadata" in conflicting_create.stderr
    assert first_delete.exit_code == 0
    assert second_delete.exit_code == 0
    assert "already absent" in second_delete.stdout


def test_cli_list_and_get_use_text_by_default_and_json_on_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given one bookmark, list and get switch between readable text and JSON."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))
    runner.invoke(
        app,
        [
            "create",
            "https://example.com",
            "--title",
            "Example",
            "--folder",
            "Research",
            "--tag",
            "docs",
        ],
    )

    listed_text = runner.invoke(app, ["list"])
    fetched_text = runner.invoke(app, ["get", "1"])
    listed_json = runner.invoke(app, ["list", "--json"])
    fetched_json = runner.invoke(app, ["get", "1", "--json"])

    assert listed_text.exit_code == 0
    assert "[1] Example" in listed_text.stdout
    assert "Folder: Research" in listed_text.stdout
    assert "Tags: docs" in listed_text.stdout
    assert fetched_text.stdout == listed_text.stdout
    assert json.loads(listed_json.stdout)[0]["title"] == "Example"
    assert json.loads(fetched_json.stdout)["title"] == "Example"


def test_cli_empty_list_supports_text_and_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given no bookmarks, list reports an empty text or JSON result."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))

    text_result = runner.invoke(app, ["list"])
    json_result = runner.invoke(app, ["list", "--json"])

    assert text_result.stdout == "No bookmarks found.\n"
    assert json.loads(json_result.stdout) == []


def test_cli_debug_writes_checkpoints_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given global debug mode, checkpoints use stderr and do not change stdout."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))

    result = runner.invoke(
        app,
        [
            "--debug",
            "--backend",
            "local",
            "create",
            "https://example.com",
            "--title",
            "Example",
        ],
    )

    assert result.exit_code == 0
    assert "DEBUG checkpoint=backend_selected backend=local" in result.stderr
    assert "DEBUG checkpoint=create_complete bookmark_id=1" in result.stderr
    assert "DEBUG" not in result.stdout
    assert json.loads(result.stdout)["title"] == "Example"


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
    assert "Import complete:" in imported.stderr
    assert json.loads(updated.stdout)["title"] == "Updated"
    assert deleted.exit_code == 0


def test_cli_lists_brave_and_zen_import_choices() -> None:
    """Given import help, the CLI lists Brave and Zen as browser choices."""
    result = runner.invoke(app, ["import-browser", "--help"])

    assert result.exit_code == 0
    assert "brave" in result.stdout
    assert "zen" in result.stdout


def test_cli_export_prompts_and_saves_the_selected_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given interactive export, the CLI prompts and saves both output formats."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setattr(cli_module, "load_cli_config", SavedCliConfig)
    saved: list[SavedCliConfig] = []

    def save_config(config: SavedCliConfig) -> Path:
        saved.append(config)
        return tmp_path / "config.json"

    monkeypatch.setattr(cli_module, "save_cli_config", save_config)
    created = runner.invoke(
        app,
        ["--backend", "local", "create", "https://example.com", "--title", "Example"],
    )
    directory = tmp_path / "exports"

    result = runner.invoke(
        app,
        ["--backend", "local", "export"],
        input=f"{directory}\n",
    )

    assert created.exit_code == 0
    assert result.exit_code == 0
    assert "Exported 1 bookmark" in result.stderr
    assert (directory / "html/bookmarks.html").is_file()
    assert (directory / "json/bookmarks.json").is_file()
    assert saved[-1].export_directory == directory.resolve()


def test_cli_export_uses_saved_default_and_confirms_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a saved directory, interactive export suggests it and confirms overwrite."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))
    directory = tmp_path / "exports"
    saved_config = SavedCliConfig(export_directory=directory)
    monkeypatch.setattr(cli_module, "load_cli_config", lambda: saved_config)
    monkeypatch.setattr(
        cli_module,
        "save_cli_config",
        lambda config: tmp_path / "config.json",
    )

    first = runner.invoke(
        app,
        ["--backend", "local", "export"],
        input="\n",
    )
    declined = runner.invoke(
        app,
        ["--backend", "local", "export"],
        input="\nn\n",
    )
    forced = runner.invoke(
        app,
        ["--backend", "local", "export", str(directory), "--no-interactive", "--force"],
    )

    assert first.exit_code == 0
    assert str(directory) in first.stdout
    assert declined.exit_code == 1
    assert "Overwrite" in declined.stdout
    assert "Export cancelled" in declined.stdout
    assert forced.exit_code == 0


def test_cli_export_requires_a_noninteractive_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given no saved directory, non-interactive export reports a stable error."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setattr(cli_module, "load_cli_config", SavedCliConfig)

    result = runner.invoke(
        app,
        ["--backend", "local", "export", "--no-interactive"],
    )

    assert result.exit_code == 2
    assert "export directory" in result.stderr.lower()


def test_cli_import_gracefully_reports_no_discovered_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given no discovered profiles, import returns success with clear feedback."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setattr(
        cli_module,
        "import_profiles",
        lambda backend, browser, profile: ImportResult(
            browser=browser,
            profiles=0,
            discovered=0,
            imported=0,
            skipped=0,
        ),
    )

    result = runner.invoke(app, ["--backend", "local", "import-browser", "brave"])

    assert result.exit_code == 0
    assert "No browser profiles were found" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_export_gracefully_reports_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given an export write failure, the CLI uses the invalid-operation exit state."""
    monkeypatch.setenv("LINK_HOARDER_DATABASE_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setattr(cli_module, "load_cli_config", SavedCliConfig)

    def fail_export(bookmarks: object, directory: Path, *, overwrite: bool) -> object:
        raise PermissionError("read-only destination")

    monkeypatch.setattr(cli_module, "export_bookmarks", fail_export)

    result = runner.invoke(
        app,
        ["--backend", "local", "export", str(tmp_path / "exports")],
        input="\n",
    )

    assert result.exit_code == 2
    assert "Export failed: read-only destination" in result.stderr
    assert "Traceback" not in result.stderr


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
    listed = runner.invoke(app, ["--backend", "api", "list", "--json"])

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
