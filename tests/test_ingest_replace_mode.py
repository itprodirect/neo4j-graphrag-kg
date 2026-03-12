"""Unit tests for replace-mode graph-write behavior."""

from __future__ import annotations

from typing import Any

import neo4j_graphrag_kg.ingest as ingest_mod


class _MockGraphStore:
    """In-memory GraphStore that records calls for assertion."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {
            "atomic": 0,
            "purge": 0,
            "doc": 0,
            "chunks": 0,
            "entities": 0,
            "mentions": 0,
            "related": 0,
        }
        self.purge_return: dict[str, int] = {
            "chunks": 0,
            "related_edges": 0,
            "entities": 0,
        }
        self.atomic_return: dict[str, Any] = {
            "purged": {"chunks": 1, "related_edges": 1, "entities": 0},
            "written": {"chunks": 1, "entities": 1, "mentions": 1, "edges": 1},
        }

    def upsert_document(self, *, doc_id: str, title: str, source: str = "") -> None:
        self.calls["doc"] += 1

    def upsert_chunks(self, rows: list[dict[str, Any]]) -> int:
        self.calls["chunks"] += 1
        return len(rows)

    def upsert_entities(self, rows: list[dict[str, Any]]) -> int:
        self.calls["entities"] += 1
        return len(rows)

    def upsert_mentions(self, rows: list[dict[str, Any]]) -> int:
        self.calls["mentions"] += 1
        return len(rows)

    def upsert_related(self, rows: list[dict[str, Any]]) -> int:
        self.calls["related"] += 1
        return len(rows)

    def purge_document_subgraph(
        self, *, doc_id: str, batch_size: int = 1000
    ) -> dict[str, int]:
        self.calls["purge"] += 1
        return dict(self.purge_return)

    def replace_document_subgraph_atomic(
        self,
        *,
        doc_id: str,
        title: str,
        source: str,
        chunk_rows: list[dict[str, Any]],
        entity_rows: list[dict[str, Any]],
        mention_rows: list[dict[str, Any]],
        relationship_rows: list[dict[str, Any]],
        batch_size: int = 500,
    ) -> dict[str, Any]:
        self.calls["atomic"] += 1
        return dict(self.atomic_return)


def test_stage_graph_write_defaults_to_atomic() -> None:
    store = _MockGraphStore()
    chunk_row = {
        "id": "doc-atomic::chunk::0",
        "document_id": "doc-atomic",
        "idx": 0,
        "text": "x",
    }

    result = ingest_mod._stage_graph_write(
        store,
        doc_id="doc-atomic",
        title="Atomic",
        source="",
        chunk_rows=[chunk_row],
        entity_rows=[{"id": "x", "name": "X", "type": "Term"}],
        mention_rows=[{"chunk_id": "doc-atomic::chunk::0", "entity_id": "x"}],
        relationship_rows=[],
    )

    assert store.calls["atomic"] == 1
    assert result["replace_mode"] == "atomic"
    # Non-atomic path must not have been called.
    assert store.calls["purge"] == 0
    assert store.calls["doc"] == 0


def test_stage_graph_write_non_atomic_mode_uses_legacy_path() -> None:
    store = _MockGraphStore()
    store.purge_return = {"chunks": 2, "related_edges": 3, "entities": 4}

    chunk_row = {
        "id": "doc-legacy::chunk::0",
        "document_id": "doc-legacy",
        "idx": 0,
        "text": "x",
    }

    result = ingest_mod._stage_graph_write(
        store,
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
    # Atomic path must not have been called.
    assert store.calls["atomic"] == 0
    assert store.calls == {
        "atomic": 0,
        "purge": 1,
        "doc": 1,
        "chunks": 1,
        "entities": 1,
        "mentions": 1,
        "related": 1,
    }
