"""Minimal configuration tests. Does not require a real API key in source."""

from pathlib import Path

import pytest

from app.config import (
    DEFAULT_MAX_REPLANS,
    DEFAULT_OPENAI_MODEL,
    PROJECT_ROOT,
    SettingsError,
    load_settings,
)

DB_PATH = PROJECT_ROOT / "interior_company_catalog.db"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
GITIGNORE = PROJECT_ROOT / ".gitignore"


def _env(**overrides: str) -> dict[str, str]:
    base = {
        "OPENAI_API_KEY": "sk-test-not-a-real-key",
        "OPENAI_MODEL": DEFAULT_OPENAI_MODEL,
        "CATALOG_DB_PATH": str(DB_PATH),
        "MAX_REPLANS": "3",
    }
    base.update(overrides)
    return base


def test_env_example_exists_with_required_keys():
    assert ENV_EXAMPLE.is_file()
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=" in text
    assert "OPENAI_MODEL=gpt-5.6" in text
    assert "CATALOG_DB_PATH=./interior_company_catalog.db" in text
    assert "MAX_REPLANS=3" in text
    assert "sk-" not in text


def test_gitignore_ignores_dotenv():
    text = GITIGNORE.read_text(encoding="utf-8")
    assert any(line.strip() == ".env" for line in text.splitlines())


def test_load_settings_with_defaults():
    settings = load_settings(env_file=None, environ=_env(OPENAI_MODEL="", MAX_REPLANS=""))
    assert settings.openai_model == DEFAULT_OPENAI_MODEL
    assert settings.max_replans == DEFAULT_MAX_REPLANS
    assert settings.catalog_db_path == DB_PATH.resolve()
    assert settings.openai_api_key == "sk-test-not-a-real-key"


def test_missing_api_key_is_rejected():
    with pytest.raises(SettingsError):
        load_settings(env_file=None, environ=_env(OPENAI_API_KEY=""))


def test_missing_catalog_is_rejected(tmp_path: Path):
    missing = tmp_path / "no-such.db"
    with pytest.raises(SettingsError):
        load_settings(env_file=None, environ=_env(CATALOG_DB_PATH=str(missing)))


def test_invalid_max_replans_is_rejected():
    with pytest.raises(SettingsError):
        load_settings(env_file=None, environ=_env(MAX_REPLANS="three"))
    with pytest.raises(SettingsError):
        load_settings(env_file=None, environ=_env(MAX_REPLANS="-1"))


def test_empty_model_falls_back_to_default():
    settings = load_settings(env_file=None, environ=_env(OPENAI_MODEL="   "))
    assert settings.openai_model == DEFAULT_OPENAI_MODEL


def test_relative_catalog_path_resolves_to_project_root():
    settings = load_settings(
        env_file=None,
        environ=_env(CATALOG_DB_PATH="./interior_company_catalog.db"),
    )
    assert settings.catalog_db_path == DB_PATH.resolve()
