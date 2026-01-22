from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from unstructured.partition.pdf import partition_pdf

from .neo4j import Neo4jGraphService, StorageResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    """
    Aggregates PDF ingestion results.
    """

    discovered_pdfs: int
    processed_pdfs: int
    failed_pdfs: int
    stored_graph_documents: int
    stored_nodes: int
    stored_relationships: int
    ingested_files: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StructuredIngestionSummary:
    """
    Aggregates structured file ingestion results.
    """

    discovered_files: int
    processed_files: int
    failed_files: int
    faulty_files: int
    stored_graph_documents: int
    stored_nodes: int
    stored_relationships: int
    ingested_files: tuple[str, ...] = ()
    missing_person_ids: tuple[str, ...] = ()
    missing_project_ids: tuple[str, ...] = ()
    missing_person_identifier_count: int = 0
    missing_project_identifier_count: int = 0


class PdfIngestor:
    """
    Converts PDFs into a Neo4j knowledge graph using LLMGraphTransformer.
    """

    def __init__(
            self,
            *,
            graph_service: Neo4jGraphService,
            transformer: LLMGraphTransformer,
            concurrency: int,
            document_type: str,
    ) -> None:
        """
        Create an ingestor.
        :param graph_service: Neo4j graph service
        :param transformer: Schema-constrained graph transformer
        :param concurrency: Maximum number of concurrent LLM conversions
        :param document_type: metadata marker, e.g. "cv" or "rfp"
        :raises ValueError: If concurrency is less than 1
        """

        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")

        self._graph_service = graph_service
        self._transformer = transformer
        self._concurrency = concurrency
        self._document_type = str(document_type).strip() or "document"

    @staticmethod
    def _extract_pdf_text(pdf_path: Path) -> str:
        try:
            elements = partition_pdf(filename=str(pdf_path), languages=["eng"])
            fragments = (getattr(element, "text", None) or str(element) for element in elements)
            text = "\n\n".join(fragment for fragment in fragments if fragment)
            logger.debug("Extracted %d characters from %s", len(text), pdf_path.name)
            return text
        except Exception:
            logger.exception("PDF extraction failed for %s", pdf_path)
            return ""

    async def _convert_pdf_to_graph_documents(self, pdf_path: Path) -> list[Any]:
        logger.info("Processing %s (%s)", pdf_path.name, self._document_type)

        text = self._extract_pdf_text(pdf_path)
        if not text.strip():
            logger.warning("No text extracted from %s", pdf_path.name)
            return []

        document = Document(
            page_content=text,
            metadata={"source": str(pdf_path), "type": self._document_type},
        )

        try:
            graph_documents = await self._transformer.aconvert_to_graph_documents([document])
            if graph_documents:
                first = graph_documents[0]
                nodes = len(getattr(first, "nodes", []))
                relationships = len(getattr(first, "relationships", []))
                logger.info(
                    "Extracted graph from %s (%s) (nodes=%d, relationships=%d)",
                    pdf_path.name,
                    self._document_type,
                    nodes,
                    relationships,
                )
            return list(graph_documents)
        except Exception:
            logger.exception("LLM graph conversion failed for %s", pdf_path.name)
            return []

    def _store_graph_documents(self, graph_documents: list[Any]) -> StorageResult:
        return self._graph_service.add_graph_documents(graph_documents)

    async def ingest_directory(self, pdf_directory: Path) -> IngestionSummary:
        """
        Process all PDFs in a directory.
        :param pdf_directory: path containing PDFs
        :return: Ingestion summary
        """

        directory = pdf_directory.expanduser()
        pdf_paths = sorted(directory.glob("*.pdf"))

        if not pdf_paths:
            logger.error("No PDF files found in %s", directory)
            return IngestionSummary(0, 0, 0, 0, 0, 0, ())

        semaphore = asyncio.Semaphore(self._concurrency)

        async def convert_with_limit(path: Path) -> tuple[Path, list[Any]]:
            async with semaphore:
                return path, await self._convert_pdf_to_graph_documents(path)

        tasks = [asyncio.create_task(convert_with_limit(path)) for path in pdf_paths]
        results = await asyncio.gather(*tasks)

        processed = 0
        failed = 0
        stored_docs = 0
        stored_nodes = 0
        stored_relationships = 0
        ingested_files: list[str] = []

        for path, documents in results:
            if not documents:
                failed += 1
                continue

            try:
                storage = self._store_graph_documents(documents)
            except Exception:
                logger.exception("Neo4j write failed for %s", path.name)
                failed += 1
                continue

            processed += 1
            stored_docs += len(documents)
            stored_nodes += storage.nodes
            stored_relationships += storage.relationships
            ingested_files.append(str(path))

        return IngestionSummary(
            discovered_pdfs=len(pdf_paths),
            processed_pdfs=processed,
            failed_pdfs=failed,
            stored_graph_documents=stored_docs,
            stored_nodes=stored_nodes,
            stored_relationships=stored_relationships,
            ingested_files=tuple(ingested_files),
        )


