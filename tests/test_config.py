"""Application configuration tests."""

from pathlib import Path

import pytest

from link_hoarder.core.config import Settings


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
