from __future__ import annotations

from pydantic import BaseModel


class LoggingConfig(BaseModel):
    format: str
    date_format: str
    level_default: str
