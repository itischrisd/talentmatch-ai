from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic.types import SecretStr

from util.common import (
    assert_true,
    build_check_context,
    load_prompts_from_context,
    load_settings_from_context,
    print_fail,
    print_ok,
    read_effective_env,
)


@dataclass(frozen=True, slots=True)
class MappingSpec:
    source: str
    source_key: str
    model_path: str


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def flatten_dict(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
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


def normalize_model_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return normalize_model_value(value.model_dump(mode="python"))
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if hasattr(value, "get_secret_value") and callable(getattr(value, "get_secret_value")):
        return value.get_secret_value()
    if isinstance(value, dict):
        return {k: normalize_model_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_model_value(v) for v in value]
    if isinstance(value, tuple):
        return [normalize_model_value(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def validate_parameter(source_name: str, source_key: str, source_value: Any, model_obj: Any, model_path: str) -> bool:
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

    normalized = normalize_model_value(model_value)
    if normalized != source_value:
        print_fail(
            f'{source_name} Parameter "{source_key}" mapped to "{model_path}" but value differs: '
            f"file={source_value!r} model={normalized!r}"
        )
        return False

    print_ok(f'{source_name} Parameter "{source_key}" loaded and mapped correctly')
    return True


def build_settings_mappings(settings_flat: dict[str, Any]) -> list[MappingSpec]:
    mappings: list[MappingSpec] = []
    for dotted_key in sorted(settings_flat.keys()):
        model_path = map_settings_key_to_model_path(dotted_key)
        mappings.append(MappingSpec(source="toml", source_key=dotted_key, model_path=model_path))
    return mappings


def map_settings_key_to_model_path(dotted_key: str) -> str:
    parts = dotted_key.split(".")
    if len(parts) >= 5 and parts[0] == "llm" and parts[1] == "use_cases" and parts[-1] == "model":
        parts[-1] = "deployment"
        return ".".join(parts)
    return dotted_key


def build_env_to_settings_mappings() -> list[MappingSpec]:
    return [
        MappingSpec("env", "AZURE_OPENAI_ENDPOINT", "azure_openai.endpoint"),
        MappingSpec("env", "AZURE_OPENAI_API_KEY", "azure_openai.api_key"),
        MappingSpec("env", "AZURE_OPENAI_API_VERSION", "azure_openai.api_version"),
        MappingSpec("env", "AZURE_OPENAI_CHAT_DEPLOYMENT", "azure_openai.chat_deployment"),
    ]


def collect_model_leaf_paths(value: Any, prefix: str) -> set[str]:
    if value is None:
        return {prefix} if prefix else set()

    if isinstance(value, BaseModel):
        paths: set[str] = set()
        for field_name in BaseModel.model_fields.keys():
            field_value = getattr(value, field_name)
            full = f"{prefix}.{field_name}" if prefix else field_name
            paths |= collect_model_leaf_paths(field_value, full)
        return paths

    if isinstance(value, dict):
        paths: set[str] = set()
        for key, item in value.items():
            key_str = str(key)
            full = f"{prefix}.{key_str}" if prefix else key_str
            paths |= collect_model_leaf_paths(item, full)
        return paths

    return {prefix} if prefix else set()


def validate_missing_model_mappings(model_obj: Any, expected_model_paths: set[str], label: str) -> bool:
    all_ok = True
    model_paths_present = collect_model_leaf_paths(model_obj, prefix="")
    unmapped = sorted(p for p in model_paths_present if p not in expected_model_paths)
    for path in unmapped:
        print_fail(f'{label} Model attribute "{path}" has no corresponding file mapping in this check')
        all_ok = False
    return all_ok


def run() -> int:
    context = build_check_context(Path(__file__))
    failures = 0

    settings = load_settings_from_context(context)
    if settings is None:
        return 1

    prompts = load_prompts_from_context(context)
    if prompts is None:
        return 1

    try:
        import talentmatch.config as config_module

        exported = set(getattr(config_module, "__all__", []))
        required = {"Settings", "Prompts", "load_settings", "load_prompts", "resolve_repo_root"}
        ok = assert_true(required.issubset(exported), ok="config public API __all__ ok",
                         fail="config __all__ missing items")
        failures += 0 if ok else 1
        for name in required:
            present = hasattr(config_module, name)
            ok = assert_true(present, ok=f"config exports {name}", fail=f"config missing export: {name}")
            failures += 0 if ok else 1
    except Exception as exc:
        print_fail(f"config module public API check failed: {exc}")
        failures += 1

    if not context.settings_path.exists():
        print_fail(f'Settings TOML not found: "{context.settings_path}"')
        return 1

    if not context.prompts_path.exists():
        print_fail(f'Prompts TOML not found: "{context.prompts_path}"')
        return 1

    try:
        from talentmatch.config.toml import read_settings_toml

        settings_toml = read_settings_toml(context.settings_path)
        print_ok("config.toml.read_settings_toml() succeeded")
    except Exception as exc:
        print_fail(f"config.toml.read_settings_toml() failed: {exc}")
        return 1

    prompts_toml = read_toml(context.prompts_path)
    prompts_root = prompts_toml.get("prompts", {})

    print("")
    print("Settings mapping validation")

    settings_flat = flatten_dict(settings_toml)
    settings_mappings = build_settings_mappings(settings_flat)
    expected_settings_paths: set[str] = set()

    for spec in settings_mappings:
        expected_settings_paths.add(spec.model_path)
        value = settings_flat.get(spec.source_key)
        if not validate_parameter("settings.toml", spec.source_key, value, settings, spec.model_path):
            failures += 1

    env_path = context.repo_root / ".env"
    effective_env = read_effective_env(env_path)
    env_mappings = build_env_to_settings_mappings()

    for spec in env_mappings:
        if spec.source_key not in effective_env:
            print_fail(f'env Parameter "{spec.source_key}" missing in environment and .env')
            failures += 1
            continue
        expected_settings_paths.add(spec.model_path)
        value = effective_env.get(spec.source_key)
        if not validate_parameter("env", spec.source_key, value, settings, spec.model_path):
            failures += 1

    if not validate_missing_model_mappings(settings, expected_settings_paths, "Settings"):
        failures += 1

    print("")
    print("Prompts mapping validation")

    prompts_flat = flatten_dict(prompts_root)
    expected_prompts_paths: set[str] = set()

    for dotted_key, value in sorted(prompts_flat.items()):
        expected_prompts_paths.add(dotted_key)
        if not validate_parameter("prompts.toml", dotted_key, value, prompts, dotted_key):
            failures += 1

    if not validate_missing_model_mappings(prompts, expected_prompts_paths, "Prompts"):
        failures += 1

    print("")
    print("Summary")

    if failures == 0:
        print_ok("Config module checks passed")
        return 0

    print_fail(f"Config module checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