class StructuredFileIngestor:
    """
    Converts structured text files (JSON/XML/YAML/...) into a Neo4j knowledge graph using LLMGraphTransformer.
    """

    def __init__(
            self,
            *,
            graph_service: Neo4jGraphService,
            transformer: LLMGraphTransformer,
            concurrency: int,
            document_type: str,
            required_node_labels: tuple[str, str] = ("Person", "Project"),
    ) -> None:
        """
        Create an ingestor.
        :param graph_service: Neo4j graph service
        :param transformer: Schema-constrained graph transformer
        :param concurrency: Maximum number of concurrent LLM conversions
        :param document_type: metadata marker, e.g. "structured"
        :param required_node_labels: node labels that must already exist in Neo4j
        :raises ValueError: If concurrency is less than 1
        """

        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")

        self._graph_service = graph_service
        self._transformer = transformer
        self._concurrency = concurrency
        self._document_type = str(document_type).strip() or "structured"
        self._required_person_label = str(required_node_labels[0]).strip() or "Person"
        self._required_project_label = str(required_node_labels[1]).strip() or "Project"

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            data = path.read_bytes()
            return data.decode("utf-8", errors="ignore")
        except Exception:
            logger.exception("Failed to read %s", path)
            return ""

    async def _convert_file_to_graph_documents(self, path: Path) -> list[Any]:
        logger.info("Processing %s (%s)", path.name, self._document_type)

        text = self._read_text(path)
        if not text.strip():
            logger.warning("No text extracted from %s", path.name)
            return []

        document = Document(
            page_content=text,
            metadata={
                "source": str(path),
                "type": self._document_type,
                "format": path.suffix.lower().lstrip("."),
            },
        )

        try:
            graph_documents = await self._transformer.aconvert_to_graph_documents([document])
            if graph_documents:
                first = graph_documents[0]
                nodes = len(getattr(first, "nodes", []))
                relationships = len(getattr(first, "relationships", []))
                logger.info(
                    "Extracted graph from %s (%s) (nodes=%d, relationships=%d)",
                    path.name,
                    self._document_type,
                    nodes,
                    relationships,
                )
            return list(graph_documents)
        except Exception:
            logger.exception("LLM graph conversion failed for %s", path.name)
            return []

    def _extract_required_ids(
            self, graph_documents: Iterable[Any]
    ) -> tuple[set[str], set[str], int, int]:
        person_ids: set[str] = set()
        project_ids: set[str] = set()
        missing_person_id = 0
        missing_project_id = 0

        for doc in graph_documents:
            for node in getattr(doc, "nodes", []) or []:
                node_type = str(getattr(node, "type", "")).strip()
                node_id = getattr(node, "id", None)

                if node_type in ("Programmer", self._required_person_label):
                    if node_id is None or str(node_id).strip() == "":
                        missing_person_id += 1
                    else:
                        person_ids.add(str(node_id).strip())

                if node_type == self._required_project_label:
                    if node_id is None or str(node_id).strip() == "":
                        missing_project_id += 1
                    else:
                        project_ids.add(str(node_id).strip())

        return person_ids, project_ids, missing_person_id, missing_project_id

    def _store_graph_documents(self, graph_documents: list[Any]) -> StorageResult:
        return self._graph_service.add_graph_documents(graph_documents)

    @staticmethod
    def _discover_files(directories: Iterable[Path], extensions: tuple[str, ...]) -> list[Path]:
        targets: set[Path] = set()
        normalized = tuple(ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions)

        for directory in directories:
            base = directory.expanduser()
            if not base.exists():
                continue
            for ext in normalized:
                for path in base.rglob(f"*{ext}"):
                    if path.is_file():
                        targets.add(path)

        return sorted(targets)

    async def ingest_directories(
            self,
            directories: Iterable[Path],
            *,
            extensions: tuple[str, ...] = (".json", ".xml", ".yaml", ".yml"),
    ) -> StructuredIngestionSummary:
        """
        Process structured files across multiple directories, validating that Person and Project nodes exist in Neo4j.
        :param directories: directories to search recursively for structured files
        :param extensions: file suffixes to ingest
        :return: ingestion summary
        """

        paths = self._discover_files(directories, extensions)

        if not paths:
            logger.info("No structured files found in the configured directories")
            return StructuredIngestionSummary(0, 0, 0, 0, 0, 0, 0)

        semaphore = asyncio.Semaphore(self._concurrency)

        async def convert_with_limit(path: Path) -> tuple[Path, list[Any]]:
            async with semaphore:
                return path, await self._convert_file_to_graph_documents(path)

        tasks = [asyncio.create_task(convert_with_limit(path)) for path in paths]
        results = await asyncio.gather(*tasks)

        processed = 0
        failed = 0
        faulty = 0
        stored_docs = 0
        stored_nodes = 0
        stored_relationships = 0
        ingested_files: list[str] = []

        missing_person_ids: set[str] = set()
        missing_project_ids: set[str] = set()
        missing_person_identifier_count = 0
        missing_project_identifier_count = 0

        for path, documents in results:
            if not documents:
                failed += 1
                continue

            person_ids, project_ids, missing_person_id, missing_project_id = self._extract_required_ids(documents)
            missing_person_identifier_count += missing_person_id
            missing_project_identifier_count += missing_project_id

            missing_person = self._graph_service.missing_node_ids(label=self._required_person_label, ids=person_ids)
            missing_project = self._graph_service.missing_node_ids(label=self._required_project_label, ids=project_ids)

            if missing_person or missing_project or missing_person_id > 0 or missing_project_id > 0:
                faulty += 1
                missing_person_ids.update(missing_person)
                missing_project_ids.update(missing_project)

            try:
                storage = self._store_graph_documents(documents)
            except Exception:
                logger.exception("Neo4j write failed for %s", path.name)
                failed += 1
                continue

            processed += 1
            stored_docs += len(documents)
            stored_nodes += storage.nodes
            stored_relationships += storage.relationships
            ingested_files.append(str(path))

        return StructuredIngestionSummary(
            discovered_files=len(paths),
            processed_files=processed,
            failed_files=failed,
            faulty_files=faulty,
            stored_graph_documents=stored_docs,
            stored_nodes=stored_nodes,
            stored_relationships=stored_relationships,
            ingested_files=tuple(ingested_files),
            missing_person_ids=tuple(sorted(missing_person_ids)),
            missing_project_ids=tuple(sorted(missing_project_ids)),
            missing_person_identifier_count=missing_person_identifier_count,
            missing_project_identifier_count=missing_project_identifier_count,
        )


class CvPdfIngestor(PdfIngestor):
    """
    Backwards-compatible wrapper for CV ingestion.
    """

    def __init__(
            self,
            *,
            graph_service: Neo4jGraphService,
            transformer: LLMGraphTransformer,
            concurrency: int,
    ) -> None:
        super().__init__(
            graph_service=graph_service,
            transformer=transformer,
            concurrency=concurrency,
            document_type="cv",
        )
