from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class StoreCvStructJsonResult:
    """Result of storing structured CV as JSON."""
    uuid: str


class CvStructJsonStore:
    """Stores a structured CV as a JSON file under a UUID-based name."""

    def __init__(self, settings: Any) -> None:
        self._base_dir = Path(settings.paths.cv_struct_json_dir)

    def store(self, uuid: str, cv_struct: Mapping[str, Any]) -> StoreCvStructJsonResult:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._base_dir / f"{uuid}.json"

        with file_path.open("w", encoding="utf-8") as f:
            json.dump(cv_struct, f, ensure_ascii=False, indent=2)

        return StoreCvStructJsonResult(uuid=uuid)
