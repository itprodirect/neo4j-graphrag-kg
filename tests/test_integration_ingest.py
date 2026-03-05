"""Integration tests for the ingestion pipeline + idempotency.

Skipped when Neo4j is not reachable.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from neo4j import GraphDatabase
from typer.testing import CliRunner

from neo4j_graphrag_kg.cli import app
from neo4j_graphrag_kg.config import get_settings
from tests.conftest import neo4j_available

runner = CliRunner()

# Minimal demo content for testing (written to a temp file).
_DEMO_TEXT = dedent("""\
    Neo4j is a leading graph database used for knowledge graphs.
    Cypher is the query language for Neo4j.  Knowledge graphs store
    entities and relationships.  GraphRAG combines graph databases with
    retrieval augmented generation.  Vector search enables semantic lookup.
    Neo4j supports both property graph and vector search features.
""")


def _write_demo(tmp_path: Path) -> Path:
    p = tmp_path / "demo.txt"
    p.write_text(_DEMO_TEXT, encoding="utf-8")
    return p


def _single_value(cypher: str, key: str, **params: object) -> object:
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            record = session.run(cypher, **params).single()
            return record[key] if record else None
    finally:
        driver.close()


def _count_nodes(label: str = "") -> int:
    """Query node count via kg query CLI."""
    q = f"MATCH (n{':' + label if label else ''}) RETURN count(n) AS c"
    result = runner.invoke(app, ["query", "--cypher", q])
    # Parse the last number from the table output
    for line in result.output.strip().splitlines():
        parts = line.strip().split("|")
        for part in parts:
            part = part.strip()
            if part.isdigit():
                return int(part)
    return -1


def _count_rels(rel_type: str = "") -> int:
    """Query relationship count via kg query CLI."""
    r = f"[:{rel_type}]" if rel_type else "[r]"
    q = f"MATCH ()-{r}->() RETURN count(*) AS c"
    result = runner.invoke(app, ["query", "--cypher", q])
    for line in result.output.strip().splitlines():
        parts = line.strip().split("|")
        for part in parts:
            part = part.strip()
            if part.isdigit():
                return int(part)
    return -1


@neo4j_available
def test_reset_clears_all() -> None:
    """kg reset --confirm should leave zero nodes."""
    result = runner.invoke(app, ["reset", "--confirm"])
    assert result.exit_code == 0
    assert _count_nodes() == 0


@neo4j_available
def test_reset_requires_confirm() -> None:
    """kg reset without --confirm should fail."""
    result = runner.invoke(app, ["reset"])
    assert result.exit_code == 1


@neo4j_available
class TestIngestIdempotency:
    """Ingest the same document twice and verify counts do not double."""

    def test_ingest_twice_stable_counts(self, tmp_path: Path) -> None:
        demo = _write_demo(tmp_path)

        # Reset first
        runner.invoke(app, ["reset", "--confirm"])
        runner.invoke(app, ["init-db"])

        # First ingest
        r1 = runner.invoke(app, [
            "ingest",
            "--input", str(demo),
            "--doc-id", "test-idem",
            "--title", "Idempotency Test",
        ])
        assert r1.exit_code == 0

        nodes_after_1 = _count_nodes()
        rels_after_1 = _count_rels()
        entities_after_1 = _count_nodes("Entity")

        assert nodes_after_1 > 0
        assert rels_after_1 > 0
        assert entities_after_1 > 0

        # Second ingest (same doc-id)
        r2 = runner.invoke(app, [
            "ingest",
            "--input", str(demo),
            "--doc-id", "test-idem",
            "--title", "Idempotency Test",
        ])
        assert r2.exit_code == 0

        nodes_after_2 = _count_nodes()
        rels_after_2 = _count_rels()
        entities_after_2 = _count_nodes("Entity")

        # Counts must be stable (idempotent)
        assert nodes_after_2 == nodes_after_1, (
            f"Node count changed: {nodes_after_1} -> {nodes_after_2}"
        )
        assert rels_after_2 == rels_after_1, (
            f"Rel count changed: {rels_after_1} -> {rels_after_2}"
        )
        assert entities_after_2 == entities_after_1, (
            f"Entity count changed: {entities_after_1} -> {entities_after_2}"
        )


@neo4j_available
def test_query_returns_results(tmp_path: Path) -> None:
    """kg query should return results after ingestion."""
    demo = _write_demo(tmp_path)
    runner.invoke(app, ["reset", "--confirm"])
    runner.invoke(app, ["init-db"])
    runner.invoke(app, [
        "ingest", "--input", str(demo),
        "--doc-id", "test-query",
        "--title", "Query Test",
    ])

    result = runner.invoke(app, [
        "query", "--cypher",
        "MATCH (e:Entity) RETURN e.name ORDER BY e.name LIMIT 5",
    ])
    assert result.exit_code == 0
    assert "row" in result.output.lower()


@neo4j_available
def test_reingest_changed_source_replaces_document_subgraph(tmp_path: Path) -> None:
    """Changed-source re-ingest should remove stale chunks/mentions/edges for doc_id."""
    input_path = tmp_path / "replace-doc.txt"
    input_path.write_text(
        "Neo4j and Cypher power graph analytics for teams.",
        encoding="utf-8",
    )

    doc_id = "test-replace"
    runner.invoke(app, ["reset", "--confirm"])
    runner.invoke(app, ["init-db"])

    first = runner.invoke(app, [
        "ingest",
        "--input", str(input_path),
        "--doc-id", doc_id,
        "--title", "Replace Test",
    ])
    assert first.exit_code == 0

    mentions_before = _single_value(
        (
            "MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->"
            "(e:Entity {id: 'cypher'}) "
            "RETURN count(*) AS c"
        ),
        "c",
        doc_id=doc_id,
    )
    related_before = _single_value(
        "MATCH ()-[r:RELATED_TO {doc_id: $doc_id}]-() RETURN count(r) AS c",
        "c",
        doc_id=doc_id,
    )
    assert int(mentions_before or 0) > 0
    assert int(related_before or 0) > 0

    # Overwrite source with content that removes Cypher mentions and co-occurrence edges.
    input_path.write_text(
        "Neo4j workflows are stable and predictable.",
        encoding="utf-8",
    )

    second = runner.invoke(app, [
        "ingest",
        "--input", str(input_path),
        "--doc-id", doc_id,
        "--title", "Replace Test",
    ])
    assert second.exit_code == 0

    stale_cypher_mentions = _single_value(
        (
            "MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->"
            "(e:Entity {id: 'cypher'}) "
            "RETURN count(*) AS c"
        ),
        "c",
        doc_id=doc_id,
    )
    stale_chunk_text = _single_value(
        (
            "MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk) "
            "WHERE c.text CONTAINS 'Cypher' "
            "RETURN count(c) AS c"
        ),
        "c",
        doc_id=doc_id,
    )
    related_after = _single_value(
        "MATCH ()-[r:RELATED_TO {doc_id: $doc_id}]-() RETURN count(r) AS c",
        "c",
        doc_id=doc_id,
    )
    chunk_count_after = _single_value(
        "MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk) RETURN count(c) AS c",
        "c",
        doc_id=doc_id,
    )

    assert int(stale_cypher_mentions or 0) == 0
    assert int(stale_chunk_text or 0) == 0
    assert int(related_after or 0) == 0
    assert int(chunk_count_after or 0) > 0

@neo4j_available
def test_atomic_replace_rolls_back_on_write_failure(tmp_path: Path) -> None:
    """Atomic replace should rollback purge if a downstream write fails."""
    from neo4j_graphrag_kg.upsert import replace_document_subgraph_atomic

    input_path = tmp_path / "replace-rollback.txt"
    input_path.write_text(
        "Neo4j and Cypher power graph analytics for teams.",
        encoding="utf-8",
    )

    doc_id = "test-replace-rollback"
    runner.invoke(app, ["reset", "--confirm"])
    runner.invoke(app, ["init-db"])

    first = runner.invoke(app, [
        "ingest",
        "--input", str(input_path),
        "--doc-id", doc_id,
        "--title", "Rollback Test",
        "--replace-mode", "atomic",
    ])
    assert first.exit_code == 0

    chunks_before = int(_single_value(
        "MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk) RETURN count(c) AS c",
        "c",
        doc_id=doc_id,
    ) or 0)
    mentions_before = int(_single_value(
        (
            "MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->"
            "(e:Entity {id: 'cypher'}) RETURN count(*) AS c"
        ),
        "c",
        doc_id=doc_id,
    ) or 0)

    assert chunks_before > 0
    assert mentions_before > 0

    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        with pytest.raises(Exception):
            replace_document_subgraph_atomic(
                driver,
                settings.neo4j_database,
                doc_id=doc_id,
                title="Rollback Test",
                source="",
                chunk_rows=[
                    {
                        "id": f"{doc_id}::chunk::0",
                        "document_id": doc_id,
                        "idx": 0,
                        "text": "Replacement content",
                    }
                ],
                entity_rows=[
                    {
                        # Invalid id forces write failure mid-transaction.
                        "id": None,
                        "name": "Broken Entity",
                        "type": "Term",
                    }
                ],
                mention_rows=[],
                relationship_rows=[],
            )
    finally:
        driver.close()

    chunks_after = int(_single_value(
        "MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk) RETURN count(c) AS c",
        "c",
        doc_id=doc_id,
    ) or 0)
    mentions_after = int(_single_value(
        (
            "MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->"
            "(e:Entity {id: 'cypher'}) RETURN count(*) AS c"
        ),
        "c",
        doc_id=doc_id,
    ) or 0)

    assert chunks_after == chunks_before
    assert mentions_after == mentions_before
