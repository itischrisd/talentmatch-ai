from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .config_models import Settings
from .toml import read_settings_toml


class EnvironmentSettings(BaseSettings):
    """
    Environment-backed settings for secrets and service endpoints
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    OPENAI_API_KEY: SecretStr
    OPENAI_BASE_URL: str | None = None
    OPENAI_ORGANIZATION: str | None = None


def resolve_repo_root() -> Path:
    """
    Locate the repository root by finding the nearest 'configs' directory
    :return: path to the repository root
    """

    start = Path(__file__).resolve()
    for parent in (start.parent, *start.parents):
        if (parent / "configs").is_dir():
            return parent
    return start.parent


def build_settings_payload(toml_data: dict[str, Any], env: EnvironmentSettings) -> dict[str, Any]:
    """
    Build the settings payload by merging TOML data with environment variables
    :param toml_data: settings from TOML
    :param env: settings from .env
    :return: merged settings payload
    """

    payload = dict(toml_data)

    payload["openai"] = {
        **payload.get("openai", {}),
        "api_key": env.OPENAI_API_KEY,
        "base_url": env.OPENAI_BASE_URL,
        "organization": env.OPENAI_ORGANIZATION,
    }

    return payload


@lru_cache(maxsize=1)
def load_settings(settings_toml_path: str | None = None) -> Settings:
    """
    Load settings from configs/settings.toml and environment variables
    :param settings_toml_path: optional path to settings TOML file
    :return: Settings instance
    """

    repo_root = resolve_repo_root()
    env_path = repo_root / ".env"
    env = EnvironmentSettings(_env_file=env_path if env_path.exists() else None)

    default_settings_path = repo_root / "configs" / "settings.toml"
    settings_path = Path(settings_toml_path) if settings_toml_path else default_settings_path

    if not settings_path.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    toml_data = read_settings_toml(settings_path)
    payload = build_settings_payload(toml_data, env)
    return Settings.from_payload(payload)
