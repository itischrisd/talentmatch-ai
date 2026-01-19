from __future__ import annotations

from pathlib import Path

from util.common import assert_true, build_check_context, is_uuid, load_settings_from_context, print_fail, print_ok
from talentmatch.datasets import CvStructMarkdownStore, StructuredCvGenerator


def run() -> int:
    context = build_check_context(Path(__file__))
    settings = load_settings_from_context(context)
    if settings is None:
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
