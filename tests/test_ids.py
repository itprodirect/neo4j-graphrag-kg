"""Unit tests for the ids module (slugify + deterministic IDs)."""

from __future__ import annotations

from neo4j_graphrag_kg.ids import chunk_id, edge_id, entity_id, slugify


class TestSlugify:
    def test_basic(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_punctuation_removed(self) -> None:
        assert slugify("Neo4j, Inc.") == "neo4j-inc"

    def test_extra_whitespace_collapsed(self) -> None:
        assert slugify("  Knowledge   Graph  ") == "knowledge-graph"

    def test_unicode(self) -> None:
        assert slugify("Ñoño") == "nono"

    def test_mixed_case(self) -> None:
        assert slugify("GraphRAG") == "graphrag"

    def test_hyphens_preserved(self) -> None:
        assert slugify("co-occurrence") == "co-occurrence"

    def test_symbol_tokens_plus_plus(self) -> None:
        assert slugify("C++") == "c-plus-plus"

    def test_symbol_tokens_sharp(self) -> None:
        assert slugify("C#") == "c-sharp"

    def test_empty(self) -> None:
        assert slugify("") == ""

    def test_only_punctuation(self) -> None:
        assert slugify("!!!") == ""

    def test_deterministic(self) -> None:
        """Same input must always produce same output."""
        assert slugify("Neo4j") == slugify("Neo4j")
        assert slugify("Neo4j") == slugify("  Neo4j  ")


class TestEntityId:
    def test_basic(self) -> None:
        assert entity_id("Knowledge Graph") == "knowledge-graph"

    def test_case_insensitive_dedup(self) -> None:
        assert entity_id("neo4j") == entity_id("Neo4j")
        assert entity_id("neo4j") == entity_id("NEO4J")


class TestChunkId:
    def test_format(self) -> None:
        assert chunk_id("doc-1", 0) == "doc-1::chunk::0"
        assert chunk_id("doc-1", 42) == "doc-1::chunk::42"

    def test_deterministic(self) -> None:
        assert chunk_id("doc-1", 3) == chunk_id("doc-1", 3)


class TestEdgeId:
    def test_format(self) -> None:
        assert edge_id("doc-1", "doc-1::chunk::0", "a", "simple", "b") == (
            "doc-1::doc-1::chunk::0::a::simple::b"
        )

    def test_deterministic(self) -> None:
        assert edge_id("demo", "demo::chunk::2", "neo4j", "simple", "cypher") == edge_id(
            "demo", "demo::chunk::2", "neo4j", "simple", "cypher"
        )
