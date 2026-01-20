from __future__ import annotations

from pathlib import Path

from util.common import assert_true, build_check_context, is_uuid, load_settings_from_context, print_fail, print_ok
from talentmatch.generation import RfpStructMarkdownStore, StructuredRfpGenerator


def run() -> int:
    context = build_check_context(Path(__file__))
    settings = load_settings_from_context(context)
    if settings is None:
        return 1

    try:
        generator = StructuredRfpGenerator(settings)
        print_ok("StructuredRfpGenerator(settings) succeeded")
    except Exception as exc:
        print_fail(f"StructuredRfpGenerator(settings) failed: {exc}")
        return 1

    try:
        rfp_result = generator.generate_one()
        print_ok("generate_one() succeeded")
    except Exception as exc:
        print_fail(f"generate_one() failed: {exc}")
        return 1

    failures = 0
    failures += 0 if assert_true(is_uuid(rfp_result.uuid), ok="uuid format ok",
                                 fail=f"uuid invalid: {rfp_result.uuid}") else 1
    failures += 0 if assert_true(isinstance(rfp_result.rfp_struct, dict), ok="rfp_struct is dict",
                                 fail="rfp_struct is not dict") else 1

    try:
        store = RfpStructMarkdownStore(settings)
        print_ok("RfpStructMarkdownStore(settings) succeeded")
    except Exception as exc:
        print_fail(f"RfpStructMarkdownStore(settings) failed: {exc}")
        return 1

    base_dir = Path(settings.paths.rfp_markdown_dir)
    md_path = base_dir / f"{rfp_result.uuid}.md"

    try:
        store.store(rfp_result.uuid, rfp_result.rfp_struct)
        print_ok("store(uuid, rfp_struct) succeeded")
    except Exception as exc:
        print_fail(f"store(uuid, rfp_struct) failed: {exc}")
        return 1

    failures += 0 if assert_true(md_path.exists(), ok="markdown file exists",
                                 fail=f'markdown file not found: "{md_path}"') else 1

    if md_path.exists():
        content = md_path.read_text(encoding="utf-8")

        failures += 0 if assert_true(len(content.strip()) > 0, ok="markdown is non-empty",
                                     fail="markdown is empty") else 1
        failures += 0 if assert_true(content.lstrip().startswith("# "), ok="markdown starts with H1",
                                     fail="markdown does not start with H1") else 1
        failures += 0 if assert_true("```" not in content, ok="markdown has no code fences",
                                     fail="markdown contains code fences") else 1

        staffing = rfp_result.rfp_struct.get("staffing_profile")
        if isinstance(staffing, list):
            roles = [
                item.get("role")
                for item in staffing
                if isinstance(item, dict) and isinstance(item.get("role"), str) and item.get("role").strip()
            ]
            for role in roles[:3]:
                failures += 0 if assert_true(role in content, ok=f'role present in markdown: "{role}"',
                                             fail=f'role missing in markdown: "{role}"') else 1

    try:
        store.store(rfp_result.uuid, rfp_result.rfp_struct)
        print_ok("overwrite store() succeeded")
    except Exception as exc:
        print_fail(f"overwrite store() failed: {exc}")
        return 1

    failures += 0 if assert_true(md_path.exists(), ok="markdown file still exists after overwrite",
                                 fail="markdown file missing after overwrite") else 1

    if failures == 0:
        print_ok("RFP struct -> Markdown checks passed")
        return 0

    print_fail(f"RFP struct -> Markdown checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
