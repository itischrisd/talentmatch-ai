from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langchain_core.prompts import PromptTemplate

from talentmatch.config import load_prompts, load_settings
from talentmatch.infra.llm import AzureLlmProvider
from talentmatch.knowledge_graph.neo4j import Neo4jGraphService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QueryResult:
    question: str
    cypher: str
    answer: str
    reasoning: str
    evidence: list[str]
    limitations: str | None
    records_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "cypher": self.cypher,
            "answer": self.answer,
            "reasoning": self.reasoning,
            "evidence": self.evidence,
            "limitations": self.limitations,
            "records_count": self.records_count,
        }


def query_knowledge_graph(question: str) -> dict[str, Any]:
    """
    Execute a natural-language query against the knowledge graph and return an answer with reasoning.

    :param question: natural language user question
    :return: dict with answer, reasoning, evidence, cypher and basic metadata
    """
    normalized = question.strip()
    if not normalized:
        return QueryResult(
            question=question,
            cypher="",
            answer="I cannot run an empty query.",
            reasoning="",
            evidence=[],
            limitations="Empty question.",
            records_count=0,
        ).to_dict()

    engine = _get_engine()
    result = engine.run(normalized)
    return result.to_dict()


@dataclass(frozen=True, slots=True)
class _Engine:
    graph_service: Neo4jGraphService
    llm_provider: AzureLlmProvider
    cypher_template: str
    answer_template: str

    def run(self, question: str) -> QueryResult:
        cypher = self._generate_cypher(question)
        records = self._execute_cypher(cypher)
        answer_payload = self._generate_answer(question=question, cypher=cypher, records=records)
        return QueryResult(
            question=question,
            cypher=cypher,
            answer=str(answer_payload.get("answer", "")).strip() or "I could not generate an answer.",
            reasoning=str(answer_payload.get("reasoning", "")).strip(),
            evidence=[str(x) for x in (answer_payload.get("evidence") or []) if str(x).strip()],
            limitations=(str(answer_payload["limitations"]).strip() if answer_payload.get("limitations") else None),
            records_count=len(records),
        )

    def _generate_cypher(self, question: str) -> str:
        graph = self.graph_service.graph
        graph.refresh_schema()

        prompt = PromptTemplate(
            input_variables=["schema", "question"],
            template=self.cypher_template,
        )
        llm = self.llm_provider.chat("query_agent")
        response = llm.invoke(prompt.format(schema=graph.schema, question=question))
        cypher = self._extract_text(response)
        cypher = self._strip_code_fences(cypher).strip()
        cypher = self._take_first_statement(cypher)
        self._validate_read_only(cypher)
        logger.info("Generated Cypher: %s", cypher)
        return cypher

    def _execute_cypher(self, cypher: str) -> list[dict[str, Any]]:
        try:
            result = self.graph_service.graph.query(cypher)
            rows = list(result) if result else []
            return [row for row in rows if isinstance(row, dict)]
        except Exception:
            logger.exception("Cypher execution failed")
            return []

    def _generate_answer(self, *, question: str, cypher: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        safe_records = self._truncate_records(records)
        records_json = json.dumps(safe_records, ensure_ascii=False)
        prompt = PromptTemplate(
            input_variables=["question", "cypher", "records_json"],
            template=self.answer_template,
        )
        llm = self.llm_provider.chat("query_agent")
        response = llm.invoke(prompt.format(question=question, cypher=cypher, records_json=records_json))
        raw = self._strip_code_fences(self._extract_text(response)).strip()

        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else {"answer": raw, "reasoning": "", "evidence": []}
        except Exception:
            return {"answer": raw, "reasoning": "", "evidence": [], "limitations": "Answer was not valid JSON."}

    @staticmethod
    def _extract_text(message: Any) -> str:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        return str(message)

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        cleaned = re.sub(r"^\s*```(?:json|cypher)?\s*", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
        return cleaned

    @staticmethod
    def _take_first_statement(text: str) -> str:
        parts = [p.strip() for p in text.split(";") if p.strip()]
        return parts[0] if parts else text.strip()

    @staticmethod
    def _validate_read_only(cypher: str) -> None:
        lowered = cypher.lower()
        forbidden = (
            "create ",
            "merge ",
            "delete ",
            "detach ",
            " set ",
            "drop ",
            "load ",
            "call apoc",
        )
        if any(token in lowered for token in forbidden):
            raise ValueError("Unsafe Cypher detected. Only read-only queries are allowed.")

    @staticmethod
    def _truncate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        limited = records[:50]
        sanitized: list[dict[str, Any]] = []
        for row in limited:
            item: dict[str, Any] = {}
            for key, value in row.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    item[str(key)] = value
                else:
                    item[str(key)] = str(value)
            sanitized.append(item)
        return sanitized


@lru_cache(maxsize=1)
def _get_engine() -> _Engine:
    settings = load_settings()
    prompts = load_prompts()
    llm_provider = AzureLlmProvider(settings)
    graph_service = Neo4jGraphService(neo4j=settings.neo4j)

    return _Engine(
        graph_service=graph_service,
        llm_provider=llm_provider,
        cypher_template=prompts.knowledge_graph.cypher_generation,
        answer_template=prompts.knowledge_graph.answer_json,
    )
