from __future__ import annotations

from functools import lru_cache

from .config import resolve_repo_root
from .prompts_models import Prompts
from .toml import read_toml


@lru_cache(maxsize=1)
def load_prompts() -> Prompts:
    """
    Load prompts from a TOML file
    :return: Prompts instance
    """

    repo_root = resolve_repo_root()
    prompts_path = repo_root / "configs" / "prompts.toml"

    if not prompts_path.exists():
        raise FileNotFoundError(f"Prompts file not found: {prompts_path}")

    toml_data = read_toml(prompts_path)
    prompt_root = toml_data.get("prompts", {})
    return Prompts.model_validate(prompt_root)
