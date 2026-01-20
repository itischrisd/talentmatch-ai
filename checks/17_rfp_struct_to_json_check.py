from __future__ import annotations

import json
from pathlib import Path

from util.common import assert_true, build_check_context, is_uuid, load_settings_from_context, print_fail, print_ok
from talentmatch.generation import RfpStructJsonStore, StructuredRfpGenerator


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
        store = RfpStructJsonStore(settings)
        print_ok("RfpStructJsonStore(settings) succeeded")
    except Exception as exc:
        print_fail(f"RfpStructJsonStore(settings) failed: {exc}")
        return 1

    base_dir = Path(settings.paths.rfp_struct_json_dir)
    json_path = base_dir / f"{rfp_result.uuid}.json"

    try:
        store.store(rfp_result.uuid, rfp_result.rfp_struct)
        print_ok("store(uuid, rfp_struct) succeeded")
    except Exception as exc:
        print_fail(f"store(uuid, rfp_struct) failed: {exc}")
        return 1

    failures += 0 if assert_true(json_path.exists(), ok="json file exists",
                                 fail=f'json file not found: "{json_path}"') else 1

    try:
        parsed = json.loads(json_path.read_text(encoding="utf-8"))
        print_ok("json file parse succeeded")
    except Exception as exc:
        print_fail(f"json file parse failed: {exc}")
        return 1

    failures += 0 if assert_true(parsed.get("uuid") == rfp_result.uuid, ok="json uuid matches",
                                 fail=f'json uuid mismatch: file={parsed.get("uuid")} expected={rfp_result.uuid}') else 1
    failures += 0 if assert_true(parsed.get("schema_version") == settings.datasets.rfp.schema_version,
                                 ok="schema_version matches", fail="schema_version mismatch") else 1

    required_keys = [
        "uuid",
        "schema_version",
        "rfp_id",
        "title",
        "client",
        "domain",
        "project_type",
        "contract_type",
        "location",
        "remote_mode",
        "remote_allowed",
        "budget_range",
        "start_date",
        "duration_months",
        "team_size",
        "staffing_profile",
        "executive_summary",
        "business_context",
        "objectives",
        "technical_requirements",
        "experience_requirements",
        "deliverables",
        "milestones",
        "acceptance_criteria",
        "proposal_submission_guidelines",
        "evaluation_process",
        "contact_information",
    ]

    for key in required_keys:
        failures += 0 if assert_true(key in parsed, ok=f'top-level key present: "{key}"',
                                     fail=f'top-level key missing: "{key}"') else 1

    try:
        store.store(rfp_result.uuid, rfp_result.rfp_struct)
        print_ok("overwrite store() succeeded")
    except Exception as exc:
        print_fail(f"overwrite store() failed: {exc}")
        return 1

    failures += 0 if assert_true(json_path.exists(), ok="json file still exists after overwrite",
                                 fail="json file missing after overwrite") else 1

    if failures == 0:
        print_ok("RFP struct -> JSON checks passed")
        return 0

    print_fail(f"RFP struct -> JSON checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
