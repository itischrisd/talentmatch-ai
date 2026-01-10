from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .config import resolve_repo_root
from .prompts_models import Prompts
from .toml import read_toml


@lru_cache(maxsize=1)
def load_prompts(prompts_toml_path: str | None = None) -> Prompts:
    """Load prompts from configs/prompts.toml."""
    repo_root = resolve_repo_root()
    default_prompts_path = repo_root / "configs" / "prompts.toml"
    prompts_path = Path(prompts_toml_path) if prompts_toml_path else default_prompts_path

    if not prompts_path.exists():
        raise FileNotFoundError(f"Prompts file not found: {prompts_path}")

    toml_data = read_toml(prompts_path)
    prompt_root = toml_data.get("prompts", {})
    return Prompts.model_validate(prompt_root)
