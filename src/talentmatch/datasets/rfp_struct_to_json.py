from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class StoreRfpStructJsonResult:
    """Result of storing a structured RFP as JSON."""
    uuid: str


class RfpStructJsonStore:
    """Stores structured RFP documents as JSON files under a configured base directory."""

    def __init__(self, settings: Any) -> None:
        self._base_dir = Path(settings.paths.rfp_struct_json_dir)

    def store(self, uuid: str, rfp_struct: Mapping[str, Any]) -> StoreRfpStructJsonResult:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._base_dir / f"{uuid}.json"
        payload = json.dumps(rfp_struct, ensure_ascii=False, indent=2, sort_keys=True)
        target_path.write_text(payload, encoding="utf-8")
        return StoreRfpStructJsonResult(uuid=uuid)
