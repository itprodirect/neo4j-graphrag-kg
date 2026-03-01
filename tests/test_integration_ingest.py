"""Integration tests for the ingestion pipeline + idempotency.

Skipped when Neo4j is not reachable.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from typer.testing import CliRunner

from neo4j_graphrag_kg.cli import app
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
            f"Node count changed: {nodes_after_1} → {nodes_after_2}"
        )
        assert rels_after_2 == rels_after_1, (
            f"Rel count changed: {rels_after_1} → {rels_after_2}"
        )
        assert entities_after_2 == entities_after_1, (
            f"Entity count changed: {entities_after_1} → {entities_after_2}"
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
