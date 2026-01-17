from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from talentmatch.datasets import CvStructMarkdownStore, StructuredCvGenerator
from talentmatch.runtime import load_settings

CHECK_OK = "✅"
CHECK_FAIL = "❌"

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CheckContext:
    repo_root: Path
    settings_path: Path


def print_ok(message: str) -> None:
    print(f"{CHECK_OK} {message}")


def print_fail(message: str) -> None:
    print(f"{CHECK_FAIL} {message}")


def assert_true(condition: bool, *, ok: str, fail: str) -> bool:
    if condition:
        print_ok(ok)
        return True
    print_fail(fail)
    return False


def is_uuid(value: Any) -> bool:
    return isinstance(value, str) and UUID_RE.match(value) is not None


def run() -> int:
    context = CheckContext(
        repo_root=Path(__file__).resolve().parents[1],
        settings_path=Path(__file__).resolve().parents[1] / "configs" / "settings.toml",
    )

    if not context.settings_path.exists():
        print_fail(f'Settings TOML not found: "{context.settings_path}"')
        return 1

    try:
        settings = load_settings(str(context.settings_path))
        print_ok("runtime.load_settings() succeeded")
    except Exception as exc:
        print_fail(f"runtime.load_settings() failed: {exc}")
        return 1

    try:
        generator = StructuredCvGenerator(settings)
        print_ok("StructuredCvGenerator(settings) succeeded")
    except Exception as exc:
        print_fail(f"StructuredCvGenerator(settings) failed: {exc}")
        return 1

    try:
        cv_result = generator.generate_one()
        print_ok("generate_one() succeeded")
    except Exception as exc:
        print_fail(f"generate_one() failed: {exc}")
        return 1

    failures = 0
    failures += 0 if assert_true(is_uuid(cv_result.uuid), ok="uuid format ok",
                                 fail=f"uuid invalid: {cv_result.uuid}") else 1
    failures += 0 if assert_true(isinstance(cv_result.cv, dict), ok="cv structure is dict",
                                 fail="cv structure is not dict") else 1

    try:
        store = CvStructMarkdownStore(settings)
        print_ok("CvStructMarkdownStore(settings) succeeded")
    except Exception as exc:
        print_fail(f"CvStructMarkdownStore(settings) failed: {exc}")
        return 1

    base_dir = Path(settings.paths.cv_markdown_dir)
    md_path = base_dir / f"{cv_result.uuid}.md"

    try:
        store.store(cv_result.uuid, cv_result.cv)
        print_ok("store(uuid, cv_struct) succeeded")
    except Exception as exc:
        print_fail(f"store(uuid, cv_struct) failed: {exc}")
        return 1

    failures += 0 if assert_true(md_path.exists(), ok="markdown file exists",
                                 fail=f'markdown file not found: "{md_path}"') else 1

    if md_path.exists():
        content = md_path.read_text(encoding="utf-8")
        failures += 0 if assert_true(len(content.strip()) > 0, ok="markdown is non-empty",
                                     fail="markdown is empty") else 1
        failures += 0 if assert_true(content.lstrip().startswith("# "), ok="markdown starts with H1",
                                     fail="markdown does not start with H1") else 1

    try:
        store.store(cv_result.uuid, cv_result.cv)
        print_ok("overwrite store() succeeded")
    except Exception as exc:
        print_fail(f"overwrite store() failed: {exc}")
        return 1

    failures += 0 if assert_true(md_path.exists(), ok="markdown file still exists after overwrite",
                                 fail="markdown file missing after overwrite") else 1

    if failures == 0:
        print_ok("CV struct -> Markdown checks passed")
        return 0

    print_fail(f"CV struct -> Markdown checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
