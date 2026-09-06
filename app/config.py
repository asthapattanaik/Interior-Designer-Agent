"""Load and validate application settings from the environment.

The model name is configuration, not business logic. Spatial/layout
thresholds are intentionally not defined in this module.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_OPENAI_MODEL = "gpt-5.6"
DEFAULT_CATALOG_DB_PATH = "./interior_company_catalog.db"
DEFAULT_MAX_REPLANS = 3


class SettingsError(ValueError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    openai_api_key: str
    openai_model: str = DEFAULT_OPENAI_MODEL
    catalog_db_path: Path
    max_replans: int = DEFAULT_MAX_REPLANS

    @field_validator("openai_api_key")
    @classmethod
    def openai_api_key_must_be_present(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("OPENAI_API_KEY is required")
        return value.strip()

    @field_validator("openai_model")
    @classmethod
    def openai_model_must_be_present(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("OPENAI_MODEL must not be empty")
        return value.strip()

    @field_validator("max_replans")
    @classmethod
    def max_replans_must_be_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("MAX_REPLANS must be >= 0")
        return value

    @field_validator("catalog_db_path")
    @classmethod
    def catalog_db_path_must_exist(cls, value: Path) -> Path:
        path = value.expanduser()
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        else:
            path = path.resolve()
        if not path.is_file():
            raise ValueError(f"CATALOG_DB_PATH does not exist or is not a file: {path}")
        return path


def _optional_int(raw: str | None, default: int) -> int:
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise SettingsError("MAX_REPLANS must be an integer") from exc


def load_settings(
    env_file: Path | None = DEFAULT_ENV_FILE,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Load settings from a .env file (if present) and environment variables.

    `OPENAI_API_KEY` is required. Other values fall back to `.env.example` defaults.
    Does not create `.env` and does not log the API key.
    """
    if environ is None:
        if env_file is not None and Path(env_file).is_file():
            load_dotenv(env_file, override=False)
        source: Mapping[str, str] = os.environ
    else:
        source = environ

    model_raw = source.get("OPENAI_MODEL", "")
    model = model_raw.strip() if model_raw and str(model_raw).strip() else DEFAULT_OPENAI_MODEL
    catalog = source.get("CATALOG_DB_PATH", "") or DEFAULT_CATALOG_DB_PATH
    try:
        return Settings(
            openai_api_key=source.get("OPENAI_API_KEY", "") or "",
            openai_model=model,
            catalog_db_path=Path(catalog),
            max_replans=_optional_int(
                source.get("MAX_REPLANS"), DEFAULT_MAX_REPLANS
            ),
        )
    except (ValidationError, ValueError) as exc:
        raise SettingsError(str(exc)) from exc
