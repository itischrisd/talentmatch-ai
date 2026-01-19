from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Mapping


@dataclass(frozen=True)
class GenerateAssignmentsForRfpResult:
    rfp_uuid: str
    assignment_struct: Mapping[str, Any]


class AssignmentStructGenerator:
    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._policy = settings.datasets.assignments

        self._cv_levels = list(settings.datasets.cv.skills.proficiency.levels)
        self._rfp_levels = list(settings.datasets.rfp.catalog.proficiency_levels)

        self._cv_rank = self._build_normalized_rank(self._cv_levels)
        self._rfp_rank = self._build_normalized_rank(self._rfp_levels)

    def generate_for_rfp(
            self,
            *,
            rfp_struct: Mapping[str, Any],
            programmers: list[Mapping[str, Any]],
            programmer_assignments: dict[str, list[tuple[date, date]]],
    ) -> GenerateAssignmentsForRfpResult:
        rfp_uuid = str(rfp_struct.get("uuid", "")).strip()
        if not rfp_uuid:
            raise ValueError("rfp_struct.uuid is required")

        team_size = int(rfp_struct.get("team_size", 0) or 0)
        start_date = date.fromisoformat(str(rfp_struct.get("start_date")))
        duration_months = int(rfp_struct.get("duration_months", 0) or 0)
        end_date = start_date + timedelta(days=max(1, duration_months) * int(self._policy.month_to_days))

        technical = self._as_mapping(rfp_struct.get("technical_requirements", {}))
        required_skills = self._as_list(technical.get("required_skills", []))
        mandatory_requirements = [self._as_mapping(x) for x in required_skills if
                                  self._as_mapping(x).get("is_mandatory")]

        skipped_by_probability = random.random() > float(self._policy.assignment_probability)
        if skipped_by_probability:
            struct = self._build_assignment_struct(
                rfp_uuid=rfp_uuid,
                rfp_start_date=start_date,
                rfp_end_date=end_date,
                team_size=team_size,
                mandatory_requirements=mandatory_requirements,
                assignments=[],
                skipped_by_probability=True,
            )
            return GenerateAssignmentsForRfpResult(rfp_uuid=rfp_uuid, assignment_struct=struct)

        max_assignments = min(max(0, team_size), len(programmers))

        eligible: list[Mapping[str, Any]] = []
        for programmer in programmers:
            programmer_uuid = str(programmer.get("uuid", "")).strip()
            if not programmer_uuid:
                continue
            if not self._matches_all_mandatory(programmer, mandatory_requirements):
                continue
            if not self._is_available(programmer_uuid, start_date, end_date, programmer_assignments):
                continue
            eligible.append(programmer)

        selected = random.sample(eligible,
                                 k=min(max_assignments, len(eligible))) if eligible and max_assignments > 0 else []

        assignments: list[dict[str, Any]] = []
        for programmer in selected:
            programmer_uuid = str(programmer.get("uuid", "")).strip()
            days_before_end = self._pick_days_before_end(start_date=start_date, end_date=end_date)
            assignment_end_date = end_date - timedelta(days=days_before_end)

            record = {
                "programmer_uuid": programmer_uuid,
                "rfp_uuid": rfp_uuid,
                "assignment_start_date": start_date.isoformat(),
                "assignment_end_date": assignment_end_date.isoformat(),
                "end_days_before_rfp_end": days_before_end,
                "allocation_percent": self._pick_allocation_percent(),
                "mandatory_requirements": self._requirements_snapshot(mandatory_requirements),
            }
            assignments.append(record)

            programmer_assignments.setdefault(programmer_uuid, []).append((start_date, assignment_end_date))

        struct = self._build_assignment_struct(
            rfp_uuid=rfp_uuid,
            rfp_start_date=start_date,
            rfp_end_date=end_date,
            team_size=team_size,
            mandatory_requirements=mandatory_requirements,
            assignments=assignments,
            skipped_by_probability=False,
        )
        return GenerateAssignmentsForRfpResult(rfp_uuid=rfp_uuid, assignment_struct=struct)

    def _matches_all_mandatory(self, programmer: Mapping[str, Any],
                               mandatory_requirements: list[Mapping[str, Any]]) -> bool:
        skills = self._as_list(programmer.get("skills", []))
        skills_by_name: dict[str, str] = {}
        for item in skills:
            m = self._as_mapping(item)
            name = str(m.get("name", "")).strip()
            prof = str(m.get("proficiency", "")).strip()
            if name and prof:
                skills_by_name[name] = prof

        for req in mandatory_requirements:
            skill_name = str(req.get("skill_name", "")).strip()
            min_prof = str(req.get("min_proficiency", "")).strip()
            if not skill_name or not min_prof:
                return False
            prog_prof = skills_by_name.get(skill_name)
            if prog_prof is None:
                return False
            if not self._meets_proficiency(programmer_level=prog_prof, required_level=min_prof):
                return False

        return True

    def _meets_proficiency(self, *, programmer_level: str, required_level: str) -> bool:
        prog = self._cv_rank.get(programmer_level)
        req = self._rfp_rank.get(required_level)
        if prog is None or req is None:
            return False
        return float(prog) >= float(req)

    @staticmethod
    def _build_normalized_rank(levels: list[str]) -> dict[str, float]:
        unique = [str(x) for x in levels if isinstance(x, str) and str(x).strip()]
        if not unique:
            return {}
        if len(unique) == 1:
            return {unique[0]: 1.0}
        return {lvl: i / (len(unique) - 1) for i, lvl in enumerate(unique)}

    @staticmethod
    def _is_available(
            programmer_uuid: str,
            start_date: date,
            end_date: date,
            programmer_assignments: dict[str, list[tuple[date, date]]],
    ) -> bool:
        periods = programmer_assignments.get(programmer_uuid, [])
        for a_start, a_end in periods:
            if not (end_date < a_start or start_date > a_end):
                return False
        return True

    def _pick_days_before_end(self, *, start_date: date, end_date: date) -> int:
        raw = random.randint(int(self._policy.assignment_end_days_before_min),
                             int(self._policy.assignment_end_days_before_max))
        duration_days = (end_date - start_date).days
        return min(int(raw), max(1, duration_days - 1))

    @staticmethod
    def _pick_allocation_percent() -> int:
        return int(random.choice((10, 20, 30, 40, 50, 60, 70, 80, 90, 100)))

    @staticmethod
    def _requirements_snapshot(mandatory_requirements: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        snapshot: list[dict[str, Any]] = []
        for req in mandatory_requirements:
            snapshot.append(
                {
                    "skill_name": str(req.get("skill_name", "")).strip(),
                    "min_proficiency": str(req.get("min_proficiency", "")).strip(),
                    "is_mandatory": bool(req.get("is_mandatory", True)),
                }
            )
        return snapshot

    def _build_assignment_struct(
            self,
            *,
            rfp_uuid: str,
            rfp_start_date: date,
            rfp_end_date: date,
            team_size: int,
            mandatory_requirements: list[Mapping[str, Any]],
            assignments: list[dict[str, Any]],
            skipped_by_probability: bool,
    ) -> dict[str, Any]:
        return {
            "schema_version": self._policy.schema_version,
            "rfp_uuid": rfp_uuid,
            "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "rfp_start_date": rfp_start_date.isoformat(),
            "rfp_end_date": rfp_end_date.isoformat(),
            "team_size": int(team_size),
            "assignment_probability": float(self._policy.assignment_probability),
            "skipped_by_probability": bool(skipped_by_probability),
            "mandatory_requirements": self._requirements_snapshot(
                [self._as_mapping(x) for x in mandatory_requirements]),
            "assignments": assignments,
        }

    @staticmethod
    def _as_mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        return list(value) if isinstance(value, list) else []

    @staticmethod
    def dumps_pretty(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False)
