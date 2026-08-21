"""Interactive user setup tests."""

import subprocess
from pathlib import Path

import pytest
from pydantic import SecretStr

from link_hoarder.cli.setup_user import (
    install_wrapper_scripts,
    provision_local_api,
    wrapper_scripts,
)
from link_hoarder.core.config import CliConfigError


def test_wrapper_scripts_use_short_safe_names(tmp_path: Path) -> None:
    """Given a project path, wrapper names start with li and contain no hyphens."""
    scripts = wrapper_scripts(tmp_path / "project", tmp_path / "link-hoarder")

    assert set(scripts) == {
        "li",
        "lilocal",
        "liapi",
        "liserverstart",
        "liserverstop",
        "liserverstatus",
    }
    assert all(name.startswith("li") and "-" not in name for name in scripts)
    assert "--backend local" in scripts["lilocal"]
    assert "--backend api" in scripts["liapi"]


def test_install_wrapper_scripts_sets_private_executable_mode(tmp_path: Path) -> None:
    """Given a target directory, setup installs each wrapper as a user executable."""
    target = tmp_path / "scripts"

    installed = install_wrapper_scripts(
        tmp_path / "project",
        tmp_path / "link-hoarder",
        target,
    )

    assert len(installed) == 6
    assert all(path.stat().st_mode & 0o777 == 0o700 for path in installed)
    assert (target / "li").read_text(encoding="utf-8").startswith("#!/bin/sh\n")


def test_provision_local_api_starts_compose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given local API setup, provisioning writes secrets and starts Docker Compose."""
    project = tmp_path / "project"
    (project / "stack").mkdir(parents=True)
    (project / "stack" / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    commands: list[list[str]] = []

    def run_command(
        command: list[str], *, check: bool
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("link_hoarder.cli.setup_user.subprocess.run", run_command)

    provision_local_api(project, SecretStr("a" * 32), 8080)

    environment = project / "stack" / ".env"
    assert environment.stat().st_mode & 0o777 == 0o600
    assert "LINK_HOARDER_API_KEY=" + "a" * 32 in environment.read_text()
    assert commands[0][:2] == ["docker", "compose"]
    assert commands[0][-3:] == ["up", "--build", "-d"]


def test_provision_local_api_reports_compose_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a Docker failure, provisioning reports one configuration error."""
    project = tmp_path / "project"
    (project / "stack").mkdir(parents=True)
    (project / "stack" / "compose.yaml").write_text("services: {}\n", encoding="utf-8")

    def run_command(
        command: list[str], *, check: bool
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr("link_hoarder.cli.setup_user.subprocess.run", run_command)

    with pytest.raises(CliConfigError, match="could not start"):
        provision_local_api(project, SecretStr("a" * 32), 8080)
