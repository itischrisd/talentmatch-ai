from __future__ import annotations

from pydantic import BaseModel


class DatasetPrompts(BaseModel):
    rfp_json_to_markdown: str


class Prompts(BaseModel):
    datasets: DatasetPrompts
