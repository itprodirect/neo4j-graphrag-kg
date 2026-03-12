"""Unit tests for ingestion summary fields."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from neo4j_graphrag_kg import ingest as ingest_mod


class _StubGraphStore:
    """Minimal GraphStore that returns canned results for summary tests."""

    def replace_document_subgraph_atomic(
        self, **_kwargs: Any
    ) -> dict[str, Any]:
        return {
            "purged": {"chunks": 0, "related_edges": 0, "entities": 0},
            "written": {"chunks": 1, "entities": 1, "mentions": 1, "edges": 0},
        }

    def purge_document_subgraph(self, **_kwargs: Any) -> dict[str, int]:
        return {"chunks": 0, "related_edges": 0, "entities": 0}

    def upsert_document(self, **_kwargs: Any) -> None:
        pass

    def upsert_chunks(self, rows: list[dict[str, Any]]) -> int:
        return len(rows)

    def upsert_entities(self, rows: list[dict[str, Any]]) -> int:
        return len(rows)

    def upsert_mentions(self, rows: list[dict[str, Any]]) -> int:
        return len(rows)

    def upsert_related(self, rows: list[dict[str, Any]]) -> int:
        return len(rows)


def test_ingest_summary_chars_uses_full_file_length(tmp_path: Path) -> None:
    """Summary chars should reflect the full source file length."""
    content = "Neo4j\n"
    input_path = tmp_path / "doc.txt"
    input_path.write_text(content, encoding="utf-8")

    summary = ingest_mod.ingest_file(
        MagicMock(),
        "neo4j",
        input_path=input_path,
        doc_id="doc-1",
        title="Doc 1",
        graph_store=_StubGraphStore(),
    )

    assert summary["chars"] == len(content)
    assert summary["replace_mode"] == "atomic"
    assert summary["purged"] == {"chunks": 0, "related_edges": 0, "entities": 0}
    assert summary["written"]["chunks"] == 1
    assert summary["written"]["mentions"] >= 0
