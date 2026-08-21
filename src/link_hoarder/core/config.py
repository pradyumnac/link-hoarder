"""Application configuration."""

from pathlib import Path

from platformdirs import user_data_path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_database_path() -> Path:
    """Return the platform-native database path."""
    return Path(user_data_path("link-hoarder", appauthor=False)) / "bookmarks.db"


class Settings(BaseSettings):
    """Validated application settings."""

    model_config = SettingsConfigDict(
        env_prefix="LINK_HOARDER_",
        env_file=".env",
        extra="ignore",
    )

    database_path: Path = default_database_path()
    api_key: SecretStr | None = None
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def database_url(self) -> str:
        """Return a SQLAlchemy SQLite URL."""
        return f"sqlite:///{self.database_path.expanduser().resolve().as_posix()}"
