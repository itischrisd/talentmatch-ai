from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_experimental.graph_transformers import LLMGraphTransformer

from talentmatch.config import load_settings
from talentmatch.infra.llm import AzureLlmProvider
from .ingestion import IngestionSummary, PdfIngestor
from .neo4j import Neo4jGraphService
from .ontology import ALLOWED_NODES, ALLOWED_RELATIONSHIPS, NODE_PROPERTIES

logger = logging.getLogger(__name__)


async def _ingest_pdf_files_async() -> dict[str, Any]:
    """
    Ingest generated PDFs into Neo4j (CVs + RFPs) using the configured transformer and connection settings.

    After ingestion, move successfully ingested PDFs (from both directories) into:
      {paths.archive_dir}/ingested_<timestamp>/

    :return: dict with per-type and total ingestion summaries
    """

    settings = load_settings()
    cvs_dir = Path(settings.paths.programmers_dir)
    rfps_dir = Path(settings.paths.rfps_dir)
    archive_root = Path(settings.paths.archive_dir)

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

    cv_ingestor = PdfIngestor(
        graph_service=graph_service,
        transformer=transformer,
        concurrency=settings.knowledge_graph.concurrency,
        document_type="cv",
    )
    rfp_ingestor = PdfIngestor(
        graph_service=graph_service,
        transformer=transformer,
        concurrency=settings.knowledge_graph.concurrency,
        document_type="rfp",
    )

    cv_summary = await cv_ingestor.ingest_directory(cvs_dir)
    rfp_summary = await rfp_ingestor.ingest_directory(rfps_dir)

    combined_files = tuple(cv_summary.ingested_files) + tuple(rfp_summary.ingested_files)

    archived_to = _archive_ingested_files(
        source_files=combined_files,
        archive_root=archive_root,
    )
    if archived_to is not None:
        logger.info("Archived ingested PDFs to %s", archived_to)

    total = _sum_summaries(cv_summary, rfp_summary)

    return {
        "total": _summary_to_dict(total),
        "cvs": _summary_to_dict(cv_summary),
        "rfps": _summary_to_dict(rfp_summary),
        "archived_to": str(archived_to) if archived_to is not None else None,
    }


def ingest_pdf_files() -> dict[str, Any]:
    """
    Synchronous wrapper for ingest_generated_pdfs_async
    """
    return asyncio.run(_ingest_pdf_files_async())


def _summary_to_dict(summary: IngestionSummary) -> dict[str, Any]:
    return {
        "discovered_pdfs": summary.discovered_pdfs,
        "processed_pdfs": summary.processed_pdfs,
        "failed_pdfs": summary.failed_pdfs,
        "stored_graph_documents": summary.stored_graph_documents,
        "stored_nodes": summary.stored_nodes,
        "stored_relationships": summary.stored_relationships,
        "ingested_files": list(summary.ingested_files),
    }


def _sum_summaries(a: IngestionSummary, b: IngestionSummary) -> IngestionSummary:
    return replace(
        a,
        discovered_pdfs=a.discovered_pdfs + b.discovered_pdfs,
        processed_pdfs=a.processed_pdfs + b.processed_pdfs,
        failed_pdfs=a.failed_pdfs + b.failed_pdfs,
        stored_graph_documents=a.stored_graph_documents + b.stored_graph_documents,
        stored_nodes=a.stored_nodes + b.stored_nodes,
        stored_relationships=a.stored_relationships + b.stored_relationships,
        ingested_files=tuple(a.ingested_files) + tuple(b.ingested_files),
    )


def _archive_ingested_files(*, source_files: tuple[str, ...], archive_root: Path) -> Path | None:
    """
    Move successfully ingested PDF files into a timestamped archive folder:
      archive_root/ingested_<timestamp>/

    Best-effort:
    - If a file does not exist, it is skipped.
    - If a destination name conflicts, a numeric suffix is added.
    - Errors per file are logged but do not fail ingestion.
    """

    if not source_files:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination_dir = archive_root.expanduser() / f"ingested_{timestamp}"
    destination_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for raw in source_files:
        src = Path(raw)
        if not src.exists():
            logger.warning("Skipping archive for missing file: %s", src)
            continue

        dest = _unique_destination(destination_dir, src.name)

        try:
            shutil.move(str(src), str(dest))
            moved += 1
        except Exception:
            logger.exception("Failed to archive %s -> %s", src, dest)

    return destination_dir if moved > 0 else None


def _unique_destination(destination_dir: Path, filename: str) -> Path:
    """
    Produce a unique destination path under destination_dir for filename.
    If filename exists, append _{n} before extension.
    """

    candidate = destination_dir / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    for i in range(1, 10000):
        alt = destination_dir / f"{stem}_{i}{suffix}"
        if not alt.exists():
            return alt

    return destination_dir / f"{stem}_{datetime.now().strftime('%H%M%S%f')}{suffix}"
