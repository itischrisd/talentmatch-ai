from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain_neo4j import Neo4jGraph

from talentmatch.config.config_models import Neo4jSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StorageResult:
    """
    Represents the number of nodes and relationships written to the graph
    """

    nodes: int
    relationships: int


class Neo4jGraphService:
    """
    Provides Neo4j connection, schema setup, and basic maintenance operations
    """

    def __init__(self, *, neo4j: Neo4jSettings) -> None:
        """
        Create a Neo4j service
        :param neo4j: Neo4j connection settings
        """

        self._graph = Neo4jGraph(
            url=str(neo4j.uri),
            username=str(neo4j.username),
            password=neo4j.password.get_secret_value(),
            database=str(neo4j.database),
        )
        logger.info("Connected to Neo4j")
        self._ensure_indexes()

    def _safe_query(self, cypher: str) -> list[dict[str, Any]]:
        try:
            result = self._graph.query(cypher)
            return list(result) if result else []
        except Exception:
            logger.exception("Neo4j query failed")
            return []

    def _reset_database(self) -> None:
        logger.warning("Resetting Neo4j database")
        self._graph.query("MATCH (n) DETACH DELETE n")

        for row in self._safe_query("SHOW CONSTRAINTS"):
            name = str(row.get("name", "")).strip()
            if name:
                self._safe_query(f"DROP CONSTRAINT `{name}` IF EXISTS")

        for row in self._safe_query("SHOW INDEXES"):
            name = str(row.get("name", "")).strip()
            if name and not name.startswith("__"):
                self._safe_query(f"DROP INDEX `{name}` IF EXISTS")

    def _ensure_indexes(self) -> None:
        statements = (
            "CREATE INDEX person_id IF NOT EXISTS FOR (p:Person) ON (p.id)",
            "CREATE INDEX company_id IF NOT EXISTS FOR (c:Company) ON (c.id)",
            "CREATE INDEX skill_id IF NOT EXISTS FOR (s:Skill) ON (s.id)",
        )
        for statement in statements:
            self._safe_query(statement)

    def add_graph_documents(self, graph_documents: list[Any]) -> StorageResult:
        """
        Persist graph documents in Neo4j
        :param graph_documents: GraphDocument objects
        :return: Storage result
        :raises Exception: If Neo4j write fails
        """

        self._graph.add_graph_documents(graph_documents, baseEntityLabel=True, include_source=True)

        nodes = sum(len(getattr(doc, "nodes", [])) for doc in graph_documents)
        relationships = sum(len(getattr(doc, "relationships", [])) for doc in graph_documents)

        logger.info(
            "Stored %d graph document(s) (nodes=%d, relationships=%d)",
            len(graph_documents),
            nodes,
            relationships,
        )

        return StorageResult(nodes=nodes, relationships=relationships)
