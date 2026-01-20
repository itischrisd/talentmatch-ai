from __future__ import annotations

from pydantic import BaseModel


class RequirementLabels(BaseModel):
    required: str
    preferred: str


class RemoteWorkLabels(BaseModel):
    allowed: str
    not_allowed: str


class DatasetPrompts(BaseModel):
    cv_markdown: str
    rfp_markdown: str
    requirement_labels: RequirementLabels
    remote_work_labels: RemoteWorkLabels


class Prompts(BaseModel):
    datasets: DatasetPrompts
