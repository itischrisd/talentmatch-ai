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


async def ingest_programmer_cvs_async(
    *,
    cv_directory: str | Path | None = None,
    llm_use_case: str = "graph_transformer",
    reset_neo4j_on_start: bool = False,
    concurrency: int = 2,
    settings_toml_path: str | None = None,
) -> IngestionSummary:
    """
    Ingest generated CV PDFs into Neo4j
    :param cv_directory: Directory containing PDF CV files. Defaults to settings.paths.programmers_dir
    :param llm_use_case: LLM use-case name from settings.llm.use_cases
    :param reset_neo4j_on_start: Whether to clear Neo4j before ingestion
    :param concurrency: Maximum number of concurrent LLM conversions
    :param settings_toml_path: Optional path to settings TOML file
    :return: Ingestion summary
    """

    settings = load_settings(settings_toml_path)
    directory = Path(cv_directory) if cv_directory is not None else Path(settings.paths.programmers_dir)

    llm_provider = AzureLlmProvider(settings)
    try:
        llm = llm_provider.chat(llm_use_case)
    except KeyError as exc:
        raise ValueError(f"Unknown llm_use_case: {llm_use_case}") from exc

    transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=list(ALLOWED_NODES),
        allowed_relationships=list(ALLOWED_RELATIONSHIPS),
        node_properties=list(NODE_PROPERTIES),
        strict_mode=True,
    )

    graph_service = Neo4jGraphService(settings=settings, reset_on_start=reset_neo4j_on_start)
    ingestor = CvPdfIngestor(graph_service=graph_service, transformer=transformer, concurrency=concurrency)
    summary = await ingestor.ingest_directory(directory)

    logger.info(
        "Ingestion summary: discovered=%d processed=%d failed=%d stored_docs=%d nodes=%d relationships=%d",
        summary.discovered_pdfs,
        summary.processed_pdfs,
        summary.failed_pdfs,
        summary.stored_graph_documents,
        summary.stored_nodes,
        summary.stored_relationships,
    )

    return summary


def ingest_programmer_cvs(
    *,
    cv_directory: str | Path | None = None,
    llm_use_case: str = "graph_transformer",
    reset_neo4j_on_start: bool = False,
    concurrency: int = 2,
    settings_toml_path: str | None = None,
) -> dict[str, Any]:
    """
    Ingest generated CV PDFs into Neo4j
    :param cv_directory: Directory containing PDF CV files. Defaults to settings.paths.programmers_dir
    :param llm_use_case: LLM use-case name from settings.llm.use_cases
    :param reset_neo4j_on_start: Whether to clear Neo4j before ingestion
    :param concurrency: Maximum number of concurrent LLM conversions
    :param settings_toml_path: Optional path to settings TOML file
    :return: Dictionary with ingestion summary
    """

    summary = asyncio.run(
        ingest_programmer_cvs_async(
            cv_directory=cv_directory,
            llm_use_case=llm_use_case,
            reset_neo4j_on_start=reset_neo4j_on_start,
            concurrency=concurrency,
            settings_toml_path=settings_toml_path,
        )
    )

    return {
        "discovered_pdfs": summary.discovered_pdfs,
        "processed_pdfs": summary.processed_pdfs,
        "failed_pdfs": summary.failed_pdfs,
        "stored_graph_documents": summary.stored_graph_documents,
        "stored_nodes": summary.stored_nodes,
        "stored_relationships": summary.stored_relationships,
    }
