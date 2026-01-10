from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .config import resolve_repo_root
from .logging_models import LoggingConfig
from .toml import read_toml


@lru_cache(maxsize=1)
def load_logging_config(logging_toml_path: str | None = None) -> LoggingConfig:
    """Load logging configuration from configs/logging.toml."""
    repo_root = resolve_repo_root()
    default_logging_path = repo_root / "configs" / "logging.toml"
    logging_path = Path(logging_toml_path) if logging_toml_path else default_logging_path

    if not logging_path.exists():
        raise FileNotFoundError(f"Logging config file not found: {logging_path}")

    toml_data = read_toml(logging_path)
    logging_root = toml_data.get("logging", {})
    return LoggingConfig.model_validate(logging_root)
