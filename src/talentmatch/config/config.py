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

    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_KEY: SecretStr
    AZURE_OPENAI_API_VERSION: str
    AZURE_OPENAI_CHAT_DEPLOYMENT: str

    NEO4J_URI: str | None = None
    NEO4J_USERNAME: str | None = None
    NEO4J_PASSWORD: SecretStr | None = None
    NEO4J_DATABASE: str | None = None


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

    payload["azure_openai"] = {
        **payload.get("azure_openai", {}),
        "endpoint": env.AZURE_OPENAI_ENDPOINT,
        "api_key": env.AZURE_OPENAI_API_KEY,
        "api_version": env.AZURE_OPENAI_API_VERSION,
        "chat_deployment": env.AZURE_OPENAI_CHAT_DEPLOYMENT,
    }

    neo4j_present = any(
        value is not None and str(value).strip()
        for value in (env.NEO4J_URI, env.NEO4J_USERNAME, env.NEO4J_PASSWORD, env.NEO4J_DATABASE)
    )
    if neo4j_present or "neo4j" in payload:
        current = payload.get("neo4j", {})
        payload["neo4j"] = {
            **current,
            "uri": env.NEO4J_URI or current.get("uri", "bolt://localhost:7687"),
            "username": env.NEO4J_USERNAME or current.get("username", "neo4j"),
            "password": env.NEO4J_PASSWORD if env.NEO4J_PASSWORD is not None else current.get("password"),
            "database": env.NEO4J_DATABASE or current.get("database", "neo4j"),
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
