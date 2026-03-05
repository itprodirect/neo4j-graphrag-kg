"""Unit tests for directional relationship handling in ingest extraction."""

from __future__ import annotations

from neo4j_graphrag_kg.extractors.base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from neo4j_graphrag_kg.ingest import _stage_extract


class _StaticExtractor(BaseExtractor):
    """Extractor stub that returns static entities/relationships."""

    def __init__(self, relationships: list[ExtractedRelationship]) -> None:
        self._relationships = relationships

    def extract(self, text: str, chunk_id: str, doc_id: str) -> ExtractionResult:
        return ExtractionResult(
            entities=[
                ExtractedEntity(name="Alice", type="Person"),
                ExtractedEntity(name="Nexus", type="Organization"),
            ],
            relationships=self._relationships,
        )


def _chunk_rows(text: str) -> list[dict[str, str]]:
    return [{"id": "doc-1::chunk::0", "text": text}]


def test_stage_extract_preserves_relationship_direction() -> None:
    extractor = _StaticExtractor([
        ExtractedRelationship(
            source="Alice",
            target="Nexus",
            type="WORKS_FOR",
            confidence=0.91,
            evidence="Alice works for Nexus",
        ),
    ])

    result = _stage_extract(
        doc_id="doc-1",
        chunk_rows=_chunk_rows("Alice works for Nexus"),
        extractor=extractor,
    )

    relationships = result["relationship_rows"]
    assert len(relationships) == 1
    rel = relationships[0]
    assert rel["source_id"] == "alice"
    assert rel["target_id"] == "nexus"
    assert rel["type"] == "WORKS_FOR"


def test_stage_extract_keeps_reverse_direction_edges_distinct() -> None:
    extractor = _StaticExtractor([
        ExtractedRelationship(
            source="Alice",
            target="Nexus",
            type="WORKS_FOR",
            confidence=0.9,
            evidence="forward",
        ),
        ExtractedRelationship(
            source="Nexus",
            target="Alice",
            type="WORKS_FOR",
            confidence=0.8,
            evidence="reverse",
        ),
    ])

    result = _stage_extract(
        doc_id="doc-1",
        chunk_rows=_chunk_rows("Alice and Nexus relationship records"),
        extractor=extractor,
    )

    relationships = result["relationship_rows"]
    assert len(relationships) == 2
    directions = {(r["source_id"], r["target_id"]) for r in relationships}
    assert ("alice", "nexus") in directions
    assert ("nexus", "alice") in directions
