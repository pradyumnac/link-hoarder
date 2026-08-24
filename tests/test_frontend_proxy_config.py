"""Tests for the frontend reverse-proxy configuration template."""

import re
from pathlib import Path

_TEMPLATE = Path(__file__).resolve().parents[1] / "frontend" / "nginx.conf.template"


def _template() -> str:
    return _TEMPLATE.read_text(encoding="utf-8")


def test_asset_routes_use_a_separate_rate_limit_zone() -> None:
    """Given a collection page render, assets do not share the general API budget."""
    content = _template()

    assert "zone=link_hoarder_assets" in content
    assert re.search(
        r"location\s+~\s+\^/api/v1/bookmarks/\[0-9\]\+/\(favicon\|thumbnail\)\$",
        content,
    )


def test_asset_rate_limit_covers_one_full_collection_page() -> None:
    """Given the largest page of 100 bookmarks, the asset burst does not reject icons."""
    content = _template()
    zone = re.search(
        r"limit_req_zone[^;]*zone=link_hoarder_assets:\d+m\s+rate=(\d+)r/s", content
    )
    burst = re.search(r"limit_req\s+zone=link_hoarder_assets\s+burst=(\d+)", content)

    assert zone is not None
    assert burst is not None
    assert int(zone.group(1)) >= 100
    assert int(burst.group(1)) >= 100


def test_general_api_keeps_its_own_stricter_limit() -> None:
    """Given non-asset API calls, the original stricter budget still applies."""
    content = _template()

    assert (
        "limit_req_zone $binary_remote_addr zone=link_hoarder_api:10m rate=10r/s"
        in content
    )
    assert "limit_req zone=link_hoarder_api burst=20 nodelay" in content
