"""Batched Neo4j upsert operations using UNWIND + MERGE.

All writes go through managed write transactions with UNWIND $rows batching.
Never single-row MERGE in a Python loop.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Callable
from typing import Any

from neo4j import Driver
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic batch helper
# ---------------------------------------------------------------------------

_TRANSIENT_WRITE_ERRORS = (TransientError, ServiceUnavailable, SessionExpired)


def _execute_write_with_retry(
    session: Any,
    callback: Callable[[Any, str, list[dict[str, Any]]], None],
    cypher: str,
    rows: list[dict[str, Any]],
    max_attempts: int = 3,
    base_backoff_s: float = 0.2,
) -> None:
    """Execute a managed write with bounded retry for transient driver errors."""
    attempts = max(1, max_attempts)
    for attempt in range(1, attempts + 1):
        try:
            session.execute_write(callback, cypher, rows)
            return
        except _TRANSIENT_WRITE_ERRORS as exc:
            if attempt >= attempts:
                raise
            backoff = base_backoff_s * (2 ** (attempt - 1))
            logger.warning(
                "Transient write failed (%s), retrying attempt %d/%d in %.2fs",
                exc.__class__.__name__,
                attempt + 1,
                attempts,
                backoff,
            )
            time.sleep(backoff)


def _run_batch(
    driver: Driver,
    database: str,
    cypher: str,
    rows: list[dict[str, Any]],
    batch_size: int = 500,
) -> int:
    """Execute *cypher* with UNWIND batching inside managed write transactions.

    Returns the total number of rows processed.
    """

    def _write_rows(tx: Any, query: str, batch_rows: list[dict[str, Any]]) -> None:
        # consume() ensures server execution is completed in the managed tx callback.
        tx.run(query, rows=batch_rows).consume()

    total = 0
    with driver.session(database=database) as session:
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            _execute_write_with_retry(session, _write_rows, cypher, batch)
            total += len(batch)
            logger.info("Wrote batch %d-%d (%d rows)", i, i + len(batch), len(batch))
    return total


# ---------------------------------------------------------------------------
# Document upsert
# ---------------------------------------------------------------------------

_UPSERT_DOCUMENT = """\
UNWIND $rows AS row
MERGE (d:Document {id: row.id})
ON CREATE SET d.created_at = row.created_at
SET d.title  = row.title,
    d.source = row.source
"""


def upsert_document(
    driver: Driver,
    database: str,
    *,
    doc_id: str,
    title: str,
    source: str = "",
) -> None:
    """MERGE a single Document node (batched with one-row list)."""
    rows = [{
        "id": doc_id,
        "title": title,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }]
    _run_batch(driver, database, _UPSERT_DOCUMENT, rows)
    logger.info("Upserted Document id=%s", doc_id)


# ---------------------------------------------------------------------------
# Chunk upsert + HAS_CHUNK relationship
# ---------------------------------------------------------------------------

_UPSERT_CHUNKS = """\
UNWIND $rows AS row
MERGE (c:Chunk {id: row.id})
SET c.document_id = row.document_id,
    c.idx         = row.idx,
    c.text        = row.text
WITH c, row
MATCH (d:Document {id: row.document_id})
MERGE (d)-[:HAS_CHUNK]->(c)
"""


def upsert_chunks(
    driver: Driver,
    database: str,
    rows: list[dict[str, Any]],
) -> int:
    """MERGE Chunk nodes and HAS_CHUNK relationships."""
    count = _run_batch(driver, database, _UPSERT_CHUNKS, rows)
    logger.info("Upserted %d chunks", count)
    return count


# ---------------------------------------------------------------------------
# Entity upsert
# ---------------------------------------------------------------------------

_UPSERT_ENTITIES = """\
UNWIND $rows AS row
MERGE (e:Entity {id: row.id})
ON CREATE SET e.name = row.name
SET e.name = coalesce(e.name, row.name),
    e.type = row.type
WITH e, row, coalesce(e.aliases, [e.name]) AS aliases
SET e.aliases = CASE
    WHEN row.name IN aliases THEN aliases
    ELSE aliases + row.name
