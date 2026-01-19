from __future__ import annotations

import json
import sys
from pathlib import Path

from common import build_check_context, load_settings_from_context, print_fail, print_ok
from talentmatch.datasets.assignment_pipeline import AssignmentPipeline
from talentmatch.datasets.cv_pipeline import CvArtifactsPipeline
from talentmatch.datasets.rfp_pipeline import RfpArtifactsPipeline


def run() -> int:
    context = build_check_context(Path(__file__) / "..")
    settings = load_settings_from_context(context)
    if settings is None:
        return 1

    cv_pipeline = CvArtifactsPipeline(settings)
    rfp_pipeline = RfpArtifactsPipeline(settings)
    assignment_pipeline = AssignmentPipeline(settings)

    cv_uuids: list[str] = []
    rfp_uuids: list[str] = []

    try:
        for i in range(1, 101):
            result = cv_pipeline.generate_one()
            cv_uuids.append(result.uuid)
            print(f"{i}/100 done")
            sys.stdout.flush()
    except Exception as exc:
        print_fail(f"CV generation failed: {exc}")
        return 1

    try:
        for i in range(1, 51):
            result = rfp_pipeline.generate_one()
            rfp_uuids.append(result.uuid)
            print(f"{i}/50 done")
            sys.stdout.flush()
    except Exception as exc:
        print_fail(f"RFP generation failed: {exc}")
        return 1

    assignments_dir = Path(settings.paths.assignments_struct_json_dir)
    assignments_dir.mkdir(parents=True, exist_ok=True)

    target_assignments = 80
    total_assignments = 0

    try:
        for rfp_uuid in rfp_uuids:
            if total_assignments >= target_assignments:
                break

            assignment_pipeline.staff_for_uuids(rfp_uuids=[rfp_uuid], programmer_uuids=cv_uuids)

            assignment_file = assignments_dir / f"{rfp_uuid}.json"
            if not assignment_file.exists():
                continue

            payload = _load_json(assignment_file)
            assignments = _ensure_list(payload.get("assignments"))

            remaining = target_assignments - total_assignments
            if remaining <= 0:
                break

            if len(assignments) > remaining:
                payload["assignments"] = assignments[:remaining]
                _write_json(assignment_file, payload)
                assignments = payload["assignments"]

            for _ in range(len(assignments)):
                total_assignments += 1
                print(f"{total_assignments}/{target_assignments} done")
                sys.stdout.flush()

            if total_assignments >= target_assignments:
                break
    except Exception as exc:
        print_fail(f"Assignments generation failed: {exc}")
        return 1

    if total_assignments != target_assignments:
        print_fail(f"Assignments count mismatch: {total_assignments}/{target_assignments}")
        return 1

    print_ok("Dataset generation finished")
    return 0


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_list(value) -> list:
    return list(value) if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(run())
