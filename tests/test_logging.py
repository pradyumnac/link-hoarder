"""Structured logging tests."""

import json

import pytest
import structlog

from link_hoarder.core.logging import configure_logging


def test_structured_logs_write_json_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Given one application event, logging writes structured JSON to stdout."""
    configure_logging("INFO")

    structlog.get_logger("test").info("test_event", bookmark_id=7)

    payload = json.loads(capsys.readouterr().out)
    assert payload["event"] == "test_event"
    assert payload["bookmark_id"] == 7
    assert payload["level"] == "info"
