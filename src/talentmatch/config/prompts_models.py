from __future__ import annotations

from pydantic import BaseModel


class RequirementLabels(BaseModel):
    """
    Labels for requirements in RFPs
    """

    required: str
    preferred: str


class RemoteWorkLabels(BaseModel):
    """
    Labels for remote work policies in RFPs
    """

    allowed: str
    not_allowed: str


class DatasetPrompts(BaseModel):
    """
    Prompts templates for dataset generation
    """

    cv_markdown: str
    rfp_markdown: str
    requirement_labels: RequirementLabels
    remote_work_labels: RemoteWorkLabels


class AgentsPrompts(BaseModel):
    """
    Prompt templates for LangChain agents.
    These must be valid ReAct prompts for create_react_agent and include:
    {tools}, {tool_names}, {input}, {agent_scratchpad}
    """

    generation_react: str
    kg_react: str


class Prompts(BaseModel):
    """
    Prompts root model
    """

    datasets: DatasetPrompts
    agents: AgentsPrompts
