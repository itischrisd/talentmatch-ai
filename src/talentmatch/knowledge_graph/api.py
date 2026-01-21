from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from langchain_experimental.graph_transformers import LLMGraphTransformer

from talentmatch.config import load_settings
from talentmatch.infra.llm import AzureLlmProvider
from .ingestion import CvPdfIngestor, IngestionSummary
from .neo4j import Neo4jGraphService
from .ontology import ALLOWED_NODES, ALLOWED_RELATIONSHIPS, NODE_PROPERTIES

logger = logging.getLogger(__name__)


async def ingest_programmer_cvs_async() -> IngestionSummary:
    """
    Ingest generated CV PDFs into Neo4j using the configured transformer and connection settings
    :return: ingestion summary
    """

    settings = load_settings()
    directory = Path(settings.paths.programmers_dir)
    llm_provider = AzureLlmProvider(settings)
    llm = llm_provider.chat(settings.knowledge_graph.llm_use_case)

    transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=list(ALLOWED_NODES),
        allowed_relationships=list(ALLOWED_RELATIONSHIPS),
        node_properties=list(NODE_PROPERTIES),
        strict_mode=True,
    )

    graph_service = Neo4jGraphService(neo4j=settings.neo4j)
    ingestor = CvPdfIngestor(
        graph_service=graph_service,
        transformer=transformer,
        concurrency=settings.knowledge_graph.concurrency,
    )
    return await ingestor.ingest_directory(directory)


def ingest_programmer_cvs() -> dict[str, Any]:
    """
    Synchronous wrapper for ingest_programmer_cvs_async
    :return: ingestion summary as a plain dict
    """

    summary = asyncio.run(ingest_programmer_cvs_async())

    return {
        "discovered_pdfs": summary.discovered_pdfs,
        "processed_pdfs": summary.processed_pdfs,
        "failed_pdfs": summary.failed_pdfs,
        "stored_graph_documents": summary.stored_graph_documents,
        "stored_nodes": summary.stored_nodes,
        "stored_relationships": summary.stored_relationships,
    }
