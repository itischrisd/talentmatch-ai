from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .assignment_struct_generator import AssignmentStructGenerator
from .assignment_struct_to_json import AssignmentStructJsonStore


@dataclass(frozen=True)
class StaffRfpResult:
    rfp_uuid: str
    assignments_count: int
    skipped: bool


class AssignmentPipeline:
    def __init__(
            self,
            settings: Any,
            *,
            generator: AssignmentStructGenerator | None = None,
            json_store: AssignmentStructJsonStore | None = None,
    ) -> None:
        self._settings = settings
        self._policy = settings.datasets.assignments
        self._generator = generator or AssignmentStructGenerator(settings)
        self._json_store = json_store or AssignmentStructJsonStore(settings)

        self._rfp_dir = Path(settings.paths.rfp_struct_json_dir)
        self._cv_dir = Path(settings.paths.cv_struct_json_dir)
        self._assignments_dir = Path(settings.paths.assignments_struct_json_dir)

    def staff_for_uuids(self, *, rfp_uuids: list[str], programmer_uuids: list[str]) -> list[StaffRfpResult]:
        rfps = self._load_many(self._rfp_dir, rfp_uuids)
        programmers = self._load_many(self._cv_dir, programmer_uuids)

        existing_periods = self._build_existing_programmer_periods()
        results: list[StaffRfpResult] = []

        for rfp in rfps:
            rfp_uuid = str(rfp.get("uuid", "")).strip()
            if not rfp_uuid:
                continue
            if self._has_staffing(rfp_uuid):
                continue

            gen = self._generator.generate_for_rfp(
                rfp_struct=rfp,
                programmers=programmers,
                programmer_assignments=existing_periods,
            )
            self._json_store.store(gen.rfp_uuid, gen.assignment_struct)

            assignments = self._as_list(self._as_mapping(gen.assignment_struct).get("assignments", []))
            skipped = bool(self._as_mapping(gen.assignment_struct).get("skipped_by_probability", False))
            results.append(StaffRfpResult(rfp_uuid=gen.rfp_uuid, assignments_count=len(assignments), skipped=skipped))

        return results

    def staff_all_missing(self) -> list[StaffRfpResult]:
        rfps = self._load_all(self._rfp_dir)
        programmers = self._load_all(self._cv_dir)

        existing_periods = self._build_existing_programmer_periods()
        results: list[StaffRfpResult] = []

        for rfp in rfps:
            rfp_uuid = str(rfp.get("uuid", "")).strip()
            if not rfp_uuid:
                continue
            if self._has_staffing(rfp_uuid):
                continue

            gen = self._generator.generate_for_rfp(
                rfp_struct=rfp,
                programmers=programmers,
                programmer_assignments=existing_periods,
            )
            self._json_store.store(gen.rfp_uuid, gen.assignment_struct)

            assignments = self._as_list(self._as_mapping(gen.assignment_struct).get("assignments", []))
            skipped = bool(self._as_mapping(gen.assignment_struct).get("skipped_by_probability", False))
            results.append(StaffRfpResult(rfp_uuid=gen.rfp_uuid, assignments_count=len(assignments), skipped=skipped))

        return results

    def _has_staffing(self, rfp_uuid: str) -> bool:
        return (self._assignments_dir / f"{rfp_uuid}.json").exists()

    def _build_existing_programmer_periods(self) -> dict[str, list[tuple[Any, Any]]]:
        from datetime import date

        periods: dict[str, list[tuple[date, date]]] = {}

        if not self._assignments_dir.exists():
            return periods

        for path in sorted(self._assignments_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            assignments = self._as_list(self._as_mapping(payload).get("assignments", []))
            for item in assignments:
                m = self._as_mapping(item)
                programmer_uuid = str(m.get("programmer_uuid", "")).strip()
                start_s = str(m.get("assignment_start_date", "")).strip()
                end_s = str(m.get("assignment_end_date", "")).strip()
                if not programmer_uuid or not start_s or not end_s:
                    continue
                try:
                    start_d = date.fromisoformat(start_s)
                    end_d = date.fromisoformat(end_s)
                except Exception:
                    continue
                periods.setdefault(programmer_uuid, []).append((start_d, end_d))

        for key in list(periods.keys()):
            periods[key] = sorted(periods[key], key=lambda x: x[0])

        return periods

    @staticmethod
    def _load_many(base_dir: Path, uuids: list[str]) -> list[Mapping[str, Any]]:
        out: list[Mapping[str, Any]] = []
        for uuid in uuids:
            path = base_dir / f"{uuid}.json"
            if not path.exists():
                continue
            try:
                out.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out

    @staticmethod
    def _load_all(base_dir: Path) -> list[Mapping[str, Any]]:
        if not base_dir.exists():
            return []
        out: list[Mapping[str, Any]] = []
        for path in sorted(base_dir.glob("*.json")):
            try:
                out.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out

    @staticmethod
    def _as_mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        return list(value) if isinstance(value, list) else []
