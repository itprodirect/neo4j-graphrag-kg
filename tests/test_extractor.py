"""Unit tests for the entity extractor and edge builder."""

from __future__ import annotations

from neo4j_graphrag_kg.extractor import (
    build_edges,
    extract_entities,
    extract_entities_from_chunk,
)


class TestExtractEntitiesFromChunk:
    def test_capitalised_phrases(self) -> None:
        text = "Neo4j is a graph database. Knowledge Graph is powerful."
        found = dict(extract_entities_from_chunk(text))
        assert "neo4j" in found
        assert "knowledge-graph" in found

    def test_known_terms_case_insensitive(self) -> None:
        text = "We use neo4j and cypher for our knowledge graph."
        found = dict(extract_entities_from_chunk(text))
        assert "neo4j" in found
        assert "cypher" in found
        assert "knowledge-graph" in found

    def test_dedup_by_slug(self) -> None:
        text = "Neo4j and Neo4j are the same."
        found = extract_entities_from_chunk(text)
        slugs = [s for s, _n in found]
        assert slugs.count("neo4j") == 1

    def test_known_terms_use_word_boundaries(self) -> None:
        text = "Pragmatics and fragments should not trigger term extraction."
        found = dict(extract_entities_from_chunk(text))
        assert "rag" not in found

    def test_known_terms_match_standalone_token(self) -> None:
        text = "RAG works well with retrieval augmented generation."
        found = dict(extract_entities_from_chunk(text))
        assert "rag" in found
        assert "retrieval-augmented-generation" in found

    def test_empty_text(self) -> None:
        assert extract_entities_from_chunk("") == []


class TestExtractEntities:
    def test_basic(self) -> None:
        chunks = [
            ("c0", "Neo4j is a great graph database."),
            ("c1", "Knowledge Graph powers modern search."),
        ]
        entities = extract_entities(chunks)
        ids = {e.id for e in entities}
        assert "neo4j" in ids
        assert "knowledge-graph" in ids

    def test_frequency_threshold(self) -> None:
        chunks = [
            ("c0", "RareEntity appears only once."),
            ("c1", "No mention here."),
        ]
        entities_min1 = extract_entities(chunks, min_frequency=1)
        entities_min2 = extract_entities(chunks, min_frequency=2)
        # RareEntity appears in only 1 chunk
        ids_1 = {e.id for e in entities_min1}
        ids_2 = {e.id for e in entities_min2}
        assert "rareentity" in ids_1
        assert "rareentity" not in ids_2

    def test_type_is_term(self) -> None:
        chunks = [("c0", "Neo4j rocks.")]
        entities = extract_entities(chunks)
        for e in entities:
            assert e.type == "Term"

    def test_returns_sorted_by_name(self) -> None:
        chunks = [("c0", "Zebra and Apple and Mango.")]
        entities = extract_entities(chunks)
        names = [e.name.lower() for e in entities]
        assert names == sorted(names)


class TestBuildEdges:
    def test_cooccurrence(self) -> None:
        # Two entities in the same chunk should produce an edge
        text = "Neo4j and Cypher work together."
        chunks = [("c0", text)]
        entity_set = {"neo4j", "cypher"}
        edges = build_edges(chunks, doc_id="doc-1", entity_set=entity_set)
        assert len(edges) >= 1
        pair = {edges[0].source_id, edges[0].target_id}
        assert pair == {"neo4j", "cypher"}

    def test_no_edge_for_single_entity(self) -> None:
        text = "Only Neo4j mentioned here."
        chunks = [("c0", text)]
        entity_set = {"neo4j"}
        edges = build_edges(chunks, doc_id="d1", entity_set=entity_set)
        assert edges == []

    def test_edge_metadata(self) -> None:
        text = "Neo4j and Cypher are friends."
        chunks = [("c0", text)]
        entity_set = {"neo4j", "cypher"}
        edges = build_edges(chunks, doc_id="doc-1", entity_set=entity_set)
        e = edges[0]
        assert e.doc_id == "doc-1"
        assert e.chunk_id == "c0"
        assert 0.0 <= e.confidence <= 1.0
        assert len(e.evidence) > 0
