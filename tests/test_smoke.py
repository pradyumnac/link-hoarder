"""Package smoke test."""

import link_hoarder


def test_package_version() -> None:
    """Given an installed package, the public version is available."""
    assert link_hoarder.__version__ == "0.1.0"
