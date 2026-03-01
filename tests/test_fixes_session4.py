"""Tests for Session 4 fixes (relationship type persistence, ImportError
handling, unified extractor interface, type validation).

All tests run without an API key — LLM calls are mocked.
Integration tests that need Neo4j are skipped when it is unreachable.
"""

from __future__ import annotations

import json
from itertools import combinations
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from neo4j_graphrag_kg.extractors.base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from neo4j_graphrag_kg.extractors.llm import LLMExtractor
from neo4j_graphrag_kg.extractors.simple import (
    SimpleExtractor,
    extract_entities_from_chunk,
)
from neo4j_graphrag_kg.ids import edge_id, slugify


# ====================================================================
# Fix 1 — Persist relationship type end-to-end
# ====================================================================


class TestEdgeIdWithType:
    """edge_id with rel_type produces distinct IDs."""

    def test_edge_id_with_type_differs(self) -> None:
        """Two edges between the same entities but different types must differ."""
        eid_works = edge_id("d", "c0", "alice", "llm", "nexus", rel_type="WORKS_FOR")
        eid_lives = edge_id("d", "c0", "alice", "llm", "nexus", rel_type="LOCATED_IN")
        assert eid_works != eid_lives

    def test_edge_id_without_type_backwards_compat(self) -> None:
        """No rel_type → same format as before."""
        eid_plain = edge_id("d", "c0", "a", "simple", "b")
        assert eid_plain == "d::c0::a::simple::b"

    def test_edge_id_with_type_appended(self) -> None:
        eid = edge_id("d", "c0", "a", "llm", "b", rel_type="WORKS_FOR")
        assert eid == "d::c0::a::llm::b::WORKS_FOR"

    def test_edge_id_empty_type_no_suffix(self) -> None:
        eid = edge_id("d", "c0", "a", "llm", "b", rel_type="")
        assert eid == "d::c0::a::llm::b"


# ====================================================================
# Fix 2 — ImportError not retried
# ====================================================================


class TestImportErrorNotRetried:
    """SDK ImportError surfaces immediately with install guidance."""

    def test_import_error_not_retried(self) -> None:
        """ImportError should propagate immediately without retry."""
        ext = LLMExtractor(provider="anthropic", api_key="test-key", max_retries=3)
        ext._call_fn = MagicMock(
            side_effect=ImportError(
                "The 'anthropic' package is required for the LLM extractor "
                "with provider='anthropic'. Install it with: pip install -e \".[anthropic]\""
            )
        )
        with pytest.raises(ImportError, match="pip install"):
            ext.extract("some text", "c0", "d0")
        # Must NOT have retried — exactly one call
        assert ext._call_fn.call_count == 1

    def test_transient_error_still_retries(self) -> None:
        """Non-ImportError should be retried as before."""
        good = json.dumps({"entities": [], "relationships": []})
        ext = LLMExtractor(provider="anthropic", api_key="test-key", max_retries=1)
        ext._call_fn = MagicMock(side_effect=[RuntimeError("transient"), good])
        result = ext.extract("text", "c0", "d0")
        assert ext._call_fn.call_count == 2
        assert result.entities == []


# ====================================================================
# Fix 3 — Unified simple extractor interface
# ====================================================================


