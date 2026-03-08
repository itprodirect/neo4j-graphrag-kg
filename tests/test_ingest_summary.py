"""Unit tests for ingestion summary fields."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from neo4j_graphrag_kg import ingest as ingest_mod


def test_ingest_summary_chars_uses_full_file_length(
    tmp_path: Path, monkeypatch
) -> None:
    """Summary chars should reflect the full source file length."""
    content = "Neo4j\n"
    input_path = tmp_path / "doc.txt"
    input_path.write_text(content, encoding="utf-8")

    monkeypatch.setattr(
        ingest_mod,
        "replace_document_subgraph_atomic",
        lambda *a, **k: {
            "replace_mode": "atomic",
            "purged": {"chunks": 0, "related_edges": 0, "entities": 0},
            "written": {"chunks": 1, "entities": 1, "mentions": 1, "edges": 0},
        },
    )

    summary = ingest_mod.ingest_file(
        MagicMock(),
        "neo4j",
        input_path=input_path,
        doc_id="doc-1",
        title="Doc 1",
    )

    assert summary["chars"] == len(content)
    assert summary["replace_mode"] == "atomic"
    assert summary["purged"] == {"chunks": 0, "related_edges": 0, "entities": 0}
    assert summary["written"]["chunks"] == 1
    assert summary["written"]["mentions"] >= 0
