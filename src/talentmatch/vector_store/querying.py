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
from talentmatch.vector_store.chroma import VectorStoreService, get_vector_store_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VectorQueryResult:
    question: str
    answer: str
    reasoning: str
    evidence: list[str]
    limitations: str | None
    retrieved_chunks: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "reasoning": self.reasoning,
            "evidence": self.evidence,
            "limitations": self.limitations,
            "retrieved_chunks": int(self.retrieved_chunks),
        }


def query_vector_store(question: str) -> dict[str, Any]:
    """
    Query the vector store using a natural-language question and return an answer with reasoning.

    :param question: natural language user question
    :return: dict with answer, reasoning, evidence, limitations and metadata
    """
    normalized = question.strip()
    if not normalized:
        return VectorQueryResult(
            question=question,
            answer="I cannot run an empty query.",
            reasoning="",
            evidence=[],
            limitations="Empty question.",
            retrieved_chunks=0,
        ).to_dict()

    engine = _get_engine()
    result = engine.run(normalized)
    return result.to_dict()


@dataclass(frozen=True, slots=True)
class _Engine:
    store: VectorStoreService
    llm_provider: AzureLlmProvider
    answer_template: str
    top_k: int

    def run(self, question: str) -> VectorQueryResult:
        docs = self.store.similarity_search(question, k=int(self.top_k))
        context_json = json.dumps([self._doc_to_context(d) for d in docs], ensure_ascii=False)

        prompt = PromptTemplate(
            input_variables=["question", "context_json"],
            template=self.answer_template,
        )
        llm = self.llm_provider.chat("query_agent")
        response = llm.invoke(prompt.format(question=question, context_json=context_json))
        raw = self._strip_code_fences(self._extract_text(response)).strip()

        payload = self._parse_payload(raw)
        return VectorQueryResult(
            question=question,
            answer=str(payload.get("answer", "")).strip() or "I could not generate an answer.",
            reasoning=str(payload.get("reasoning", "")).strip(),
            evidence=[str(x) for x in (payload.get("evidence") or []) if str(x).strip()],
            limitations=(str(payload["limitations"]).strip() if payload.get("limitations") else None),
            retrieved_chunks=len(docs),
        )

    @staticmethod
    def _doc_to_context(doc: Any) -> dict[str, Any]:
        meta = getattr(doc, "metadata", {}) or {}
        return {
            "metadata": {str(k): meta[k] for k in meta},
            "text": str(getattr(doc, "page_content", "") or ""),
        }

    @staticmethod
    def _extract_text(message: Any) -> str:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        return str(message)

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        cleaned = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
        return cleaned

    @staticmethod
    def _parse_payload(text: str) -> dict[str, Any]:
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else {"answer": text, "reasoning": "", "evidence": []}
        except Exception:
            return {"answer": text, "reasoning": "", "evidence": [], "limitations": "Answer was not valid JSON."}


@lru_cache(maxsize=1)
def _get_engine() -> _Engine:
    settings = load_settings()
    prompts = load_prompts()
    llm_provider = AzureLlmProvider(settings)
    store = get_vector_store_service()
    return _Engine(
        store=store,
        llm_provider=llm_provider,
        answer_template=prompts.vector_store.answer_json,
        top_k=int(settings.vector_store.top_k),
    )
