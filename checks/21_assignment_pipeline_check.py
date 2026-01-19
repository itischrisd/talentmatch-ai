from __future__ import annotations

from pathlib import Path

from util.common import assert_true, build_check_context, load_settings_from_context, print_fail, print_ok
from talentmatch.datasets import AssignmentPipeline, CvStructJsonStore, RfpStructJsonStore


def run() -> int:
    context = build_check_context(Path(__file__))
    settings = load_settings_from_context(context)
    if settings is None:
        return 1

    cv_store = CvStructJsonStore(settings)
    rfp_store = RfpStructJsonStore(settings)

    cv_uuids = [
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    ]
    rfp_uuids = [
        "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    ]

    cv_levels = list(settings.datasets.cv.skills.proficiency.levels)
    rfp_levels = list(settings.datasets.rfp.catalog.proficiency_levels)

    low_cv = cv_levels[0] if cv_levels else "Beginner"
    high_cv = cv_levels[-1] if cv_levels else "Expert"
    req_prof = rfp_levels[0] if rfp_levels else "Beginner"

    skill = "Python"
    if settings.datasets.rfp.catalog.skills:
        skill = settings.datasets.rfp.catalog.skills[0]

    cvs = [
        {
            "uuid": cv_uuids[0],
            "schema_version": settings.datasets.cv.schema_version,
            "person": {"name": "A", "email": "a@x", "location": "PL", "seniority": "mid", "headline": "X", "links": []},
            "summary": "X",
            "skills": [{"name": skill, "proficiency": high_cv}],
            "certifications": [],
            "experience": [],
            "projects": [],
            "education": [],
        },
        {
            "uuid": cv_uuids[1],
            "schema_version": settings.datasets.cv.schema_version,
            "person": {"name": "B", "email": "b@x", "location": "PL", "seniority": "mid", "headline": "X", "links": []},
            "summary": "X",
            "skills": [{"name": skill, "proficiency": low_cv}],
            "certifications": [],
            "experience": [],
            "projects": [],
            "education": [],
        },
        {
            "uuid": cv_uuids[2],
            "schema_version": settings.datasets.cv.schema_version,
            "person": {"name": "C", "email": "c@x", "location": "PL", "seniority": "mid", "headline": "X", "links": []},
            "summary": "X",
            "skills": [{"name": skill, "proficiency": high_cv}],
            "certifications": [],
            "experience": [],
            "projects": [],
            "education": [],
        },
    ]

    rfps = [
        {
            "uuid": rfp_uuids[0],
            "schema_version": settings.datasets.rfp.schema_version,
            "rfp_id": "RFP-X",
            "title": "T",
            "client": "C",
            "domain": "D",
            "project_type": "P",
            "contract_type": "CT",
            "location": "L",
            "remote_mode": "Remote",
            "remote_allowed": True,
            "budget_range": "B",
            "start_date": "2030-01-10",
            "duration_months": 6,
            "team_size": 2,
            "staffing_profile": [],
            "executive_summary": "X",
            "business_context": "X",
            "objectives": [],
            "technical_requirements": {
                "required_skills": [{"skill_name": skill, "min_proficiency": req_prof, "is_mandatory": True,
                                     "preferred_certifications": []}],
                "preferred_skills": [],
            },
            "experience_requirements": {
                "min_total_years": 5,
                "min_relevant_years": 3,
                "preferred_seniority": "senior",
                "description": "Minimum 5+ years of overall professional experience, including at least 3+ years relevant to the domain and project type.",
            },
            "deliverables": [],
            "milestones": [],
            "acceptance_criteria": [],
            "proposal_submission_guidelines": [],
            "evaluation_process": "X",
            "contact_information": {"name": "X", "email": "X", "phone": "X"},
        },
        {
            "uuid": rfp_uuids[1],
            "schema_version": settings.datasets.rfp.schema_version,
            "rfp_id": "RFP-Y",
            "title": "T",
            "client": "C",
            "domain": "D",
            "project_type": "P",
            "contract_type": "CT",
            "location": "L",
            "remote_mode": "Remote",
            "remote_allowed": True,
            "budget_range": "B",
            "start_date": "2030-02-10",
            "duration_months": 4,
            "team_size": 1,
            "staffing_profile": [],
            "executive_summary": "X",
            "business_context": "X",
            "objectives": [],
            "technical_requirements": {
                "required_skills": [{"skill_name": skill, "min_proficiency": req_prof, "is_mandatory": True,
                                     "preferred_certifications": []}],
                "preferred_skills": [],
            },
            "experience_requirements": {
                "min_total_years": 4,
                "min_relevant_years": 2,
                "preferred_seniority": "mid",
                "description": "Minimum 4+ years of overall professional experience, including at least 2+ years relevant to the domain and project type.",
            },
            "deliverables": [],
            "milestones": [],
            "acceptance_criteria": [],
            "proposal_submission_guidelines": [],
            "evaluation_process": "X",
            "contact_information": {"name": "X", "email": "X", "phone": "X"},
        },
    ]

    for cv in cvs:
        cv_store.store(cv["uuid"], cv)

    for rfp in rfps:
        rfp_store.store(rfp["uuid"], rfp)

    pipeline = AssignmentPipeline(settings)
    results = pipeline.staff_for_uuids(rfp_uuids=rfp_uuids, programmer_uuids=cv_uuids)

    failures = 0
    failures += 0 if assert_true(len(results) <= len(rfp_uuids), ok="results size ok",
                                 fail="results size invalid") else 1

    assignments_dir = Path(settings.paths.assignments_struct_json_dir)
    for rfp_uuid in rfp_uuids:
        out_path = assignments_dir / f"{rfp_uuid}.json"
        failures += 0 if assert_true(out_path.exists(), ok=f"assignment file exists for {rfp_uuid}",
                                     fail=f"missing assignment file for {rfp_uuid}") else 1
        if out_path.exists():
            payload = out_path.read_text(encoding="utf-8")
            failures += 0 if assert_true(len(payload) > 0, ok=f"assignment file non-empty for {rfp_uuid}",
                                         fail=f"assignment file empty for {rfp_uuid}") else 1

    if failures == 0:
        print_ok("Assignment pipeline checks passed")
        return 0

    print_fail(f"Assignment pipeline checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