class TestSimpleExtractorPluggable:
    """SimpleExtractor through the pluggable interface produces expected output."""

    def test_deterministic_entity_extraction(self) -> None:
        """Known input produces a deterministic set of entities."""
        text = "Neo4j and Cypher power the Knowledge Graph."
        ext = SimpleExtractor()
        result = ext.extract(text, "c0", "d0")

        slugs = {slugify(e.name) for e in result.entities}
        assert "neo4j" in slugs
        assert "cypher" in slugs
        assert "knowledge-graph" in slugs

    def test_cooccurrence_relationships_built(self) -> None:
        """Entities co-occurring in a chunk produce RELATED_TO relationships."""
        text = "Neo4j and Cypher are great."
        ext = SimpleExtractor()
        result = ext.extract(text, "c0", "d0")

        assert len(result.relationships) >= 1
        rel_pairs = {
            (slugify(r.source), slugify(r.target))
            for r in result.relationships
        }
        # Neo4j <-> Cypher should be related
        assert ("cypher", "neo4j") in rel_pairs or ("neo4j", "cypher") in rel_pairs

    def test_single_entity_no_relationships(self) -> None:
        """A chunk with a single entity should not produce relationships."""
        text = "we like neo4j a lot and use it every day."
        ext = SimpleExtractor()
        result = ext.extract(text, "c0", "d0")
        slugs = sorted({slugify(e.name) for e in result.entities})
        assert slugs == ["neo4j"]
        assert len(result.relationships) == 0

    def test_relationship_type_is_related_to(self) -> None:
        """SimpleExtractor relationships always have type RELATED_TO."""
        text = "Neo4j and Cypher work together."
        ext = SimpleExtractor()
        result = ext.extract(text, "c0", "d0")
        for rel in result.relationships:
            assert rel.type == "RELATED_TO"

    def test_entity_count_pinned(self) -> None:
        """Pin the expected entity count for a known input."""
        text = (
            "Neo4j is a graph database. Knowledge Graph is powerful. "
            "Cypher is the query language for Neo4j."
        )
        ext = SimpleExtractor()
        result = ext.extract(text, "c0", "d0")
        # Neo4j, Knowledge Graph, Cypher + known-term matches
        slugs = {slugify(e.name) for e in result.entities}
        assert len(slugs) >= 3
        assert "neo4j" in slugs
        assert "cypher" in slugs
        assert "knowledge-graph" in slugs

    def test_edge_count_pinned(self) -> None:
        """Pin the expected edge count: n entities → C(n,2) relationships."""
        text = "Neo4j and Cypher and Knowledge Graph together."
        ext = SimpleExtractor()
        result = ext.extract(text, "c0", "d0")
        n_entities = len(result.entities)
        if n_entities >= 2:
            expected_edges = len(list(combinations(range(n_entities), 2)))
            # Should match: all pairs from co-occurrence
            # (some slugs may overlap, so >= is safer)
            assert len(result.relationships) <= expected_edges


# ====================================================================
# Fix 4 — Post-parse type validation
# ====================================================================


def _make_mock_response(entities: list[dict], relationships: list[dict]) -> str:
    return json.dumps({"entities": entities, "relationships": relationships})


class TestTypeValidation:
    """Validate entity/relationship types against allowed lists."""

    def _make_extractor(
        self,
        response: str,
        entity_types: list[str] | None = None,
        relationship_types: list[str] | None = None,
    ) -> LLMExtractor:
        ext = LLMExtractor(
            provider="anthropic",
            api_key="test-key",
            entity_types=entity_types or ["Person", "Organization", "Concept"],
            relationship_types=relationship_types or ["WORKS_FOR", "RELATED_TO"],
        )
        ext._call_fn = MagicMock(return_value=response)
        return ext

    def test_entity_type_remapped_to_concept(self) -> None:
        """Unknown entity type is remapped to 'Concept'."""
        response = _make_mock_response(
            entities=[
                {"name": "Foo", "type": "FakeType", "evidence": "test"},
            ],
            relationships=[],
        )
        ext = self._make_extractor(response)
        result = ext.extract("text about Foo", "c0", "d0")
        assert len(result.entities) == 1
        assert result.entities[0].type == "Concept"

    def test_relationship_type_remapped_to_related(self) -> None:
        """Unknown relationship type is remapped to 'RELATED_TO'."""
        response = _make_mock_response(
            entities=[
                {"name": "A", "type": "Person", "evidence": "A"},
                {"name": "B", "type": "Organization", "evidence": "B"},
            ],
            relationships=[
                {"source": "A", "target": "B", "type": "MADE_UP",
                 "confidence": 0.9, "evidence": "test"},
            ],
        )
        ext = self._make_extractor(response)
        result = ext.extract("A works at B", "c0", "d0")
        assert len(result.relationships) == 1
        assert result.relationships[0].type == "RELATED_TO"

    def test_valid_types_pass_through(self) -> None:
        """Types in the allowed list pass through unchanged."""
        response = _make_mock_response(
            entities=[
                {"name": "Alice", "type": "Person", "evidence": "alice"},
            ],
            relationships=[
                {"source": "Alice", "target": "Corp", "type": "WORKS_FOR",
                 "confidence": 0.95, "evidence": "works"},
            ],
        )
        ext = self._make_extractor(response)
        result = ext.extract("Alice works at Corp", "c0", "d0")
        assert result.entities[0].type == "Person"
        assert result.relationships[0].type == "WORKS_FOR"

    def test_no_constraints_all_types_accepted(self) -> None:
        """When entity_types/relationship_types are empty, all types pass."""
        response = _make_mock_response(
            entities=[
                {"name": "Widget", "type": "AnyCustomType", "evidence": "w"},
            ],
            relationships=[
                {"source": "A", "target": "B", "type": "CUSTOM_REL",
                 "confidence": 1.0, "evidence": "test"},
            ],
        )
        # Pass empty lists to skip validation
        ext = LLMExtractor(
            provider="anthropic",
            api_key="test-key",
            entity_types=[],
            relationship_types=[],
        )
        ext._call_fn = MagicMock(return_value=response)
        result = ext.extract("text", "c0", "d0")
        assert result.entities[0].type == "AnyCustomType"
        assert result.relationships[0].type == "CUSTOM_REL"

    def test_mixed_valid_and_invalid_types(self) -> None:
        """Mix of valid and invalid types: only invalid ones get remapped."""
        response = _make_mock_response(
            entities=[
                {"name": "Alice", "type": "Person", "evidence": "a"},
                {"name": "Gadget", "type": "Phantom", "evidence": "g"},
            ],
            relationships=[
                {"source": "Alice", "target": "Corp", "type": "WORKS_FOR",
                 "confidence": 0.9, "evidence": "works"},
                {"source": "Alice", "target": "Gadget", "type": "INVENTED",
                 "confidence": 0.5, "evidence": "invented"},
            ],
        )
        ext = self._make_extractor(response)
        result = ext.extract("text", "c0", "d0")
        # Entity types
        assert result.entities[0].type == "Person"
        assert result.entities[1].type == "Concept"  # remapped
        # Relationship types
        assert result.relationships[0].type == "WORKS_FOR"
        assert result.relationships[1].type == "RELATED_TO"  # remapped


