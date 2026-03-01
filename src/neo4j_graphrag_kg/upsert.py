"""Batched Neo4j upsert operations using UNWIND + MERGE.

All writes go through managed write transactions with UNWIND $rows batching.
Never single-row MERGE in a Python loop.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from neo4j import Driver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic batch helper
# ---------------------------------------------------------------------------

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
            session.execute_write(_write_rows, cypher, batch)
            total += len(batch)
            logger.info("Wrote batch %d-%d (%d rows)", i, i + len(batch), len(batch))
    return total


# ---------------------------------------------------------------------------
# Document upsert
# ---------------------------------------------------------------------------

_UPSERT_DOCUMENT = """\
UNWIND $rows AS row
MERGE (d:Document {id: row.id})
SET d.title      = row.title,
    d.source     = row.source,
    d.created_at = row.created_at
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
