from __future__ import annotations

import json
from pathlib import Path

from common import assert_true, build_check_context, is_uuid, load_settings_from_context, print_fail, print_ok
from talentmatch.datasets import CvStructJsonStore, StructuredCvGenerator


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
        store = CvStructJsonStore(settings)
        print_ok("CvStructJsonStore(settings) succeeded")
    except Exception as exc:
        print_fail(f"CvStructJsonStore(settings) failed: {exc}")
        return 1

    base_dir = Path(settings.paths.cv_struct_json_dir)
    json_path = base_dir / f"{cv_result.uuid}.json"

    try:
        store.store(cv_result.uuid, cv_result.cv)
        print_ok("store(uuid, cv_struct) succeeded")
    except Exception as exc:
        print_fail(f"store(uuid, cv_struct) failed: {exc}")
        return 1

    failures += 0 if assert_true(json_path.exists(), ok="json file exists",
                                 fail=f'json file not found: "{json_path}"') else 1

    try:
        parsed = json.loads(json_path.read_text(encoding="utf-8"))
        print_ok("json file parse succeeded")
    except Exception as exc:
        print_fail(f"json file parse failed: {exc}")
        return 1

    failures += 0 if assert_true(parsed.get("uuid") == cv_result.uuid, ok="json uuid matches",
                                 fail=f'json uuid mismatch: file={parsed.get("uuid")} expected={cv_result.uuid}') else 1

    try:
        store.store(cv_result.uuid, cv_result.cv)
        print_ok("overwrite store() succeeded")
    except Exception as exc:
        print_fail(f"overwrite store() failed: {exc}")
        return 1

    failures += 0 if assert_true(json_path.exists(), ok="json file still exists after overwrite",
                                 fail="json file missing after overwrite") else 1

    if failures == 0:
        print_ok("CV struct -> JSON checks passed")
        return 0

    print_fail(f"CV struct -> JSON checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