END
SET e.alias_count = size(e.aliases)
"""


def upsert_entities(
    driver: Driver,
    database: str,
    rows: list[dict[str, Any]],
) -> int:
    """MERGE Entity nodes."""
    count = _run_batch(driver, database, _UPSERT_ENTITIES, rows)
    logger.info("Upserted %d entities", count)
    return count


# ---------------------------------------------------------------------------
# MENTIONS relationship  (Chunk)-[:MENTIONS]->(Entity)
# ---------------------------------------------------------------------------

_UPSERT_MENTIONS = """\
UNWIND $rows AS row
MATCH (c:Chunk {id: row.chunk_id})
MATCH (e:Entity {id: row.entity_id})
MERGE (c)-[:MENTIONS]->(e)
"""


def upsert_mentions(
    driver: Driver,
    database: str,
    rows: list[dict[str, Any]],
) -> int:
    """MERGE MENTIONS relationships between Chunks and Entities."""
    count = _run_batch(driver, database, _UPSERT_MENTIONS, rows)
    logger.info("Upserted %d MENTIONS edges", count)
    return count


# ---------------------------------------------------------------------------
# Document-scoped reconciliation cleanup
# ---------------------------------------------------------------------------

_DELETE_DOC_CHUNK_BATCH = """\
MATCH (:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
WITH c LIMIT $limit
DETACH DELETE c
RETURN count(c) AS deleted
"""

_DELETE_DOC_RELATED_BATCH = """\
MATCH ()-[r:RELATED_TO {doc_id: $doc_id}]->()
WITH r LIMIT $limit
DELETE r
RETURN count(r) AS deleted
"""


def purge_document_subgraph(
    driver: Driver,
    database: str,
    *,
    doc_id: str,
    batch_size: int = 1000,
) -> dict[str, int]:
    """Delete stale chunk/mention and document-scoped RELATED_TO data."""
    safe_batch = max(1, int(batch_size))

    def _delete_batch(tx: Any, query: str, target_doc_id: str, limit: int) -> int:
        record = tx.run(query, doc_id=target_doc_id, limit=limit).single()
        if not record:
            return 0
        return int(record["deleted"])

    deleted_chunks = 0
    deleted_related = 0

    with driver.session(database=database) as session:
        while True:
            deleted_raw = session.execute_write(
                _delete_batch,
                _DELETE_DOC_CHUNK_BATCH,
                doc_id,
                safe_batch,
            )
            deleted = deleted_raw if isinstance(deleted_raw, int) else 0
            if deleted == 0:
                break
            deleted_chunks += deleted

        while True:
            deleted_raw = session.execute_write(
                _delete_batch,
                _DELETE_DOC_RELATED_BATCH,
                doc_id,
                safe_batch,
            )
            deleted = deleted_raw if isinstance(deleted_raw, int) else 0
            if deleted == 0:
                break
            deleted_related += deleted

    logger.info(
        "Purged doc_id=%s stale subgraph: chunks=%d related_edges=%d",
        doc_id,
        deleted_chunks,
        deleted_related,
    )
    return {
        "chunks": deleted_chunks,
        "related_edges": deleted_related,
    }

# ---------------------------------------------------------------------------
# RELATED_TO relationship  (Entity)-[:RELATED_TO]->(Entity)
# ---------------------------------------------------------------------------

_UPSERT_RELATED = """\
UNWIND $rows AS row
MATCH (e1:Entity {id: row.source_id})
MATCH (e2:Entity {id: row.target_id})
OPTIONAL MATCH (e1)-[legacy:RELATED_TO {
    doc_id: row.doc_id,
    chunk_id: row.chunk_id,
    extractor: row.extractor
}]->(e2)
WITH e1, e2, row, [lr IN collect(legacy) WHERE lr IS NOT NULL] AS legacy_rels
FOREACH (lr IN legacy_rels | SET lr.id = coalesce(lr.id, row.id))
MERGE (e1)-[r:RELATED_TO {id: row.id}]->(e2)
SET r.extractor  = row.extractor,
    r.doc_id     = row.doc_id,
    r.chunk_id   = row.chunk_id,
    r.confidence = row.confidence,
    r.evidence   = row.evidence,
    r.type       = row.type
"""


def upsert_related(
    driver: Driver,
    database: str,
    rows: list[dict[str, Any]],
) -> int:
    """MERGE RELATED_TO relationships between Entities."""
    count = _run_batch(driver, database, _UPSERT_RELATED, rows)
    logger.info("Upserted %d RELATED_TO edges", count)
    return count
