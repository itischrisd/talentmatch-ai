from __future__ import annotations

from pydantic import BaseModel


class DatasetPrompts(BaseModel):
    cv_json_to_markdown: str
    rfp_json_to_markdown: str


class Prompts(BaseModel):
    datasets: DatasetPrompts
