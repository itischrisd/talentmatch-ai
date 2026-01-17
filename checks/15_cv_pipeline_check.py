from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from talentmatch.datasets import CvArtifactsPipeline
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
        pipeline = CvArtifactsPipeline(settings)
        print_ok("CvArtifactsPipeline(settings) succeeded")
    except Exception as exc:
        print_fail(f"CvArtifactsPipeline(settings) failed: {exc}")
        return 1

    try:
        results = pipeline.generate_many(2)
        print_ok("generate_many(2) succeeded")
    except Exception as exc:
        print_fail(f"generate_many(2) failed: {exc}")
        return 1

    failures = 0
    failures += 0 if assert_true(len(results) == 2, ok="generated 2 results", fail="did not generate 2 results") else 1

    struct_dir = Path(settings.paths.cv_struct_json_dir)
    md_dir = Path(settings.paths.cv_markdown_dir)
    pdf_dir = Path(settings.paths.cv_pdf_dir)

    seen: set[str] = set()

    for idx, item in enumerate(results, start=1):
        failures += 0 if assert_true(is_uuid(item.uuid), ok=f"[{idx}] uuid format ok",
                                     fail=f"[{idx}] uuid invalid: {item.uuid}") else 1
        failures += 0 if assert_true(item.uuid not in seen, ok=f"[{idx}] uuid unique",
                                     fail=f"[{idx}] duplicate uuid: {item.uuid}") else 1
        seen.add(item.uuid)

        json_path = struct_dir / f"{item.uuid}.json"
        md_path = md_dir / f"{item.uuid}.md"
        pdf_path = pdf_dir / f"{item.uuid}.pdf"

        failures += 0 if assert_true(json_path.exists(), ok=f"[{idx}] json exists",
                                     fail=f'[{idx}] json not found: "{json_path}"') else 1
        failures += 0 if assert_true(md_path.exists(), ok=f"[{idx}] markdown exists",
                                     fail=f'[{idx}] markdown not found: "{md_path}"') else 1
        failures += 0 if assert_true(pdf_path.exists(), ok=f"[{idx}] pdf exists",
                                     fail=f'[{idx}] pdf not found: "{pdf_path}"') else 1

        if json_path.exists():
            try:
                parsed = json.loads(json_path.read_text(encoding="utf-8"))
                print_ok(f"[{idx}] json parse succeeded")
            except Exception as exc:
                print_fail(f"[{idx}] json parse failed: {exc}")
                return 1

            failures += 0 if assert_true(parsed.get("uuid") == item.uuid, ok=f"[{idx}] json uuid matches",
                                         fail=f"[{idx}] json uuid mismatch: file={parsed.get('uuid')} expected={item.uuid}") else 1

        if md_path.exists():
            content = md_path.read_text(encoding="utf-8")
            failures += 0 if assert_true(len(content.strip()) > 0, ok=f"[{idx}] markdown non-empty",
                                         fail=f"[{idx}] markdown empty") else 1
            failures += 0 if assert_true(content.lstrip().startswith("# "), ok=f"[{idx}] markdown starts with H1",
                                         fail=f"[{idx}] markdown does not start with H1") else 1

        if pdf_path.exists():
            failures += 0 if assert_true(pdf_path.stat().st_size > 0, ok=f"[{idx}] pdf non-empty",
                                         fail=f"[{idx}] pdf empty") else 1

    if failures == 0:
        print_ok("CV full pipeline checks passed")
        return 0

    print_fail(f"CV full pipeline checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
