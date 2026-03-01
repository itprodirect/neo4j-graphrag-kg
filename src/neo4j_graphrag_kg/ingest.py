"""Ingestion pipeline: read file → chunk → extract → upsert to Neo4j.

Orchestrates the full ingestion flow with structured logging.
All extractors (simple heuristic and LLM-powered) go through the
same pluggable BaseExtractor interface.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from neo4j import Driver

from neo4j_graphrag_kg.chunker import chunk_text
from neo4j_graphrag_kg.extractors.base import BaseExtractor, ExtractionResult
from neo4j_graphrag_kg.extractors.simple import SimpleExtractor
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
        If provided, use this extractor.
        When ``None``, defaults to ``SimpleExtractor()``.

    Returns a summary dict with counts and timing.
    """
    if extractor is None:
        extractor = SimpleExtractor()

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

    # 4. Determine extractor label for provenance
    extractor_name = type(extractor).__name__.lower()
    ext_label = "simple" if "simple" in extractor_name else "llm"

    # 5. Extract entities + relationships per chunk
    all_entities: dict[str, dict[str, str]] = {}   # slug -> {name, type}
    all_mentions: list[dict[str, str]] = []

    # Accumulate relationships per (source, target, type) for cross-chunk
    # deduplication — matching the legacy build_edges() aggregation behaviour.
    # Keys: (src_slug, tgt_slug, rel_type) → first occurrence dict + count.
    edge_acc: dict[tuple[str, str, str], dict[str, Any]] = {}

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

        # Collect relationships — deduplicate by (source, target, type)
        for rel in result.relationships:
            src_slug = slugify(rel.source)
            tgt_slug = slugify(rel.target)
            if not src_slug or not tgt_slug or src_slug == tgt_slug:
                continue
            # Ensure canonical ordering for undirected pairs
            pair_key_src, pair_key_tgt = (
                (src_slug, tgt_slug) if src_slug <= tgt_slug
                else (tgt_slug, src_slug)
            )
            # Ensure both ends exist as entities
            if src_slug not in all_entities:
                all_entities[src_slug] = {"name": rel.source, "type": "Term"}
            if tgt_slug not in all_entities:
                all_entities[tgt_slug] = {"name": rel.target, "type": "Term"}

            rel_type = rel.type or "RELATED_TO"
            key = (pair_key_src, pair_key_tgt, rel_type)

            if key not in edge_acc:
                edge_acc[key] = {
                    "source_id": pair_key_src,
                    "target_id": pair_key_tgt,
                    "doc_id": doc_id,
                    "chunk_id": cid,
                    "extractor": ext_label,
                    "confidence": rel.confidence,
                    "evidence": rel.evidence,
                    "type": rel_type,
                    "_count": 1,
                    "_evidence_parts": [rel.evidence] if rel.evidence else [],
                }
            else:
                acc = edge_acc[key]
                acc["_count"] += 1
                if rel.evidence and len(acc["_evidence_parts"]) < 3:
                    acc["_evidence_parts"].append(rel.evidence)

    # Build final relationship rows with normalized confidence
    max_count = max((e["_count"] for e in edge_acc.values()), default=1)
    all_relationships: list[dict[str, Any]] = []
    for key, acc in sorted(edge_acc.items()):
        confidence = round(acc["_count"] / max_count, 4)
        evidence = "; ".join(acc["_evidence_parts"][:2])
        row = {
            "id": make_edge_id(
                doc_id, acc["chunk_id"],
                acc["source_id"], ext_label, acc["target_id"],
                rel_type=acc["type"],
            ),
            "source_id": acc["source_id"],
            "target_id": acc["target_id"],
            "doc_id": doc_id,
            "chunk_id": acc["chunk_id"],
            "extractor": ext_label,
            "confidence": confidence,
            "evidence": evidence,
            "type": acc["type"],
        }
        all_relationships.append(row)

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
