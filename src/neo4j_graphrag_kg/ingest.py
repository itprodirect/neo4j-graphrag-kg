"""Ingestion pipeline: read file → chunk → extract → upsert to Neo4j.

Orchestrates the full ingestion flow with structured logging.
Supports pluggable extractors (simple heuristic or LLM-powered).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from neo4j import Driver

from neo4j_graphrag_kg.chunker import chunk_text
from neo4j_graphrag_kg.extractors.base import BaseExtractor, ExtractionResult
from neo4j_graphrag_kg.extractors.simple import (
    build_edges,
    extract_entities,
    extract_entities_from_chunk,
)
from neo4j_graphrag_kg.ids import chunk_id as make_chunk_id
from neo4j_graphrag_kg.ids import edge_id as make_edge_id
from neo4j_graphrag_kg.ids import slugify
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
    extractor: BaseExtractor | None = None,
) -> dict[str, Any]:
    """Run the full ingestion pipeline for a single text file.

    Parameters
    ----------
    extractor:
        If provided, use this extractor instead of the default heuristic.
        When ``None``, falls back to the simple (regex) extractor via the
        legacy code path for full backward compatibility.

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

    # 3. Prepare chunk tuples
    chunk_tuples: list[tuple[str, str]] = [
        (make_chunk_id(doc_id, c.idx), c.text) for c in chunks
    ]

    # 4 & 5. Extract entities + edges — pluggable or legacy path
    if extractor is not None:
        return _ingest_with_extractor(
            driver, database, extractor,
            doc_id=doc_id, title=title, source=source,
            chunks=chunks, chunk_tuples=chunk_tuples, t0=t0,
            text=text,
        )

    # --- Legacy simple-extractor path (preserves exact old behaviour) ---
    entities = extract_entities(chunk_tuples)
    entity_set = {e.id for e in entities}
    logger.info("Extracted %d unique entities", len(entities))

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

    # 9. Upsert MENTIONS
    mention_rows: list[dict[str, Any]] = []
    for cid, chunk_text_value in chunk_tuples:
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
            "type": "RELATED_TO",
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


def _ingest_with_extractor(
    driver: Driver,
    database: str,
    extractor: BaseExtractor,
    *,
    doc_id: str,
    title: str,
    source: str,
    chunks: list,
    chunk_tuples: list[tuple[str, str]],
    t0: float,
    text: str,
) -> dict[str, Any]:
    """Run ingestion using a pluggable BaseExtractor instance.

    Collects extraction results from each chunk, deduplicates entities
    by slug, and batches all upserts via UNWIND MERGE.
    """
    extractor_name = type(extractor).__name__.lower()
    if "simple" in extractor_name:
        ext_label = "simple"
    else:
        ext_label = "llm"

    all_entities: dict[str, dict[str, str]] = {}   # slug -> {name, type}
    all_mentions: list[dict[str, str]] = []
    all_relationships: list[dict[str, Any]] = []

    for cid, chunk_text_val in chunk_tuples:
        result: ExtractionResult = extractor.extract(
            text=chunk_text_val,
            chunk_id=cid,
            doc_id=doc_id,
        )

        # Collect entities (deduplicate by slug)
        for ent in result.entities:
            slug = slugify(ent.name)
            if slug and slug not in all_entities:
                all_entities[slug] = {"name": ent.name, "type": ent.type}
            if slug:
                all_mentions.append({"chunk_id": cid, "entity_id": slug})

        # Collect relationships
        for rel in result.relationships:
            src_slug = slugify(rel.source)
            tgt_slug = slugify(rel.target)
            if not src_slug or not tgt_slug or src_slug == tgt_slug:
                continue
            # Ensure both ends exist as entities
            if src_slug not in all_entities:
                all_entities[src_slug] = {"name": rel.source, "type": "Term"}
            if tgt_slug not in all_entities:
                all_entities[tgt_slug] = {"name": rel.target, "type": "Term"}
            rel_type = rel.type or "RELATED_TO"
            all_relationships.append({
                "id": make_edge_id(
                    doc_id, cid, src_slug, ext_label, tgt_slug,
                    rel_type=rel_type,
                ),
                "source_id": src_slug,
                "target_id": tgt_slug,
                "doc_id": doc_id,
                "chunk_id": cid,
                "extractor": ext_label,
                "confidence": rel.confidence,
                "evidence": rel.evidence,
                "type": rel_type,
            })

    logger.info("Extracted %d unique entities via extractor", len(all_entities))
    logger.info("Found %d relationships via extractor", len(all_relationships))

    # --- Upserts (all batched via UNWIND MERGE) ---

    upsert_document(driver, database, doc_id=doc_id, title=title, source=source)

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

    entity_rows = [
        {"id": slug, "name": info["name"], "type": info["type"]}
        for slug, info in all_entities.items()
    ]
    upsert_entities(driver, database, entity_rows)

    # Deduplicate mentions
    seen_mentions: set[tuple[str, str]] = set()
    deduped_mentions: list[dict[str, str]] = []
    for m in all_mentions:
        key = (m["chunk_id"], m["entity_id"])
        if key not in seen_mentions:
            seen_mentions.add(key)
            deduped_mentions.append(m)
    upsert_mentions(driver, database, deduped_mentions)

    upsert_related(driver, database, all_relationships)

    elapsed = time.perf_counter() - t0
    summary = {
        "doc_id": doc_id,
        "chars": len(text),
        "chunks": len(chunk_tuples),
        "entities": len(all_entities),
        "mentions": len(deduped_mentions),
        "edges": len(all_relationships),
        "elapsed_s": round(elapsed, 2),
    }
    logger.info("Ingestion complete: %s", summary)
    return summary
