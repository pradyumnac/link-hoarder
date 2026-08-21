"""Application configuration."""

import json
from enum import StrEnum
from pathlib import Path

from platformdirs import user_config_path, user_data_path
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendKind(StrEnum):
    """CLI bookmark backend."""

    LOCAL = "local"
    API = "api"


def default_database_path() -> Path:
    """Return the platform-native database path."""
    return Path(user_data_path("link-hoarder", appauthor=False)) / "bookmarks.db"


def default_config_path() -> Path:
    """Return the platform-native CLI configuration path."""
    return Path(user_config_path("link-hoarder", appauthor=False)) / "config.json"


class Settings(BaseSettings):
    """Validated environment and application settings."""

    model_config = SettingsConfigDict(
        env_prefix="LINK_HOARDER_",
        extra="ignore",
    )

    database_path: Path = default_database_path()
    api_key: SecretStr | None = Field(default=None, min_length=32)
    backend: BackendKind | None = None
    api_url: HttpUrl | None = None
    api_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def database_url(self) -> str:
        """Return a SQLAlchemy SQLite URL."""
        return f"sqlite:///{self.database_path.expanduser().resolve().as_posix()}"


class SavedCliConfig(BaseModel):
    """Validated user configuration saved outside the environment."""

    model_config = ConfigDict(extra="forbid")

    backend: BackendKind = BackendKind.LOCAL
    api_url: HttpUrl | None = None
    api_key: SecretStr | None = Field(default=None, min_length=32)
    export_directory: Path | None = None


class ResolvedCliConfig(BaseModel):
    """Effective CLI backend configuration."""

    backend: BackendKind
    api_url: HttpUrl | None = None
    api_key: SecretStr | None = None
    api_timeout_seconds: float


class CliConfigError(Exception):
    """The saved or effective CLI configuration is invalid."""


def load_cli_config(path: Path | None = None) -> SavedCliConfig:
    """Load saved CLI configuration, or return local defaults."""
    current = path or default_config_path()
    try:
        content = current.read_text(encoding="utf-8")
    except FileNotFoundError:
        return SavedCliConfig()
    except OSError as error:
        raise CliConfigError(
            f"The configuration file could not be read: {current}"
        ) from error
    try:
        return SavedCliConfig.model_validate_json(content)
    except ValidationError as error:
        raise CliConfigError(f"The configuration file is invalid: {current}") from error


def save_cli_config(config: SavedCliConfig, path: Path | None = None) -> Path:
    """Save CLI configuration with user-only file permissions."""
    current = path or default_config_path()
    current.parent.mkdir(parents=True, exist_ok=True)
    temporary = current.with_name(f".{current.name}.tmp")
    api_key = config.api_key.get_secret_value() if config.api_key is not None else None
    payload: dict[str, object] = {
        "backend": config.backend.value,
        "api_url": str(config.api_url) if config.api_url is not None else None,
        "api_key": api_key,
        "export_directory": (
            str(config.export_directory)
            if config.export_directory is not None
            else None
        ),
    }
    try:
        temporary.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(current)
        current.chmod(0o600)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise CliConfigError(
            f"The configuration file could not be saved: {current}"
        ) from error
    return current


def resolve_cli_config(
    settings: Settings,
    selected_backend: BackendKind | None,
    saved: SavedCliConfig | None = None,
) -> ResolvedCliConfig:
    """Resolve CLI options, environment values, and saved configuration."""
    stored = saved or load_cli_config()
    backend = selected_backend or settings.backend or stored.backend
    api_url = settings.api_url or stored.api_url
    api_key = settings.api_key or stored.api_key
    if backend is BackendKind.API and api_url is None:
        raise CliConfigError(
            "API mode requires LINK_HOARDER_API_URL or a saved API URL."
        )
    if backend is BackendKind.API and api_key is None:
        raise CliConfigError(
            "API mode requires LINK_HOARDER_API_KEY or a saved API key."
        )
    return ResolvedCliConfig(
        backend=backend,
        api_url=api_url,
        api_key=api_key,
        api_timeout_seconds=settings.api_timeout_seconds,
    )
