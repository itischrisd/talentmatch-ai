from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from unstructured.partition.pdf import partition_pdf

from .neo4j import Neo4jGraphService, StorageResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    """Aggregates ingestion results."""

    discovered_pdfs: int
    processed_pdfs: int
    failed_pdfs: int
    stored_graph_documents: int
    stored_nodes: int
    stored_relationships: int


class CvPdfIngestor:
    """Converts CV PDFs into a Neo4j knowledge graph using LLMGraphTransformer."""

    def __init__(
            self,
            *,
            graph_service: Neo4jGraphService,
            transformer: LLMGraphTransformer,
            concurrency: int,
    ) -> None:
        """
        Create an ingestor

        :param graph_service: Neo4j graph service.
        :param transformer: Schema-constrained graph transformer.
        :param concurrency: Maximum number of concurrent LLM conversions.
        :raises ValueError: If concurrency is less than 1.
        """

        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")

        self._graph_service = graph_service
        self._transformer = transformer
        self._concurrency = concurrency

    @staticmethod
    def extract_pdf_text(pdf_path: Path) -> str:
        """Extract text from a PDF.

        :param pdf_path: Path to a PDF file.
        :return: Extracted text, or an empty string on failure.
        """

        try:
            elements = partition_pdf(filename=str(pdf_path))
            fragments = (getattr(element, "text", None) or str(element) for element in elements)
            text = "\n\n".join(fragment for fragment in fragments if fragment)
            logger.debug("Extracted %d characters from %s", len(text), pdf_path.name)
            return text
        except Exception:
            logger.exception("PDF extraction failed for %s", pdf_path)
            return ""

    async def convert_pdf_to_graph_documents(self, pdf_path: Path) -> list[Any]:
        """Convert a single PDF into graph documents.

        :param pdf_path: Path to a PDF file.
        :return: List of graph documents.
        """

        logger.info("Processing %s", pdf_path.name)
        text = self.extract_pdf_text(pdf_path)
        if not text.strip():
            logger.warning("No text extracted from %s", pdf_path.name)
            return []

        document = Document(page_content=text, metadata={"source": str(pdf_path), "type": "cv"})

        try:
            graph_documents = await self._transformer.aconvert_to_graph_documents([document])
            if graph_documents:
                first = graph_documents[0]
                nodes = len(getattr(first, "nodes", []))
                relationships = len(getattr(first, "relationships", []))
                logger.info(
                    "Extracted graph from %s (nodes=%d, relationships=%d)",
                    pdf_path.name,
                    nodes,
                    relationships,
                )
            return list(graph_documents)
        except Exception:
            logger.exception("LLM graph conversion failed for %s", pdf_path.name)
            return []

    def store_graph_documents(self, graph_documents: list[Any]) -> StorageResult:
        """Store graph documents in Neo4j.

        :param graph_documents: GraphDocument objects.
        :return: Storage result.
        """

        return self._graph_service.add_graph_documents(graph_documents)

    async def ingest_directory(self, pdf_directory: Path) -> IngestionSummary:
        """Process all PDFs in a directory.

        :param pdf_directory: Directory containing PDF CV files.
        :return: Ingestion summary.
        """

        directory = pdf_directory.expanduser()
        pdf_paths = sorted(directory.glob("*.pdf"))

        if not pdf_paths:
            logger.error("No PDF files found in %s", directory)
            return IngestionSummary(0, 0, 0, 0, 0, 0)

        semaphore = asyncio.Semaphore(self._concurrency)

        async def convert_with_limit(path: Path) -> tuple[Path, list[Any]]:
            async with semaphore:
                return path, await self.convert_pdf_to_graph_documents(path)

        tasks = [asyncio.create_task(convert_with_limit(path)) for path in pdf_paths]
        results = await asyncio.gather(*tasks)

        processed = 0
        failed = 0
        stored_docs = 0
        stored_nodes = 0
        stored_relationships = 0

        for _path, documents in results:
            if not documents:
                failed += 1
                continue

            processed += 1
            stored_docs += len(documents)
            storage = self.store_graph_documents(documents)
            stored_nodes += storage.nodes
            stored_relationships += storage.relationships

        return IngestionSummary(
            discovered_pdfs=len(pdf_paths),
            processed_pdfs=processed,
            failed_pdfs=failed,
            stored_graph_documents=stored_docs,
            stored_nodes=stored_nodes,
            stored_relationships=stored_relationships,
        )
