"""Interactive user setup for CLI backends and wrapper scripts."""

import secrets
import shlex
import subprocess
from enum import StrEnum
from pathlib import Path

import typer
from pydantic import HttpUrl, SecretStr, ValidationError

from link_hoarder.core.config import (
    BackendKind,
    CliConfigError,
    SavedCliConfig,
    save_cli_config,
)


class SetupMode(StrEnum):
    """Interactive setup mode."""

    LOCAL = "local"
    LOCAL_API = "local-api"
    REMOTE_API = "remote-api"


def wrapper_scripts(project_root: Path, executable: Path) -> dict[str, str]:
    """Return wrapper script names and contents."""
    cli = shlex.quote(str(executable))
    compose = shlex.quote(str(project_root / "stack" / "compose.yaml"))
    environment = shlex.quote(str(project_root / "stack" / ".env"))
    compose_command = f"docker compose --env-file {environment} -f {compose}"
    return {
        "li": f'#!/bin/sh\nexec {cli} "$@"\n',
        "lilocal": f'#!/bin/sh\nexec {cli} --backend local "$@"\n',
        "liapi": f'#!/bin/sh\nexec {cli} --backend api "$@"\n',
        "liserverstart": (f"#!/bin/sh\nexec {compose_command} up --build -d\n"),
        "liserverstop": f"#!/bin/sh\nexec {compose_command} down\n",
        "liserverstatus": f"#!/bin/sh\nexec {compose_command} ps\n",
    }


def install_wrapper_scripts(
    project_root: Path,
    executable: Path,
    target: Path | None = None,
) -> list[Path]:
    """Install executable user wrapper scripts."""
    directory = target or Path.home() / ".local" / "scripts"
    directory.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    for name, content in wrapper_scripts(project_root, executable).items():
        path = directory / name
        path.write_text(content, encoding="utf-8", newline="\n")
        path.chmod(0o700)
        installed.append(path)
    return installed


def write_stack_environment(project_root: Path, api_key: SecretStr, port: int) -> Path:
    """Write the local Docker Compose environment file."""
    path = project_root / "stack" / ".env"
    path.write_text(
        "LINK_HOARDER_LOG_LEVEL=INFO\n"
        f"LINK_HOARDER_PORT={port}\n"
        f"LINK_HOARDER_API_KEY={api_key.get_secret_value()}\n",
        encoding="utf-8",
        newline="\n",
    )
    path.chmod(0o600)
    return path


def provision_local_api(project_root: Path, api_key: SecretStr, port: int) -> None:
    """Configure and start the local Docker Compose API stack."""
    compose = project_root / "stack" / "compose.yaml"
    if not compose.is_file():
        raise CliConfigError(f"The Docker Compose file was not found: {compose}")
    environment = write_stack_environment(project_root, api_key, port)
    try:
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(environment),
                "-f",
                str(compose),
                "up",
                "--build",
                "-d",
            ],
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise CliConfigError("Docker Compose could not start the local API.") from error


def _tool_executable() -> Path:
    try:
        result = subprocess.run(
            ["uv", "tool", "dir", "--bin"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise CliConfigError("The uv tool directory could not be found.") from error
    return Path(result.stdout.strip()) / "link-hoarder"


def _select_mode() -> SetupMode:
    typer.echo("Select the default CLI backend:")
    typer.echo("  1. Local SQLite")
    typer.echo("  2. Local Docker API")
    typer.echo("  3. Existing remote API")
    choice = typer.prompt("Selection", default="1")
    modes = {"1": SetupMode.LOCAL, "2": SetupMode.LOCAL_API, "3": SetupMode.REMOTE_API}
    try:
        return modes[choice.strip()]
    except KeyError as error:
        raise CliConfigError("Select 1, 2, or 3.") from error


def _remote_config() -> SavedCliConfig:
    api_url = typer.prompt("API server URL")
    api_key = typer.prompt("API key", hide_input=True)
    try:
        return SavedCliConfig(
            backend=BackendKind.API,
            api_url=HttpUrl(api_url),
            api_key=SecretStr(api_key),
        )
    except ValidationError as error:
        raise CliConfigError("The remote API configuration is invalid.") from error


def _local_api_config(project_root: Path) -> SavedCliConfig:
    port = typer.prompt("Local web port", default=8080, type=int)
    if not 1 <= port <= 65535:
        raise CliConfigError("The local web port must be between 1 and 65535.")
    api_key = SecretStr(secrets.token_urlsafe(48))
    provision_local_api(project_root, api_key, port)
    return SavedCliConfig(
        backend=BackendKind.API,
        api_url=HttpUrl(f"http://127.0.0.1:{port}"),
        api_key=api_key,
    )


def run_setup(project_root: Path) -> None:
    """Run interactive setup from a project checkout."""
    if not (project_root / "pyproject.toml").is_file():
        raise CliConfigError("Run setup from the Link Hoarder project directory.")
    mode = _select_mode()
    if mode is SetupMode.LOCAL:
        config = SavedCliConfig(backend=BackendKind.LOCAL)
    elif mode is SetupMode.LOCAL_API:
        config = _local_api_config(project_root)
    else:
        config = _remote_config()

    config_path = save_cli_config(config)
    installed = install_wrapper_scripts(project_root, _tool_executable())
    typer.echo(f"Saved configuration: {config_path}")
    typer.echo(f"Installed {len(installed)} scripts in {installed[0].parent}")
    typer.echo("Add ~/.local/scripts to PATH if the directory is not already present.")


def main() -> None:
    """Run the interactive user setup."""
    try:
        run_setup(Path.cwd().resolve())
    except CliConfigError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error


if __name__ == "__main__":
    main()
