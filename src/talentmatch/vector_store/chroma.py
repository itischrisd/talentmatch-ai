from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import AzureOpenAIEmbeddings

from talentmatch.config import load_settings, resolve_repo_root

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VectorStoreService:
    """
    Provides a Chroma-backed vector store for document ingestion and retrieval.
    """

    store: Chroma

    def add_documents(self, documents: list[Document]) -> int:
        if not documents:
            return 0
        try :
            self.store.add_documents(documents)
        except Exception as e:
            logger.error("Error adding documents to Chroma: %s", e)
            raise e
        logger.info("Added %s document chunk(s) to Chroma", len(documents))
        return len(documents)

    def similarity_search(self, query: str, *, k: int) -> list[Document]:
        return self.store.similarity_search(query, k=int(k))


@lru_cache(maxsize=1)
def get_vector_store_service() -> VectorStoreService:
    settings = load_settings()
    repo_root = resolve_repo_root()

    persist_dir = Path(settings.vector_store.persist_dir)
    persist_path = persist_dir if persist_dir.is_absolute() else (repo_root / persist_dir)
    persist_path.mkdir(parents=True, exist_ok=True)

    azure = settings.azure_openai
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=azure.endpoint,
        api_key=azure.api_key,
        api_version=azure.api_version,
        azure_deployment=azure.embeddings_deployment,
    )

    store = Chroma(
        collection_name=settings.vector_store.collection_name,
        persist_directory=str(persist_path),
        embedding_function=embeddings,
    )

    logger.info(
        "Chroma vector store ready (collection=%s, persist=%s)",
        settings.vector_store.collection_name,
        str(persist_path),
    )
    return VectorStoreService(store=store)
