from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping

from util.common import (
    assert_between,
    assert_in,
    assert_json_serializable,
    assert_true,
    assert_uuid,
    build_check_context,
    load_settings_from_context,
    print_fail,
    print_ok,
)
from talentmatch.datasets import StructuredRfpGenerator


def validate_skill_req(obj: Any, *, label: str, settings: Any) -> int:
    failures = 0
    if not isinstance(obj, dict):
        return 1

    failures += 0 if assert_true(
        isinstance(obj.get("skill_name"), str) and obj["skill_name"].strip(),
        ok=f"{label}.skill_name ok",
        fail=f"{label}.skill_name invalid",
    ) else 1

    failures += 0 if assert_true(
        isinstance(obj.get("min_proficiency"), str) and obj["min_proficiency"].strip(),
        ok=f"{label}.min_proficiency ok",
        fail=f"{label}.min_proficiency invalid",
    ) else 1

    if isinstance(obj.get("min_proficiency"), str):
        failures += 0 if assert_in(
            obj["min_proficiency"],
            list(settings.datasets.rfp.catalog.proficiency_levels),
            label=f"{label}.min_proficiency",
        ) else 1

    failures += 0 if assert_true(
        isinstance(obj.get("is_mandatory"), bool),
        ok=f"{label}.is_mandatory ok",
        fail=f"{label}.is_mandatory invalid",
    ) else 1

    certs = obj.get("preferred_certifications")
    failures += 0 if assert_true(
        isinstance(certs, list),
        ok=f"{label}.preferred_certifications list",
        fail=f"{label}.preferred_certifications invalid",
    ) else 1

    if isinstance(certs, list):
        for i, c in enumerate(certs):
            failures += 0 if assert_true(
                isinstance(c, str) and c.strip(),
                ok=f"{label}.cert[{i}] ok",
                fail=f"{label}.cert[{i}] invalid",
            ) else 1

    return failures


