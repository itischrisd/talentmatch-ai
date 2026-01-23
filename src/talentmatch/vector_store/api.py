from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from talentmatch.config import load_settings
from talentmatch.vector_store.chroma import get_vector_store_service
from talentmatch.vector_store.ingestion import VectorStoreIngestor
from talentmatch.vector_store.querying import query_vector_store as _query_vector_store
from talentmatch.vector_store.staffing import propose_staffing as _propose_staffing

logger = logging.getLogger(__name__)


def ingest_pdf_files() -> dict[str, Any]:
    """
    Ingest generated PDFs (CVs + RFPs) and structured files into the vector store (Chroma).

    After ingestion, move successfully ingested files into:
      {paths.archive_dir}/vector_ingested_<timestamp>/

    :return: dict with per-type and total ingestion summaries
    """
    settings = load_settings()
    cvs_dir = Path(settings.paths.programmers_dir)
    rfps_dir = Path(settings.paths.rfps_dir)
    projects_dir = Path(settings.paths.projects_dir)
    archive_root = Path(settings.paths.archive_dir)

    store = get_vector_store_service()
    ingestor = VectorStoreIngestor(store=store)

    cv_summary = ingestor.ingest_paths(_discover_files(cvs_dir), document_type="cv")
    rfp_summary = ingestor.ingest_paths(_discover_files(rfps_dir), document_type="rfp")
    structured_summary = ingestor.ingest_paths(_discover_structured_files(projects_dir), document_type="project_struct")

    archive_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = _prepare_archive_dir(archive_root=archive_root, timestamp=archive_timestamp)

    moved = 0
    moved += _archive_ingested_files(tuple(cv_summary.ingested_files), destination_dir=archive_dir)
    moved += _archive_ingested_files(tuple(rfp_summary.ingested_files), destination_dir=archive_dir)
    moved += _archive_ingested_files(tuple(structured_summary.ingested_files), destination_dir=archive_dir)

    total = {
        "stored_chunks": int(cv_summary.stored_chunks + rfp_summary.stored_chunks + structured_summary.stored_chunks),
        "moved_to_archive": int(moved),
        "archive_dir": str(archive_dir),
    }

    return {
        "cv": cv_summary.to_dict(),
        "rfp": rfp_summary.to_dict(),
        "structured": structured_summary.to_dict(),
        "total": total,
    }


def query_vector_store(question: str) -> dict[str, Any]:
    """
    Query the vector store using a natural-language question and return an answer with reasoning.

    :param question: natural language user question
    :return: dict with answer and reasoning
    """
    logger.info("API call: vector_store.query_vector_store")
    return _query_vector_store(question)


def propose_staffing(request: str) -> dict[str, Any]:
    """
    Propose a best-effort staffing using the vector store and return an explainable proposal.

    :param request: user request containing an RFP id or staffing request
    :return: dict with team proposal and reasoning
    """
    logger.info("API call: vector_store.propose_staffing")
    return _propose_staffing(request)


def _discover_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted([p for p in directory.glob("*.pdf") if p.is_file()])


def _discover_structured_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    patterns = ("*.json", "*.yaml", "*.yml", "*.xml", "*.txt")
    files: list[Path] = []
    for pattern in patterns:
        files.extend([p for p in directory.rglob(pattern) if p.is_file()])
    return sorted(files)


def _prepare_archive_dir(*, archive_root: Path, timestamp: str) -> Path:
    archive_root.mkdir(parents=True, exist_ok=True)
    destination = archive_root / f"vector_ingested_{timestamp}"
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _archive_ingested_files(*, source_files: tuple[str, ...], destination_dir: Path) -> int:
    moved = 0
    for raw in source_files:
        path = Path(raw)
        if not path.exists():
            continue
        target = destination_dir / path.name
        try:
            shutil.move(str(path), str(target))
            moved += 1
        except Exception:
            logger.exception("Failed to archive file: %s", str(path))
    return moved
