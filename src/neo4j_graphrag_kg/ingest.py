"""Ingestion pipeline: read file → chunk → extract → upsert to Neo4j.

Orchestrates the full ingestion flow with structured logging.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from neo4j import Driver

from neo4j_graphrag_kg.chunker import chunk_text
from neo4j_graphrag_kg.extractor import build_edges, extract_entities
from neo4j_graphrag_kg.ids import chunk_id as make_chunk_id
from neo4j_graphrag_kg.ids import edge_id as make_edge_id
from neo4j_graphrag_kg.upsert import (
    upsert_chunks,
    upsert_document,
    upsert_entities,
    upsert_mentions,
    upsert_related,
)

logger = logging.getLogger(__name__)


def ingest_file(
    driver: Driver,
    database: str,
    *,
    input_path: Path,
    doc_id: str,
    title: str,
    source: str = "",
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> dict[str, Any]:
    """Run the full ingestion pipeline for a single text file.

    Returns a summary dict with counts and timing.
    """
    t0 = time.perf_counter()

    # 1. Read input
    logger.info("Reading %s", input_path)
    text = input_path.read_text(encoding="utf-8")
    logger.info("Read %d characters", len(text))

    # 2. Chunk
    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    logger.info("Created %d chunks (size=%d, overlap=%d)", len(chunks), chunk_size, chunk_overlap)

    # 3. Prepare chunk tuples for extractor
    chunk_tuples: list[tuple[str, str]] = [
        (make_chunk_id(doc_id, c.idx), c.text) for c in chunks
    ]

    # 4. Extract entities
    entities = extract_entities(chunk_tuples)
    entity_set = {e.id for e in entities}
    logger.info("Extracted %d unique entities", len(entities))

    # 5. Build co-occurrence edges
    edges = build_edges(chunk_tuples, doc_id=doc_id, entity_set=entity_set)
    logger.info("Built %d RELATED_TO edges", len(edges))

    # 6. Upsert Document
    upsert_document(driver, database, doc_id=doc_id, title=title, source=source)

    # 7. Upsert Chunks + HAS_CHUNK
    chunk_rows = [
        {
            "id": make_chunk_id(doc_id, c.idx),
            "document_id": doc_id,
            "idx": c.idx,
            "text": c.text,
        }
        for c in chunks
    ]
    upsert_chunks(driver, database, chunk_rows)

    # 8. Upsert Entities
    entity_rows = [{"id": e.id, "name": e.name, "type": e.type} for e in entities]
    upsert_entities(driver, database, entity_rows)

    # 9. Upsert MENTIONS (chunk → entity)
    mention_rows: list[dict[str, Any]] = []
    for cid, chunk_text_value in chunk_tuples:
        from neo4j_graphrag_kg.extractor import extract_entities_from_chunk

        found = extract_entities_from_chunk(chunk_text_value)
        for slug, _name in found:
            if slug in entity_set:
                mention_rows.append({"chunk_id": cid, "entity_id": slug})
    upsert_mentions(driver, database, mention_rows)

    # 10. Upsert RELATED_TO
    related_rows = [
        {
            "id": make_edge_id(
                e.doc_id,
                e.chunk_id,
                e.source_id,
                "simple",
                e.target_id,
            ),
            "source_id": e.source_id,
            "target_id": e.target_id,
            "doc_id": e.doc_id,
            "chunk_id": e.chunk_id,
            "extractor": "simple",
            "confidence": e.confidence,
            "evidence": e.evidence,
        }
        for e in edges
    ]
    upsert_related(driver, database, related_rows)

    elapsed = time.perf_counter() - t0
    summary = {
        "doc_id": doc_id,
        "chars": len(text),
        "chunks": len(chunks),
        "entities": len(entities),
        "mentions": len(mention_rows),
        "edges": len(edges),
        "elapsed_s": round(elapsed, 2),
    }
    logger.info("Ingestion complete: %s", summary)
    return summary
