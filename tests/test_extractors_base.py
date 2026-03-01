"""Unit tests for the base extractor protocol and dataclasses."""

from __future__ import annotations

from neo4j_graphrag_kg.extractors.base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)


class TestExtractedEntity:
    def test_creation(self) -> None:
        e = ExtractedEntity(name="Neo4j", type="Technology")
        assert e.name == "Neo4j"
        assert e.type == "Technology"
        assert e.properties is None

    def test_with_properties(self) -> None:
        e = ExtractedEntity(name="Alice", type="Person", properties={"role": "CEO"})
        assert e.properties == {"role": "CEO"}


class TestExtractedRelationship:
    def test_creation(self) -> None:
        r = ExtractedRelationship(
            source="Alice", target="Nexus", type="WORKS_FOR",
        )
        assert r.source == "Alice"
        assert r.target == "Nexus"
        assert r.type == "WORKS_FOR"
        assert r.confidence == 1.0
        assert r.evidence == ""

    def test_with_metadata(self) -> None:
        r = ExtractedRelationship(
            source="A", target="B", type="USES",
            confidence=0.8, evidence="A uses B",
        )
        assert r.confidence == 0.8
        assert r.evidence == "A uses B"


class TestExtractionResult:
    def test_empty_default(self) -> None:
        result = ExtractionResult()
        assert result.entities == []
        assert result.relationships == []

    def test_with_data(self) -> None:
        result = ExtractionResult(
            entities=[ExtractedEntity(name="X", type="Concept")],
            relationships=[
                ExtractedRelationship(source="X", target="Y", type="RELATED_TO"),
            ],
        )
        assert len(result.entities) == 1
        assert len(result.relationships) == 1


class TestBaseExtractorABC:
    def test_cannot_instantiate_directly(self) -> None:
        try:
            BaseExtractor()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_subclass_works(self) -> None:
        class DummyExtractor(BaseExtractor):
            def extract(self, text: str, chunk_id: str, doc_id: str) -> ExtractionResult:
                return ExtractionResult()

        ext = DummyExtractor()
        result = ext.extract("hello", "c0", "d0")
        assert result.entities == []
