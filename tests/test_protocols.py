"""Protocol conformance tests for typed service contracts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from neo4j_graphrag_kg.ingest import Neo4jIngestJobStore
from neo4j_graphrag_kg.protocols import GraphStore, IngestJobSpec, JobStore
from neo4j_graphrag_kg.upsert import Neo4jGraphStore

# ---------------------------------------------------------------------------
# Minimal in-memory implementations for protocol conformance checks
# ---------------------------------------------------------------------------


class _MemoryJobStore:
    """Minimal in-memory job store used only for protocol checks."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    def create_job(
        self, spec: IngestJobSpec, *, max_retries: int, extractor_name: str
    ) -> str:
        job_id = f"job::{spec.doc_id}"
        self._jobs[job_id] = {"id": job_id, "status": "queued"}
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = self._jobs.get(job_id)
        return deepcopy(job) if job is not None else None

    def save_progress(
        self,
        *,
        job_id: str,
        status: str,
        stage: str,
        stage_index: int,
        attempt: int,
        state: dict[str, Any],
        error: str,
        started_at: str | None = None,
        completed_at: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> None:
        self._jobs[job_id]["status"] = status

    def list_jobs(
        self, *, status: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        return list(self._jobs.values())[:limit]


# ---------------------------------------------------------------------------
# Protocol conformance — runtime isinstance checks
# ---------------------------------------------------------------------------


def test_neo4j_job_store_satisfies_job_store_protocol() -> None:
    assert issubclass(Neo4jIngestJobStore, JobStore)


def test_neo4j_graph_store_satisfies_graph_store_protocol() -> None:
    assert issubclass(Neo4jGraphStore, GraphStore)


def test_memory_job_store_satisfies_job_store_protocol() -> None:
    store = _MemoryJobStore()
    assert isinstance(store, JobStore)


# ---------------------------------------------------------------------------
# Backward compatibility — IngestJobSpec importable from both locations
# ---------------------------------------------------------------------------


def test_ingest_job_spec_importable_from_protocols() -> None:
    from neo4j_graphrag_kg.protocols import IngestJobSpec as Proto

    spec = Proto(input_path=Path("a.txt"), doc_id="d", title="t")
    assert spec.doc_id == "d"


def test_ingest_job_spec_importable_from_ingest() -> None:
    from neo4j_graphrag_kg.ingest import IngestJobSpec as Ingest

    spec = Ingest(input_path=Path("a.txt"), doc_id="d", title="t")
    assert spec.doc_id == "d"


def test_ingest_job_spec_is_same_class() -> None:
    from neo4j_graphrag_kg.ingest import IngestJobSpec as A
    from neo4j_graphrag_kg.protocols import IngestJobSpec as B

    assert A is B
