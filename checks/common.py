from __future__ import annotations

import json
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


@dataclass(frozen=True)
class CheckContext:
    repo_root: Path
    settings_path: Path


def build_check_context(current_file: Path) -> CheckContext:
    """Build a CheckContext assuming checks/ is located directly under repository root."""
    repo_root = current_file.resolve().parents[1]
    return CheckContext(
        repo_root=repo_root,
        settings_path=repo_root / "configs" / "settings.toml",
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


def assert_uuid(value: Any, *, label: str) -> bool:
    if is_uuid(value):
        print_ok(f"{label} ok")
        return True
    print_fail(f"{label} invalid: {value}")
    return False


def assert_in(value: Any, allowed: list[Any], *, label: str) -> bool:
    return assert_true(
        value in allowed,
        ok=f'{label} is valid: "{value}"',
        fail=f'{label} invalid: "{value}", allowed={allowed}',
    )


def assert_between(value: int, *, min_value: int, max_value: int, label: str) -> bool:
    return assert_true(
        min_value <= value <= max_value,
        ok=f"{label} within range: {value}",
        fail=f"{label} out of range: {value}, expected [{min_value}, {max_value}]",
    )


def assert_json_serializable(value: Any, *, label: str, sort_keys: bool = False) -> bool:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=sort_keys)
        print_ok(f"{label} is JSON-serializable")
        return True
    except Exception as exc:
        print_fail(f"{label} is not JSON-serializable: {exc}")
        return False


def load_settings_from_context(context: CheckContext) -> Any | None:
    if not context.settings_path.exists():
        print_fail(f'Settings TOML not found: "{context.settings_path}"')
        return None

    try:
        from talentmatch.runtime import load_settings

        settings = load_settings(str(context.settings_path))
        print_ok("runtime.load_settings() succeeded")
        return settings
    except Exception as exc:
        print_fail(f"runtime.load_settings() failed: {exc}")
        return None
