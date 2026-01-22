from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def ingest_files() -> dict[str, Any]:
    """
    Ingest generated CV PDFs into Neo4j using the configured transformer and connection settings.

    :return: Ingestion summary as a plain dictionary.
    """
    from talentmatch.knowledge_graph import ingest_pdf_files as _ingest_pdf_files

    logger.info("Tool call: knowledge_graph.ingest_programmer_cvs")
    return _ingest_pdf_files()
