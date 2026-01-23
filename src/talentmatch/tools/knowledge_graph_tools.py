from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from talentmatch.config import load_settings

logger = logging.getLogger(__name__)


def _backend() -> str:
    return load_settings().storage.backend


@tool
def ingest_files() -> dict[str, Any]:
    """
    Ingest generated PDFs into the configured storage backend.

    :return: ingestion summary
    """
    backend = _backend()
    logger.info("Tool call: ingest_files (backend=%s)", backend)

    if backend == "vector_store":
        from talentmatch.vector_store import ingest_pdf_files as ingest_pdf_files
    else:
        from talentmatch.knowledge_graph import ingest_pdf_files as ingest_pdf_files

    return ingest_pdf_files()


@tool
def query_knowledge_graph(question: str) -> dict[str, Any]:
    """
    Query the configured storage backend using a natural-language question.

    :param question: user question
    :return: dict containing answer and reasoning
    """
    backend = _backend()
    logger.info("Tool call: query_knowledge_graph (backend=%s)", backend)

    if backend == "vector_store":
        from talentmatch.vector_store import query_vector_store as query
    else:
        from talentmatch.knowledge_graph import query_knowledge_graph as query

    return query(question)


@tool
def propose_staffing(request: str) -> dict[str, Any]:
    """
    Propose a staffing plan for the given request using the configured storage backend.

    :param request: RFP id or staffing request
    :return: dict with team proposal and reasoning
    """
    backend = _backend()
    logger.info("Tool call: propose_staffing (backend=%s)", backend)

    if backend == "vector_store":
        from talentmatch.vector_store import propose_staffing as propose
    else:
        from talentmatch.knowledge_graph import propose_staffing as propose

    return propose(request)