def validate_rfp_shape(rfp: Mapping[str, Any], settings: Any) -> int:
    failures = 0
    p = settings.datasets.rfp

    failures += 0 if assert_true(isinstance(rfp, dict), ok="rfp_struct is dict", fail="rfp_struct is not dict") else 1

    uuid_value = rfp.get("uuid")
    failures += 0 if assert_true(isinstance(uuid_value, str), ok="uuid is str", fail="uuid is not str") else 1
    if isinstance(uuid_value, str):
        failures += 0 if assert_uuid(uuid_value, label="uuid format") else 1

    failures += 0 if assert_true(
        rfp.get("schema_version") == p.schema_version,
        ok="schema_version matches settings",
        fail=f'schema_version mismatch: {rfp.get("schema_version")} != {p.schema_version}',
    ) else 1

    for key in ["rfp_id", "title", "client", "domain", "project_type"]:
        failures += 0 if assert_true(
            isinstance(rfp.get(key), str) and rfp[key].strip(),
            ok=f"{key} ok",
            fail=f"{key} invalid",
        ) else 1

    if isinstance(rfp.get("domain"), str):
        failures += 0 if assert_in(rfp["domain"], list(p.catalog.domains), label="domain") else 1
    if isinstance(rfp.get("project_type"), str):
        failures += 0 if assert_in(rfp["project_type"], list(p.catalog.project_types), label="project_type") else 1

    start_date_raw = rfp.get("start_date")
    failures += 0 if assert_true(
        isinstance(start_date_raw, str) and start_date_raw.strip(),
        ok="start_date is str",
        fail="start_date invalid",
    ) else 1

    if isinstance(start_date_raw, str):
        try:
            start_date_value = date.fromisoformat(start_date_raw)
            today = date.today()
            min_date = today.fromordinal(today.toordinal() + p.text.start_date_min_days)
            max_date = today.fromordinal(today.toordinal() + p.text.start_date_max_days)
            failures += 0 if assert_true(
                min_date <= start_date_value <= max_date,
                ok="start_date within configured bounds",
                fail=f"start_date out of bounds: {start_date_value} not in [{min_date}, {max_date}]",
            ) else 1
        except Exception as exc:
            failures += 0 if assert_true(False, ok="", fail=f"start_date parse failed: {exc}") else 1

    duration_months = rfp.get("duration_months")
    failures += 0 if assert_true(isinstance(duration_months, int), ok="duration_months is int",
                                 fail="duration_months is not int") else 1
    if isinstance(duration_months, int):
        failures += 0 if assert_between(
            duration_months,
            min_value=p.text.duration_months_min,
            max_value=p.text.duration_months_max,
            label="duration_months",
        ) else 1

    for key in ["contract_type", "location", "remote_mode", "budget_range"]:
        failures += 0 if assert_true(
            isinstance(rfp.get(key), str) and rfp[key].strip(),
            ok=f"{key} ok",
            fail=f"{key} invalid",
        ) else 1

    remote_allowed = rfp.get("remote_allowed")
    failures += 0 if assert_true(isinstance(remote_allowed, bool), ok="remote_allowed is bool",
                                 fail="remote_allowed invalid") else 1

    team_size = rfp.get("team_size")
    failures += 0 if assert_true(isinstance(team_size, int), ok="team_size is int", fail="team_size invalid") else 1
    if isinstance(team_size, int):
        failures += 0 if assert_between(
            team_size,
            min_value=p.text.team_size_min,
            max_value=p.text.team_size_max,
            label="team_size",
        ) else 1

    staffing = rfp.get("staffing_profile")
    failures += 0 if assert_true(isinstance(staffing, list), ok="staffing_profile is list",
                                 fail="staffing_profile invalid") else 1
    if isinstance(staffing, list) and isinstance(team_size, int):
        total = 0
        for i, item in enumerate(staffing):
            label = f"staffing_profile[{i}]"
            failures += 0 if assert_true(isinstance(item, dict), ok=f"{label} is dict", fail=f"{label} invalid") else 1
            if isinstance(item, dict):
                failures += 0 if assert_true(isinstance(item.get("role"), str) and item["role"].strip(),
                                             ok=f"{label}.role ok", fail=f"{label}.role invalid") else 1
                failures += 0 if assert_true(isinstance(item.get("count"), int) and item["count"] > 0,
                                             ok=f"{label}.count ok", fail=f"{label}.count invalid") else 1
                failures += 0 if assert_true(isinstance(item.get("seniority"), str) and item["seniority"].strip(),
                                             ok=f"{label}.seniority ok", fail=f"{label}.seniority invalid") else 1
                failures += 0 if assert_true(isinstance(item.get("key_skills"), list), ok=f"{label}.key_skills list",
                                             fail=f"{label}.key_skills invalid") else 1
                failures += 0 if assert_true(isinstance(item.get("responsibilities"), list),
                                             ok=f"{label}.responsibilities list",
                                             fail=f"{label}.responsibilities invalid") else 1
                if isinstance(item.get("count"), int):
                    total += item["count"]

        failures += 0 if assert_true(total == team_size, ok="staffing counts sum to team_size",
                                     fail=f"staffing counts do not sum to team_size: {total} != {team_size}") else 1

    for key in ["executive_summary", "business_context"]:
        failures += 0 if assert_true(isinstance(rfp.get(key), str) and rfp[key].strip(), ok=f"{key} ok",
                                     fail=f"{key} invalid") else 1

    objectives = rfp.get("objectives")
    failures += 0 if assert_true(isinstance(objectives, list), ok="objectives is list",
                                 fail="objectives invalid") else 1
    if isinstance(objectives, list):
        failures += 0 if assert_between(
            len(objectives),
            min_value=p.text.objectives_min_count,
            max_value=p.text.objectives_max_count,
            label="objectives count",
        ) else 1

    tech = rfp.get("technical_requirements")
    failures += 0 if assert_true(isinstance(tech, dict), ok="technical_requirements is dict",
                                 fail="technical_requirements invalid") else 1
    if isinstance(tech, dict):
        req = tech.get("required_skills")
        pref = tech.get("preferred_skills")
        failures += 0 if assert_true(isinstance(req, list), ok="required_skills is list",
                                     fail="required_skills invalid") else 1
        failures += 0 if assert_true(isinstance(pref, list), ok="preferred_skills is list",
                                     fail="preferred_skills invalid") else 1

        if isinstance(req, list):
            failures += 0 if assert_between(
                len(req),
                min_value=p.text.required_skills_min_count,
                max_value=p.text.required_skills_max_count,
                label="required_skills count",
            ) else 1
            for i, obj in enumerate(req):
                failures += validate_skill_req(obj, label=f"required_skills[{i}]", settings=settings)

        if isinstance(pref, list):
            failures += 0 if assert_between(
                len(pref),
                min_value=p.text.preferred_skills_min_count,
                max_value=p.text.preferred_skills_max_count,
                label="preferred_skills count",
            ) else 1
            for i, obj in enumerate(pref):
                failures += validate_skill_req(obj, label=f"preferred_skills[{i}]", settings=settings)

    deliverables = rfp.get("deliverables")
    failures += 0 if assert_true(isinstance(deliverables, list), ok="deliverables is list",
                                 fail="deliverables invalid") else 1
    if isinstance(deliverables, list):
        failures += 0 if assert_between(
            len(deliverables),
            min_value=p.text.deliverables_min_count,
            max_value=p.text.deliverables_max_count,
            label="deliverables count",
        ) else 1

    milestones = rfp.get("milestones")
    failures += 0 if assert_true(isinstance(milestones, list), ok="milestones is list",
                                 fail="milestones invalid") else 1
    if isinstance(milestones, list):
        failures += 0 if assert_between(
            len(milestones),
            min_value=p.text.milestones_min_count,
            max_value=p.text.milestones_max_count,
            label="milestones count",
        ) else 1

    for key in ["acceptance_criteria", "proposal_submission_guidelines"]:
        failures += 0 if assert_true(isinstance(rfp.get(key), list), ok=f"{key} is list", fail=f"{key} invalid") else 1

    failures += 0 if assert_true(isinstance(rfp.get("evaluation_process"), str) and rfp["evaluation_process"].strip(),
                                 ok="evaluation_process ok", fail="evaluation_process invalid") else 1
    failures += 0 if assert_true(isinstance(rfp.get("contact_information"), dict), ok="contact_information is dict",
                                 fail="contact_information invalid") else 1

    failures += 0 if assert_json_serializable(rfp, label="rfp_struct", sort_keys=True) else 1
    return failures


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
        result = generator.generate_one()
        print_ok("generate_one() succeeded")
    except Exception as exc:
        print_fail(f"generate_one() failed: {exc}")
        return 1

    failures = validate_rfp_shape(result.rfp_struct, settings)

    try:
        batch = generator.generate_many(count=3)
        print_ok("generate_many(count=3) succeeded")
    except Exception as exc:
        print_fail(f"generate_many(count=3) failed: {exc}")
        return 1

    failures += 0 if assert_true(len(batch) == 3, ok="batch size ok (3)",
                                 fail=f"batch size invalid: {len(batch)}") else 1
    failures += 0 if assert_true(len({item.uuid for item in batch}) == 3, ok="batch UUIDs are unique",
                                 fail="batch UUIDs are not unique") else 1

    if failures == 0:
        print_ok("RFP structured generator checks passed")
        return 0

    print_fail(f"RFP structured generator checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
