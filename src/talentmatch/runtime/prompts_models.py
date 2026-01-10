from __future__ import annotations

from pydantic import BaseModel


class SystemPrompts(BaseModel):
    base: str


class CommandPrompts(BaseModel):
    router: str


class KnowledgeGraphPrompts(BaseModel):
    extraction_instructions: str


class GraphRagPrompts(BaseModel):
    cypher_generation: str
    answer_from_cypher_result: str


class RagPrompts(BaseModel):
    answer: str


class MatchingPrompts(BaseModel):
    judge_relevance: str
    explain: str


class BiPrompts(BaseModel):
    intent: str


class Prompts(BaseModel):
    system: SystemPrompts
    commands: CommandPrompts
    kg: KnowledgeGraphPrompts
    graphrag: GraphRagPrompts
    rag: RagPrompts
    matching: MatchingPrompts
    bi: BiPrompts
