from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final, Optional

from dotenv import dotenv_values


_DOTENV_PATH: Final[str] = ".env"


@dataclass(frozen=True)
class Settings:
    """Application configuration loaded from environment variables.

    This wrapper keeps configuration access explicit and fully typed.
    """

    google_api_key: str
    database_url: str
    environment: str
    gemini_model_name: str


def _load_from_env() -> Settings:
    """Load configuration from `.env` and OS environment variables."""
    dotenv_config = dotenv_values(_DOTENV_PATH)

    def _get(name: str, default: Optional[str] = None) -> Optional[str]:
        value = os.getenv(name)
        if value is not None:
            return value
        return dotenv_config.get(name) or default

    google_api_key = _get("GOOGLE_API_KEY")
    if not google_api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is required but was not found in the environment or .env file.",
        )

    environment = _get("ENV", "development") or "development"

    # Default to a local SQLite database for development.
    default_sqlite_url = "sqlite:///./negotiator_ai.db"
    database_url = _get("DATABASE_URL", default_sqlite_url) or default_sqlite_url

    gemini_model_name = _get("GEMINI_MODEL_NAME", "gemini-2.5-flash") or "gemini-2.5-flash"

    return Settings(
        google_api_key=google_api_key,
        database_url=database_url,
        environment=environment,
        gemini_model_name=gemini_model_name,
    )


_SETTINGS: Optional[Settings] = None


def get_settings() -> Settings:
    """Return a cached instance of loaded application settings."""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = _load_from_env()
    return _SETTINGS

