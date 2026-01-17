from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from talentmatch.datasets import CvMarkdownPdfStore
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
        store = CvMarkdownPdfStore(settings)
        print_ok("CvMarkdownPdfStore(settings) succeeded")
    except Exception as exc:
        print_fail(f"CvMarkdownPdfStore(settings) failed: {exc}")
        return 1

    uuid = "11111111-1111-4111-8111-111111111111"
    markdown = "\n".join(
        [
            "# Jan Kowalski",
            "Senior Python Developer",
            "",
            "## Skills",
            "- Python",
            "- FastAPI",
            "- PostgreSQL",
            "",
            "## Summary",
            "Doświadczony inżynier oprogramowania z naciskiem na backend i dane.",
        ]
    )

    failures = 0
    base_dir = Path(settings.paths.cv_pdf_dir)
    pdf_path = base_dir / f"{uuid}.pdf"

    try:
        result = store.store(uuid, markdown)
        print_ok("store(uuid, markdown) succeeded")
    except Exception as exc:
        print_fail(f"store(uuid, markdown) failed: {exc}")
        return 1

    failures += 0 if assert_true(is_uuid(result.uuid), ok="result uuid format ok",
                                 fail=f"result uuid invalid: {result.uuid}") else 1
    failures += 0 if assert_true(pdf_path.exists(), ok="pdf file exists",
                                 fail=f'pdf file not found: "{pdf_path}"') else 1
    failures += 0 if assert_true(pdf_path.stat().st_size > 0, ok="pdf file non-empty",
                                 fail="pdf file is empty") else 1

    try:
        store.store(uuid, markdown)
        print_ok("overwrite store() succeeded")
    except Exception as exc:
        print_fail(f"overwrite store() failed: {exc}")
        return 1

    failures += 0 if assert_true(pdf_path.exists(), ok="pdf file still exists after overwrite",
                                 fail="pdf file missing after overwrite") else 1

    if failures == 0:
        print_ok("Markdown -> PDF checks passed")
        return 0

    print_fail(f"Markdown -> PDF checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
