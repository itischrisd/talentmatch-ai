from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from talentmatch.datasets import RfpStructJsonStore, StructuredRfpGenerator
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
