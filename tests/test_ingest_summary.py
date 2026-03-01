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

    monkeypatch.setattr(ingest_mod, "upsert_document", lambda *a, **k: None)
    monkeypatch.setattr(ingest_mod, "upsert_chunks", lambda *a, **k: 0)
    monkeypatch.setattr(ingest_mod, "upsert_entities", lambda *a, **k: 0)
    monkeypatch.setattr(ingest_mod, "upsert_mentions", lambda *a, **k: 0)
    monkeypatch.setattr(ingest_mod, "upsert_related", lambda *a, **k: 0)

    summary = ingest_mod.ingest_file(
        MagicMock(),
        "neo4j",
        input_path=input_path,
        doc_id="doc-1",
        title="Doc 1",
    )

    assert summary["chars"] == len(content)
