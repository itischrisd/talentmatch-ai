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
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT: str = ""

    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: SecretStr
    NEO4J_DATABASE: str

    STORAGE_BACKEND: str = ""


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
        "embeddings_deployment": env.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT or env.AZURE_OPENAI_CHAT_DEPLOYMENT,
    }

    payload["neo4j"] = {
        **payload.get("neo4j", {}),
        "uri": env.NEO4J_URI,
        "username": env.NEO4J_USERNAME,
        "password": env.NEO4J_PASSWORD,
        "database": env.NEO4J_DATABASE,
    }

    if env.STORAGE_BACKEND.strip():
        payload["storage"] = {
            **payload.get("storage", {}),
            "backend": env.STORAGE_BACKEND,
        }

    return payload


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """
    Load settings from configs/settings.toml and environment variables
    :return: Settings instance
    """

    repo_root = resolve_repo_root()
    env_path = repo_root / ".env"
    env = EnvironmentSettings(_env_file=env_path if env_path.exists() else None)

    settings_path = repo_root / "configs" / "settings.toml"
    if not settings_path.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    toml_data = read_settings_toml(settings_path)
    payload = build_settings_payload(toml_data, env)
    return Settings.from_payload(payload)
