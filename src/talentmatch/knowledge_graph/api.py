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
from .ingestion import IngestionSummary, PdfIngestor, StructuredFileIngestor, StructuredIngestionSummary
from .neo4j import Neo4jGraphService
from .ontology import ALLOWED_NODES, ALLOWED_RELATIONSHIPS, NODE_PROPERTIES

logger = logging.getLogger(__name__)


async def _ingest_pdf_files_async() -> dict[str, Any]:
    """
    Ingest generated PDFs into Neo4j (CVs + RFPs) using the configured transformer and connection settings.

    After PDF ingestion, move successfully ingested PDFs into:
      {paths.archive_dir}/ingested_<timestamp>/

    As the final step, ingest structured files (JSON/XML/YAML) located anywhere under:
    - {paths.programmers_dir}
    - {paths.rfps_dir}
    - {paths.projects_dir}

    After structured ingestion, move successfully ingested structured files into the same archive folder used for PDFs.

    :return: dict with per-type and total ingestion summaries
    """

    settings = load_settings()
    cvs_dir = Path(settings.paths.programmers_dir)
    rfps_dir = Path(settings.paths.rfps_dir)
    projects_dir = Path(settings.paths.projects_dir)
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

    archive_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir: Path | None = None

    def archive_files(source_files: tuple[str, ...]) -> int:
        nonlocal archive_dir
        if not source_files:
            return 0

        if archive_dir is None:
            archive_dir = _prepare_archive_dir(archive_root=archive_root, timestamp=archive_timestamp)

        return _archive_ingested_files(source_files=source_files, destination_dir=archive_dir)

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

    pdf_files = tuple(cv_summary.ingested_files) + tuple(rfp_summary.ingested_files)
    moved_pdfs = archive_files(pdf_files)
    if moved_pdfs > 0 and archive_dir is not None:
        logger.info("Archived %d ingested PDF(s) to %s", moved_pdfs, archive_dir)

    structured_ingestor = StructuredFileIngestor(
        graph_service=graph_service,
        transformer=transformer,
        concurrency=settings.knowledge_graph.concurrency,
        document_type="structured",
    )

    structured_summary = await structured_ingestor.ingest_directories(
        (cvs_dir, rfps_dir, projects_dir),
    )

    moved_structured = archive_files(tuple(structured_summary.ingested_files))
    if moved_structured > 0 and archive_dir is not None:
        logger.info("Archived %d ingested structured file(s) to %s", moved_structured, archive_dir)

    total_pdf = _sum_summaries(cv_summary, rfp_summary)

    return {
        "total": _summary_to_dict(total_pdf),
        "cvs": _summary_to_dict(cv_summary),
        "rfps": _summary_to_dict(rfp_summary),
        "archived_to": str(archive_dir) if archive_dir is not None else None,
        "structured": _structured_summary_to_dict(structured_summary),
        "missing_values": {
            "missing_person_ids": list(structured_summary.missing_person_ids),
            "missing_project_ids": list(structured_summary.missing_project_ids),
            "missing_person_identifier_count": structured_summary.missing_person_identifier_count,
            "missing_project_identifier_count": structured_summary.missing_project_identifier_count,
        },
    }


def ingest_pdf_files() -> dict[str, Any]:
    """
    Synchronous wrapper for _ingest_pdf_files_async.
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


def _structured_summary_to_dict(summary: StructuredIngestionSummary) -> dict[str, Any]:
    return {
        "discovered_files": summary.discovered_files,
        "processed_files": summary.processed_files,
        "failed_files": summary.failed_files,
        "faulty_files": summary.faulty_files,
        "stored_graph_documents": summary.stored_graph_documents,
        "stored_nodes": summary.stored_nodes,
        "stored_relationships": summary.stored_relationships,
        "ingested_files": list(summary.ingested_files),
        "missing_person_ids": list(summary.missing_person_ids),
        "missing_project_ids": list(summary.missing_project_ids),
        "missing_person_identifier_count": summary.missing_person_identifier_count,
        "missing_project_identifier_count": summary.missing_project_identifier_count,
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


def _prepare_archive_dir(*, archive_root: Path, timestamp: str) -> Path:
    """
    Prepare a timestamped archive folder under archive_root:
      archive_root/ingested_<timestamp>/
    """
    destination_dir = archive_root.expanduser() / f"ingested_{timestamp}"
    destination_dir.mkdir(parents=True, exist_ok=True)
    return destination_dir


def _archive_ingested_files(*, source_files: tuple[str, ...], destination_dir: Path) -> int:
    """
    Move successfully ingested files into destination_dir.

    Best-effort:
    - If a file does not exist, it is skipped.
    - If a destination name conflicts, a numeric suffix is added.
    - Errors per file are logged but do not fail ingestion.

    :return: number of files moved
    """
    if not source_files:
        return 0

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

    return moved


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


def query_knowledge_graph(question: str) -> dict[str, Any]:
    """
    Query the knowledge graph using a natural language question.

    :param question: user question
    :return: dict with answer, reasoning, evidence, cypher and basic metadata
    """
    from .querying import query_knowledge_graph as _query_knowledge_graph

    logger.info("API call: knowledge_graph.query_knowledge_graph")
    return _query_knowledge_graph(question)


def propose_staffing(request: str) -> dict[str, Any]:
    """
    Propose a best-effort staffing for an RFP based on the current knowledge graph.

    :param request: user request containing an RFP id (e.g. "RFP-001") or a short staffing request
    :return: dict with staffing proposal and explainable reasoning
    """
    from .staffing import propose_staffing as _propose_staffing

    logger.info("API call: knowledge_graph.propose_staffing")
    return _propose_staffing(request)
