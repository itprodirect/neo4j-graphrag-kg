"""Service boundary for graph operations and ingestion pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypedDict

from neo4j import Driver

from neo4j_graphrag_kg.config import Settings, get_settings
from neo4j_graphrag_kg.ingest import IngestPipelineService
from neo4j_graphrag_kg.neo4j_client import close_driver, get_driver
from neo4j_graphrag_kg.upsert import Neo4jGraphStore


class GraphDiagnosticsChecks(TypedDict):
    """Named graph consistency counters."""

    documents_without_chunks: int
    orphan_chunks: int
    related_edges_without_document: int
    orphan_entities: int


class GraphDiagnostics(TypedDict):
    """Lightweight graph consistency summary."""

    status: str
    stale_total: int
    checks: GraphDiagnosticsChecks


class GraphService:
    """Explicit graph service with injected driver/database dependencies."""

    def __init__(self, driver: Driver, database: str) -> None:
        self._driver = driver
        self._database = database

    @property
    def database(self) -> str:
        return self._database

    def verify_connectivity(self) -> None:
        self._driver.verify_connectivity()

    def run(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher, params or {})
            return [dict(record) for record in result]

    def session(self) -> Any:
        """Return a Neo4j session bound to the configured database."""
        return self._driver.session(database=self._database)

    def reset(self, *, batch_size: int = 10000) -> int:
        deleted = 0
        with self._driver.session(database=self._database) as session:
            while True:
                record = session.run(
                    f"MATCH (n) WITH n LIMIT {batch_size} DETACH DELETE n RETURN count(*) AS c"
                ).single()
                count = record["c"] if record else 0
                if count == 0:
                    break
                deleted += int(count)
        return deleted

    def diagnostics(self) -> GraphDiagnostics:
        """Return lightweight graph consistency indicators."""
        with self._driver.session(database=self._database) as session:
            docs_without_chunks_row = session.run(
                "MATCH (d:Document) WHERE NOT (d)-[:HAS_CHUNK]->(:Chunk) "
                "RETURN count(d) AS c"
            ).single()
            orphan_chunks_row = session.run(
                "MATCH (c:Chunk) WHERE NOT (:Document)-[:HAS_CHUNK]->(c) "
                "RETURN count(c) AS c"
            ).single()
            related_without_doc_row = session.run(
                "MATCH ()-[r:RELATED_TO]->() "
                "WHERE r.doc_id IS NOT NULL "
                "AND NOT EXISTS { MATCH (:Document {id: r.doc_id}) } "
                "RETURN count(r) AS c"
            ).single()
            orphan_entities_row = session.run(
                "MATCH (e:Entity) "
                "WHERE NOT EXISTS { MATCH (:Chunk)-[:MENTIONS]->(e) } "
                "AND NOT EXISTS { MATCH (e)-[:RELATED_TO]-() } "
                "RETURN count(e) AS c"
            ).single()

        checks: GraphDiagnosticsChecks = {
            "documents_without_chunks": (
                int(docs_without_chunks_row["c"]) if docs_without_chunks_row else 0
            ),
            "orphan_chunks": int(orphan_chunks_row["c"]) if orphan_chunks_row else 0,
            "related_edges_without_document": (
                int(related_without_doc_row["c"]) if related_without_doc_row else 0
            ),
            "orphan_entities": int(orphan_entities_row["c"]) if orphan_entities_row else 0,
        }
        stale_total = (
            checks["documents_without_chunks"]
            + checks["orphan_chunks"]
            + checks["related_edges_without_document"]
            + checks["orphan_entities"]
        )
        return {
            "status": "ok" if stale_total == 0 else "attention",
            "stale_total": stale_total,
            "checks": checks,
        }


@dataclass
class ServiceContainer:
    """Application service bundle with explicit lifecycle management."""

    settings: Settings
    driver: Driver
    graph: GraphService
    ingest: IngestPipelineService
    _close: Callable[[], None]

    def close(self) -> None:
        self._close()


def build_service_container(
    settings: Settings | None = None,
    *,
    driver: Driver | None = None,
) -> ServiceContainer:
    """Bootstrap app services.

    This is the default singleton boundary for runtime entrypoints.
    """
    resolved_settings = settings or get_settings()
    if driver is None:
        resolved_driver = get_driver(resolved_settings)
        close_fn: Callable[[], None] = close_driver
    else:
        resolved_driver = driver
        close_fn = resolved_driver.close

    database = resolved_settings.neo4j_database
    graph = GraphService(resolved_driver, database)
    graph_store = Neo4jGraphStore(resolved_driver, database)
    ingest = IngestPipelineService(resolved_driver, database, graph_store=graph_store)

    return ServiceContainer(
        settings=resolved_settings,
        driver=resolved_driver,
        graph=graph,
        ingest=ingest,
        _close=close_fn,
    )
