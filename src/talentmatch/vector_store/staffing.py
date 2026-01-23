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
class StaffingResult:
    request: str
    team: list[dict[str, Any]]
    reasoning: list[str]
    coverage: str
    evidence: list[str]
    limitations: str | None
    retrieved_chunks: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "team": self.team,
            "reasoning": self.reasoning,
            "coverage": self.coverage,
            "evidence": self.evidence,
            "limitations": self.limitations,
            "retrieved_chunks": int(self.retrieved_chunks),
        }


def propose_staffing(request: str) -> dict[str, Any]:
    """
    Propose a best-effort staffing for an RFP using the vector store.

    This is a vector-based placeholder implementation intended to mirror the Neo4j-based interface.
    It always returns a non-empty staffing offer.

    :param request: user request containing an RFP id (e.g. "RFP-001") or a short staffing request
    :return: dict with staffing proposal, reasoning and evidence
    """
    normalized = request.strip()
    if not normalized:
        return _external_offer("Empty request.").to_dict()

    engine = _get_engine()
    result = engine.run(normalized)
    return result.to_dict()


def _external_offer(reason: str) -> StaffingResult:
    return StaffingResult(
        request="",
        team=[{"person_id": "EXTERNAL", "name": "External contractor", "reasoning": reason}],
        reasoning=[reason],
        coverage="No internal coverage could be determined.",
        evidence=[],
        limitations="Provide an RFP id and ingest CV/RFP PDFs into the vector store for internal proposals.",
        retrieved_chunks=0,
    )


@dataclass(frozen=True, slots=True)
class _Engine:
    store: VectorStoreService
    llm_provider: AzureLlmProvider
    staffing_template: str
    top_k: int

    def run(self, request: str) -> StaffingResult:
        docs = self.store.similarity_search(request, k=int(self.top_k))
        context_json = json.dumps([self._doc_to_context(d) for d in docs], ensure_ascii=False)

        prompt = PromptTemplate(
            input_variables=["request", "context_json"],
            template=self.staffing_template,
        )

        llm = self.llm_provider.chat("query_agent")
        response = llm.invoke(prompt.format(request=request, context_json=context_json))
        raw = self._strip_code_fences(self._extract_text(response)).strip()
        payload = self._parse_payload(raw)

        team = payload.get("team")
        if not isinstance(team, list) or not team:
            return _external_offer("Insufficient internal evidence; placeholder offer.")

        reasoning = payload.get("reasoning") or []
        evidence = payload.get("evidence") or []

        return StaffingResult(
            request=request,
            team=[x for x in team if isinstance(x, dict)] or [
                {"person_id": "EXTERNAL", "name": "External contractor", "reasoning": "Placeholder offer."}],
            reasoning=[str(x) for x in reasoning if str(x).strip()],
            coverage=str(payload.get("coverage", "")).strip() or "Coverage unknown.",
            evidence=[str(x) for x in evidence if str(x).strip()],
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
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}


@lru_cache(maxsize=1)
def _get_engine() -> _Engine:
    settings = load_settings()
    prompts = load_prompts()
    llm_provider = AzureLlmProvider(settings)
    store = get_vector_store_service()
    return _Engine(
        store=store,
        llm_provider=llm_provider,
        staffing_template=prompts.vector_store.staffing_json,
        top_k=max(int(settings.vector_store.top_k), 8),
    )
