from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def ensure_dirs(*dirs: Path) -> None:
    """Ensure directories exist."""
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    """Write payload as pretty JSON."""
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def safe_filename(text: str) -> str:
    """Create a filesystem-friendly filename."""
    normalized = text.replace(" ", "_").replace("/", "_").replace("\\", "_")
    normalized = re.sub(r"[^\w.-]+", "", normalized, flags=re.UNICODE)
    return normalized.strip("._") or "document"
