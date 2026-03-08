"""Unit tests for replace-mode graph-write behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import neo4j_graphrag_kg.ingest as ingest_mod


def test_stage_graph_write_defaults_to_atomic(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"atomic": 0}
    chunk_row = {
        "id": "doc-atomic::chunk::0",
        "document_id": "doc-atomic",
        "idx": 0,
        "text": "x",
    }

    def _atomic(*_args: object, **_kwargs: object) -> dict[str, object]:
        calls["atomic"] += 1
        return {
            "purged": {"chunks": 1, "related_edges": 1, "entities": 0},
            "written": {"chunks": 1, "entities": 1, "mentions": 1, "edges": 1},
        }

    monkeypatch.setattr(ingest_mod, "replace_document_subgraph_atomic", _atomic)

    def _should_not_run(*_args: object, **_kwargs: object) -> dict[str, int]:
        raise AssertionError("non-atomic path should not be used in atomic mode")

    monkeypatch.setattr(ingest_mod, "purge_document_subgraph", _should_not_run)

    result = ingest_mod._stage_graph_write(
        MagicMock(),
        "neo4j",
        doc_id="doc-atomic",
        title="Atomic",
        source="",
        chunk_rows=[chunk_row],
        entity_rows=[{"id": "x", "name": "X", "type": "Term"}],
        mention_rows=[{"chunk_id": "doc-atomic::chunk::0", "entity_id": "x"}],
        relationship_rows=[],
    )

    assert calls["atomic"] == 1
    assert result["replace_mode"] == "atomic"


def test_stage_graph_write_non_atomic_mode_uses_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {
        "purge": 0,
        "doc": 0,
        "chunks": 0,
        "entities": 0,
        "mentions": 0,
        "related": 0,
    }
    chunk_row = {
        "id": "doc-legacy::chunk::0",
        "document_id": "doc-legacy",
        "idx": 0,
        "text": "x",
    }

    def _atomic_should_not_run(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("atomic path should not be used in non_atomic mode")

    monkeypatch.setattr(
        ingest_mod, "replace_document_subgraph_atomic", _atomic_should_not_run
    )

    def _purge(*_args: object, **_kwargs: object) -> dict[str, int]:
        calls["purge"] += 1
        return {"chunks": 2, "related_edges": 3, "entities": 4}

    def _bump(key: str) -> None:
        calls[key] += 1

    def _bump_fn(key: str):
        return lambda *_a, **_k: _bump(key)

    monkeypatch.setattr(ingest_mod, "purge_document_subgraph", _purge)
    monkeypatch.setattr(ingest_mod, "upsert_document", _bump_fn("doc"))
    monkeypatch.setattr(ingest_mod, "upsert_chunks", _bump_fn("chunks"))
    monkeypatch.setattr(ingest_mod, "upsert_entities", _bump_fn("entities"))
    monkeypatch.setattr(ingest_mod, "upsert_mentions", _bump_fn("mentions"))
    monkeypatch.setattr(ingest_mod, "upsert_related", _bump_fn("related"))

    result = ingest_mod._stage_graph_write(
        MagicMock(),
        "neo4j",
        doc_id="doc-legacy",
        title="Legacy",
        source="",
        chunk_rows=[chunk_row],
        entity_rows=[{"id": "x", "name": "X", "type": "Term"}],
        mention_rows=[{"chunk_id": "doc-legacy::chunk::0", "entity_id": "x"}],
        relationship_rows=[],
        replace_mode="non_atomic",
    )

    assert result["replace_mode"] == "non_atomic"
    assert result["purged"] == {"chunks": 2, "related_edges": 3, "entities": 4}
    assert calls == {
        "purge": 1,
        "doc": 1,
        "chunks": 1,
        "entities": 1,
        "mentions": 1,
        "related": 1,
    }
