from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CHECK_OK = "✅"
CHECK_FAIL = "❌"
CHECK_WARN = "⚠️"

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CheckContext:
    repo_root: Path
    settings_path: Path
    prompts_path: Path


def build_check_context(current_file: Path) -> CheckContext:
    """
    Build a CheckContext assuming checks/ is located directly under repository root.
    :param current_file: file path used as reference for resolving the repository root
    :return: CheckContext instance
    """

    repo_root = current_file.resolve().parents[1]
    return CheckContext(
        repo_root=repo_root,
        settings_path=repo_root / "configs" / "settings.toml",
        prompts_path=repo_root / "configs" / "prompts.toml",
    )


def print_ok(message: str) -> None:
    print(f"{CHECK_OK} {message}")


def print_fail(message: str) -> None:
    print(f"{CHECK_FAIL} {message}")


def print_warn(message: str) -> None:
    print(f"{CHECK_WARN} {message}")


def assert_true(condition: bool, *, ok: str, fail: str) -> bool:
    if condition:
        print_ok(ok)
        return True
    print_fail(fail)
    return False


def is_uuid(value: Any) -> bool:
    return isinstance(value, str) and _UUID_RE.match(value) is not None


def assert_json_serializable(value: Any, *, label: str) -> bool:
    try:
        json.dumps(value, ensure_ascii=False)
        print_ok(f"{label} is JSON-serializable")
        return True
    except Exception as exc:
        print_fail(f"{label} is not JSON-serializable: {exc}")
        return False


def read_env_file(path: Path) -> dict[str, str]:
    """
    Read a .env-like file using a minimal KEY=VALUE parser.
    :param path: path to the env file
    :return: dictionary with parsed environment values
    """

    env: dict[str, str] = {}
    if not path.exists():
        return env

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env[key] = value
    return env


def read_effective_env(path: Path) -> dict[str, str]:
    """
    Build effective env mapping preferring .env file values and falling back to process environment.
    :param path: path to .env file
    :return: dictionary of environment values
    """

    file_env = read_env_file(path)
    merged = dict(os.environ)
    merged.update(file_env)
    return {k: str(v) for k, v in merged.items()}


def load_settings_from_context(context: CheckContext) -> Any | None:
    """
    Load runtime settings using the project's public loader.
    :param context: CheckContext instance
    :return: Settings model or None on failure
    """

    if not context.settings_path.exists():
        print_fail(f'Settings TOML not found: "{context.settings_path}"')
        return None

    try:
        from talentmatch.config import load_settings

        settings = load_settings()
        print_ok("config.load_settings() succeeded")
        return settings
    except Exception as exc:
        print_fail(f"config.load_settings() failed: {exc}")
        return None


def load_prompts_from_context(context: CheckContext) -> Any | None:
    """
    Load prompts using the project's public loader.
    :param context: CheckContext instance
    :return: Prompts model or None on failure
    """

    if not context.prompts_path.exists():
        print_fail(f'Prompts TOML not found: "{context.prompts_path}"')
        return None

    try:
        from talentmatch.config import load_prompts

        prompts = load_prompts()
        print_ok("config.load_prompts() succeeded")
        return prompts
    except Exception as exc:
        print_fail(f"config.load_prompts() failed: {exc}")
        return None
