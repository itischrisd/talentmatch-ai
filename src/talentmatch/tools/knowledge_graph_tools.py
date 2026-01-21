from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

ToolCallable = Callable[..., Any]

__all__ = [
    "KnowledgeGraphTools",
]


def _ingestion_summary_to_dict(summary: Any) -> dict[str, int]:
    return {
        "discovered_pdfs": int(summary.discovered_pdfs),
        "processed_pdfs": int(summary.processed_pdfs),
        "failed_pdfs": int(summary.failed_pdfs),
        "stored_graph_documents": int(summary.stored_graph_documents),
        "stored_nodes": int(summary.stored_nodes),
        "stored_relationships": int(summary.stored_relationships),
    }


class KnowledgeGraphTools:
    """
    Toolset exposing public operations from the knowledge_graph module.
    """

    @staticmethod
    def toolset() -> tuple[ToolCallable, ...]:
        """
        Return the tool callables exposed by this toolset.

        :return: Tuple of tool callables.
        """
        return (
            KnowledgeGraphTools.ingest_programmer_cvs,
            KnowledgeGraphTools.ingest_programmer_cvs_async,
        )

    @staticmethod
    def ingest_programmer_cvs() -> dict[str, Any]:
        """
        Ingest generated CV PDFs into Neo4j using the configured transformer and connection settings.

        :return: Ingestion summary as a plain dictionary.
        """
        from talentmatch.knowledge_graph import ingest_programmer_cvs as _ingest_programmer_cvs

        logger.info("Tool call: knowledge_graph.ingest_programmer_cvs")
        return _ingest_programmer_cvs()

    @staticmethod
    async def ingest_programmer_cvs_async() -> dict[str, Any]:
        """
        Ingest generated CV PDFs into Neo4j asynchronously using the configured transformer and connection settings.

        :return: Ingestion summary as a plain dictionary.
        """
        from talentmatch.knowledge_graph import ingest_programmer_cvs_async as _ingest_programmer_cvs_async

        logger.info("Tool call: knowledge_graph.ingest_programmer_cvs_async")
        summary = await _ingest_programmer_cvs_async()
        return _ingestion_summary_to_dict(summary)
