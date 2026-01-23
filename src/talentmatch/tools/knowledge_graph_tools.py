from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def ingest_files() -> dict[str, Any]:
    """
    Ingest staged PDFs (and structured files, if present) into Neo4j using the configured transformer and
    connection settings.

    :return: Ingestion summary as a plain dictionary.
    """
    from talentmatch.knowledge_graph import ingest_pdf_files as _ingest_pdf_files

    logger.info("Tool call: knowledge_graph.ingest_files")
    return _ingest_pdf_files()


@tool
def query_knowledge_graph(question: str) -> dict[str, Any]:
    """
    Query the knowledge graph using a natural language question and return an answer with reasoning.

    :param question: user question
    :return: dict with answer, reasoning, evidence, cypher and basic metadata
    """
    from talentmatch.knowledge_graph import query_knowledge_graph as _query_knowledge_graph

    logger.info("Tool call: knowledge_graph.query_knowledge_graph")
    return _query_knowledge_graph(question)


@tool
def propose_staffing(request: str) -> dict[str, Any]:
    """
    Propose a best-effort staffing for an RFP and return an explainable proposal with reasoning.

    :param request: user request containing an RFP id (e.g. "RFP-001") or a short staffing request
    :return: dict with proposed team, coverage and reasoning
    """
    from talentmatch.knowledge_graph import propose_staffing as _propose_staffing

    logger.info("Tool call: knowledge_graph.propose_staffing")
    return _propose_staffing(request)
