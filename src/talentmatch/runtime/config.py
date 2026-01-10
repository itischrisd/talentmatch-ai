from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from .config_models import Settings
from .toml import read_toml


class EnvironmentSettings(BaseSettings):
    """Environment-backed settings for secrets and service endpoints."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_CHAT_DEPLOYMENT: str
    AZURE_OPENAI_EMBED_DEPLOYMENT: str

    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    NEO4J_DATABASE: str = "neo4j"

    CHROMA_URL: str = "http://chroma:8000"
    CHROMA_TENANT: str = "default_tenant"
    CHROMA_DATABASE: str = "default_database"


def resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_settings_payload(toml_data: dict[str, Any], env: EnvironmentSettings) -> dict[str, Any]:
    payload = dict(toml_data)

    payload["azure_openai"] = {
        **payload.get("azure_openai", {}),
        "endpoint": env.AZURE_OPENAI_ENDPOINT,
        "api_key": env.AZURE_OPENAI_API_KEY,
        "api_version": env.AZURE_OPENAI_API_VERSION,
        "chat_deployment": env.AZURE_OPENAI_CHAT_DEPLOYMENT,
        "embed_deployment": env.AZURE_OPENAI_EMBED_DEPLOYMENT,
    }

    payload["neo4j"] = {
        **payload.get("neo4j", {}),
        "uri": env.NEO4J_URI,
        "user": env.NEO4J_USER,
        "password": env.NEO4J_PASSWORD,
        "database": env.NEO4J_DATABASE,
    }

    payload["chroma"] = {
        **payload.get("chroma", {}),
        "url": env.CHROMA_URL,
        "tenant": env.CHROMA_TENANT,
        "database": env.CHROMA_DATABASE,
    }

    return payload


@lru_cache(maxsize=1)
def load_settings(settings_toml_path: str | None = None) -> Settings:
    """Load settings from configs/settings.toml and environment variables."""

    repo_root = resolve_repo_root()
    env_path = repo_root / ".env"

    env = EnvironmentSettings(_env_file=env_path)

    default_settings_path = repo_root / "configs" / "settings.toml"
    settings_path = Path(settings_toml_path) if settings_toml_path else default_settings_path

    if not settings_path.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    toml_data = read_toml(settings_path)
    payload = build_settings_payload(toml_data, env)
    return Settings.model_validate(payload)
