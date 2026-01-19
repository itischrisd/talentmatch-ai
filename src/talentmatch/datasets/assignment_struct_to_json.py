from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class StoreAssignmentStructJsonResult:
    rfp_uuid: str


class AssignmentStructJsonStore:
    def __init__(self, settings: Any) -> None:
        self._base_dir = Path(settings.paths.assignments_struct_json_dir)

    def store(self, rfp_uuid: str, assignment_struct: Mapping[str, Any]) -> StoreAssignmentStructJsonResult:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._base_dir / f"{rfp_uuid}.json"

        with file_path.open("w", encoding="utf-8") as f:
            json.dump(assignment_struct, f, ensure_ascii=False, indent=2)

        return StoreAssignmentStructJsonResult(rfp_uuid=rfp_uuid)
