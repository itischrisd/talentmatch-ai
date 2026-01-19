from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from util.common import print_fail, print_ok
from talentmatch.runtime import load_logging_config, load_prompts, load_settings
from talentmatch.runtime.toml import read_settings_toml



@dataclass(frozen=True)
class MappingSpec:
    source: str
    source_key: str
    model_path: str


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env[key] = value
    return env


def flatten_dict(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten_dict(value, prefix=full_key))
        else:
            flat[full_key] = value
    return flat


def get_by_path(obj: Any, dotted_path: str) -> Any:
    current = obj
    for part in dotted_path.split("."):
        if isinstance(current, dict):
            if part not in current:
                raise AttributeError(dotted_path)
            current = current[part]
            continue

        if not hasattr(current, part):
            raise AttributeError(dotted_path)
        current = getattr(current, part)

    return current


def format_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return repr(value)


def validate_parameter(
        source_name: str,
        source_key: str,
        source_value: Any,
        model_obj: Any,
        model_path: str,
) -> bool:
    if source_value is None:
        print_fail(f'{source_name} Parameter "{source_key}" has no value in file')
        return False

    try:
        model_value = get_by_path(model_obj, model_path)
    except AttributeError:
        print_fail(
            f'{source_name} Parameter "{source_key}" exists in file but is not mapped to model attribute "{model_path}"'
        )
        return False

    normalized_model_value = normalize_model_value(model_value)

    if normalized_model_value != source_value:
        print_fail(
            f'{source_name} Parameter "{source_key}" mapped to "{model_path}" but value differs: '
            f'file={format_value(source_value)} model={format_value(model_value)}'
        )
        return False

    print_ok(f'{source_name} Parameter "{source_key}" loaded and mapped correctly')
    return True


def validate_missing_model_mappings(
        model_obj: Any,
        expected_model_paths: set[str],
        label: str,
) -> bool:
    all_ok = True
    model_paths_present = collect_model_leaf_paths(model_obj, prefix="")
    unmapped = sorted(p for p in model_paths_present if p not in expected_model_paths)
    for path in unmapped:
        print_fail(f'{label} Model attribute "{path}" has no corresponding file mapping in this check')
        all_ok = False
    return all_ok


def collect_model_leaf_paths(model_obj: Any, prefix: str) -> set[str]:
    result: set[str] = set()
    for name, value in vars(model_obj).items():
        full = f"{prefix}.{name}" if prefix else name
        if is_pydantic_model(value):
            result |= collect_model_leaf_paths(value, full)
        else:
            result.add(full)
    return result


def is_pydantic_model(value: Any) -> bool:
    return hasattr(value, "model_dump") and hasattr(value, "model_fields")


def build_env_to_settings_mappings() -> list[MappingSpec]:
    return [
        MappingSpec("env", "AZURE_OPENAI_ENDPOINT", "azure_openai.endpoint"),
        MappingSpec("env", "AZURE_OPENAI_API_KEY", "azure_openai.api_key"),
        MappingSpec("env", "AZURE_OPENAI_API_VERSION", "azure_openai.api_version"),
        MappingSpec("env", "AZURE_OPENAI_CHAT_DEPLOYMENT", "azure_openai.chat_deployment"),
    ]


def build_toml_to_model_mappings(
        toml_flat: dict[str, Any],
        root_model_prefix: str = "",
) -> list[MappingSpec]:
    mappings: list[MappingSpec] = []
    for dotted_key in toml_flat.keys():
        model_path = f"{root_model_prefix}{dotted_key}" if not root_model_prefix else f"{root_model_prefix}.{dotted_key}"
        mappings.append(MappingSpec("toml", dotted_key, model_path))
    return mappings


def normalize_model_value(value: Any) -> Any:
    """Normalizes Pydantic values to TOML-like primitives for stable comparisons."""
    if isinstance(value, BaseModel):
        return normalize_model_value(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {k: normalize_model_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_model_value(v) for v in value]
    if isinstance(value, tuple):
        return [normalize_model_value(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def run() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    settings_path = repo_root / "configs" / "settings.toml"
    prompts_path = repo_root / "configs" / "prompts.toml"
    logging_path = repo_root / "configs" / "logging.toml"

    failures = 0

    env_data = read_env(env_path)
    if not env_data:
        print_fail(f'Env file not found or empty: "{env_path}"')
        failures += 1

    if not settings_path.exists():
        print_fail(f'Settings TOML not found: "{settings_path}"')
        return 1
    if not prompts_path.exists():
        print_fail(f'Prompts TOML not found: "{prompts_path}"')
        return 1
    if not logging_path.exists():
        print_fail(f'Logging TOML not found: "{logging_path}"')
        return 1

    settings_toml = read_settings_toml(settings_path)
    prompts_toml = read_toml(prompts_path)
    logging_toml = read_toml(logging_path)

    try:
        settings = load_settings(str(settings_path))
        print_ok("runtime.load_settings() succeeded")
    except Exception as exc:
        print_fail(f"runtime.load_settings() failed: {exc}")
        return 1

    try:
        prompts = load_prompts(str(prompts_path))
        print_ok("runtime.load_prompts() succeeded")
    except Exception as exc:
        print_fail(f"runtime.load_prompts() failed: {exc}")
        return 1

    try:
        logging_config = load_logging_config(str(logging_path))
        print_ok("runtime.load_logging_config() succeeded")
    except Exception as exc:
        print_fail(f"runtime.load_logging_config() failed: {exc}")
        return 1

    print("")
    print("Settings mapping validation")

    settings_flat = flatten_dict(settings_toml)
    settings_mappings = build_toml_to_model_mappings(settings_flat)
    expected_settings_paths: set[str] = set()

    for spec in settings_mappings:
        value = settings_flat.get(spec.source_key)
        expected_settings_paths.add(spec.model_path)
        if not validate_parameter("settings.toml", spec.source_key, value, settings, spec.model_path):
            failures += 1

    env_mappings = build_env_to_settings_mappings()
    for spec in env_mappings:
        if spec.source_key not in env_data:
            print_fail(f'env Parameter "{spec.source_key}" missing in .env')
            failures += 1
            continue
        value = env_data.get(spec.source_key)
        expected_settings_paths.add(spec.model_path)
        if not validate_parameter("env", spec.source_key, value, settings, spec.model_path):
            failures += 1

    print("")
    print("Prompts mapping validation")

    prompts_root = prompts_toml.get("prompts", {})
    prompts_flat = flatten_dict(prompts_root)
    for dotted_key, value in prompts_flat.items():
        model_path = dotted_key
        if not validate_parameter("prompts.toml", dotted_key, value, prompts, model_path):
            failures += 1

    print("")
    print("Logging mapping validation")

    logging_root = logging_toml.get("logging", {})
    logging_flat = flatten_dict(logging_root)
    for dotted_key, value in logging_flat.items():
        model_path = dotted_key
        if not validate_parameter("logging.toml", dotted_key, value, logging_config, model_path):
            failures += 1

    print("")
    print("Unused .env keys validation")

    env_keys_used = {spec.source_key for spec in env_mappings}
    unused_env_keys = sorted(k for k in env_data.keys() if k not in env_keys_used)

    for key in unused_env_keys:
        print_fail(f'env Parameter "{key}" exists in .env but is not used by runtime loader')
        failures += 1

    print("")
    print("Summary")

    if failures == 0:
        print_ok("Runtime configuration checks passed")
        return 0

    print_fail(f"Runtime configuration checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