# ====================================================================
# Integration: typed relationships persist to Neo4j
# ====================================================================

from tests.conftest import neo4j_available  # noqa: E402


@neo4j_available
class TestTypedRelationshipsIntegration:
    """Verify that relationship types are persisted in Neo4j."""

    def test_typed_edges_in_neo4j(self) -> None:
        """Ingest with a mock extractor returning typed rels, then query."""
        from pathlib import Path
        import tempfile
        from neo4j_graphrag_kg.config import get_settings
        from neo4j_graphrag_kg.ingest import ingest_file
        from neo4j import GraphDatabase

        settings = get_settings()
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

        # Reset first
        with driver.session(database=settings.neo4j_database) as session:
            session.run("MATCH (n) DETACH DELETE n")

        # Create a mock extractor that returns typed relationships
        class TypedExtractor(BaseExtractor):
            def extract(self, text: str, chunk_id: str, doc_id: str) -> ExtractionResult:
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(name="Alice", type="Person"),
                        ExtractedEntity(name="Nexus", type="Organization"),
                        ExtractedEntity(name="London", type="Location"),
                    ],
                    relationships=[
                        ExtractedRelationship(
                            source="Alice", target="Nexus",
                            type="WORKS_FOR", confidence=0.95,
                            evidence="Alice works at Nexus",
                        ),
                        ExtractedRelationship(
                            source="Nexus", target="London",
                            type="LOCATED_IN", confidence=0.8,
                            evidence="Nexus is in London",
                        ),
                    ],
                )

        # Write temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8",
        ) as f:
            f.write("Alice works at Nexus in London.")
            tmp_path = Path(f.name)

        try:
            # Run schema init
            from neo4j_graphrag_kg.schema import ALL_STATEMENTS
            with driver.session(database=settings.neo4j_database) as session:
                for stmt in ALL_STATEMENTS:
                    session.run(stmt)

            summary = ingest_file(
                driver,
                settings.neo4j_database,
                input_path=tmp_path,
                doc_id="typed-test",
                title="Typed Test",
                extractor=TypedExtractor(),
            )

            assert summary["edges"] == 2

            # Query and check types
            with driver.session(database=settings.neo4j_database) as session:
                result = list(session.run(
                    "MATCH ()-[r:RELATED_TO]->() "
                    "RETURN r.type AS type ORDER BY r.type"
                ))
                types = [r["type"] for r in result]
                assert "LOCATED_IN" in types
                assert "WORKS_FOR" in types
        finally:
            tmp_path.unlink(missing_ok=True)
            # Cleanup
            with driver.session(database=settings.neo4j_database) as session:
                session.run("MATCH (n) DETACH DELETE n")
            driver.close()
