"""Application configuration tests."""

from pathlib import Path

import pytest
from pydantic import HttpUrl, SecretStr

from link_hoarder.core.config import (
    BackendKind,
    SavedCliConfig,
    Settings,
    load_cli_config,
    resolve_cli_config,
    save_cli_config,
)


def test_settings_do_not_read_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a local dotenv file, application settings use only the environment."""
    (tmp_path / ".env").write_text(
        "LINK_HOARDER_API_KEY=dotenv-key-with-at-least-32-characters\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LINK_HOARDER_API_KEY", raising=False)

    assert Settings().api_key is None


def test_cli_config_round_trip_uses_private_permissions(tmp_path: Path) -> None:
    """Given API settings, save and load preserve values with private permissions."""
    path = tmp_path / "config.json"
    expected = SavedCliConfig(
        backend=BackendKind.API,
        api_url=HttpUrl("https://links.example"),
        api_key=SecretStr("a" * 32),
        export_directory=tmp_path / "exports",
    )

    save_cli_config(expected, path)
    actual = load_cli_config(path)

    assert actual == expected
    assert path.stat().st_mode & 0o777 == 0o600


def test_cli_config_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given all configuration layers, the CLI option and environment take priority."""
    monkeypatch.setenv("LINK_HOARDER_BACKEND", "local")
    monkeypatch.setenv("LINK_HOARDER_API_URL", "https://environment.example")
    monkeypatch.setenv("LINK_HOARDER_API_KEY", "e" * 32)
    saved = SavedCliConfig(
        backend=BackendKind.API,
        api_url=HttpUrl("https://saved.example"),
        api_key=SecretStr("s" * 32),
    )

    result = resolve_cli_config(Settings(), BackendKind.API, saved)

    assert result.backend is BackendKind.API
    assert str(result.api_url) == "https://environment.example/"
    assert result.api_key is not None
    assert result.api_key.get_secret_value() == "e" * 32
