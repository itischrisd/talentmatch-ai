from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from talentmatch.config import load_settings
from talentmatch.vector_store.chroma import VectorStoreService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VectorIngestionSummary:
    discovered_files: int
    processed_files: int
    failed_files: int
    stored_chunks: int
    ingested_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovered_files": int(self.discovered_files),
            "processed_files": int(self.processed_files),
            "failed_files": int(self.failed_files),
            "stored_chunks": int(self.stored_chunks),
            "ingested_files": list(self.ingested_files),
        }


class VectorStoreIngestor:
    """
    Ingests PDFs and structured files into the vector store.
    """

    def __init__(self, *, store: VectorStoreService) -> None:
        self._store = store
        settings = load_settings()
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=int(settings.vector_store.chunk_size),
            chunk_overlap=int(settings.vector_store.chunk_overlap),
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

    def ingest_paths(self, paths: Iterable[Path], *, document_type: str) -> VectorIngestionSummary:
        files = [p for p in paths if p.is_file()]
        logger.info("Ingesting %s file(s) as type=%s", len(files), document_type)
        processed = 0
        failed = 0
        stored = 0
        ingested: list[str] = []

        for path in files:
            try:
                chunks = self._load_and_split(path, document_type=document_type)
                if not chunks:
                    logger.warning("No chunks produced for %s (type=%s)", path.name, document_type)
                    failed += 1
                    continue
                stored += self._store.add_documents(chunks)
                processed += 1
                ingested.append(str(path))
            except Exception:
                logger.exception("Vector ingestion failed for %s", path)
                failed += 1

        logger.info(
            "Ingestion result type=%s: discovered=%s processed=%s failed=%s stored_chunks=%s",
            document_type,
            len(files),
            processed,
            failed,
            stored,
        )

        return VectorIngestionSummary(
            discovered_files=len(files),
            processed_files=processed,
            failed_files=failed,
            stored_chunks=stored,
            ingested_files=tuple(ingested),
        )

    def _load_and_split(self, path: Path, *, document_type: str) -> list[Document]:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            docs = PyPDFLoader(str(path)).load()
            for d in docs:
                d.metadata.update({"source_file": path.name, "document_type": document_type, "source_path": str(path)})
            return self._splitter.split_documents(docs)

        if suffix in {".json", ".yaml", ".yml", ".xml", ".txt"}:
            text = path.read_text(encoding="utf-8")
            if suffix == ".json":
                text = self._normalize_json(text)

            base = Document(
                page_content=text,
                metadata={"source_file": path.name, "document_type": document_type, "source_path": str(path)},
            )
            return self._splitter.split_documents([base])

        return []

    @staticmethod
    def _normalize_json(text: str) -> str:
        try:
            payload = json.loads(text)
            return json.dumps(payload, indent=2, ensure_ascii=False)
        except Exception:
            return re.sub(r"\s+", " ", text).strip()
