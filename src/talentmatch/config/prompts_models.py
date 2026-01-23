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
    Labels for remote work modes
    """

    allowed: str
    not_allowed: str


class DatasetPrompts(BaseModel):
    """
    Prompt templates for dataset generation
    """

    cv_markdown: str
    rfp_markdown: str
    requirement_labels: RequirementLabels
    remote_work_labels: RemoteWorkLabels


class AgentsPrompts(BaseModel):
    """
    Prompt templates for the supervisor system and its worker agents.
    """

    generation_react: str
    kg_react: str
    query_react: str
    supervisor: str


class KnowledgeGraphPrompts(BaseModel):
    """
    Prompt templates for knowledge graph querying.
    """

    cypher_generation: str
    answer_json: str


class VectorStorePrompts(BaseModel):
    """
    Prompt templates for vector store querying and staffing.
    """

    answer_json: str
    staffing_json: str


class Prompts(BaseModel):
    """
    Prompts root model
    """

    datasets: DatasetPrompts
    agents: AgentsPrompts
    knowledge_graph: KnowledgeGraphPrompts
    vector_store: VectorStorePrompts
