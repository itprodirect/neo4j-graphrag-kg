"""Unit tests for staged ingest jobs with durable state and retries."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import neo4j_graphrag_kg.ingest as ingest_mod
from neo4j_graphrag_kg.ingest import IngestJobSpec, IngestPipelineService


class _MemoryJobStore:
    """In-memory job store used to test pipeline logic without Neo4j."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, object]] = {}

    def create_job(
        self,
        spec: IngestJobSpec,
        *,
        max_retries: int,
        extractor_name: str,
    ) -> str:
        job_id = f"job::{spec.doc_id}"
        now = ingest_mod._utc_now_iso()
        self._jobs[job_id] = {
            "id": job_id,
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "completed_at": None,
            "doc_id": spec.doc_id,
            "title": spec.title,
            "source": spec.source,
            "input_path": str(spec.input_path),
            "chunk_size": spec.chunk_size,
            "chunk_overlap": spec.chunk_overlap,
            "extractor_name": extractor_name,
            "status": "queued",
            "stage": "queued",
            "stage_index": 0,
            "attempt": 0,
            "max_retries": max_retries,
            "error": "",
            "state": {},
            "summary": {},
        }
        return job_id

    def get_job(self, job_id: str) -> dict[str, object] | None:
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
        state: dict[str, object],
        error: str,
        started_at: str | None = None,
        completed_at: str | None = None,
        summary: dict[str, object] | None = None,
    ) -> None:
        job = self._jobs[job_id]
        job["status"] = status
        job["stage"] = stage
        job["stage_index"] = stage_index
        job["attempt"] = attempt
        job["error"] = error
        job["updated_at"] = ingest_mod._utc_now_iso()
        if started_at is not None:
            job["started_at"] = started_at
        if completed_at is not None:
            job["completed_at"] = completed_at
        job["state"] = dict(state)
        if summary is not None:
            job["summary"] = dict(summary)


def _write_input(tmp_path: Path, text: str = "Neo4j and Cypher.") -> Path:
    p = tmp_path / "doc.txt"
    p.write_text(text, encoding="utf-8")
    return p


def test_ingest_job_completes_and_persists_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _MemoryJobStore()
    service = IngestPipelineService(MagicMock(), "neo4j", job_store=store)
    monkeypatch.setattr(
        ingest_mod,
        "_stage_graph_write",
        lambda *a, **k: {"written": {"chunks": 1, "entities": 1, "mentions": 1, "edges": 0}},
    )

    spec = IngestJobSpec(
        input_path=_write_input(tmp_path),
        doc_id="doc-1",
        title="Doc 1",
    )
    job_id = service.enqueue_job(spec, max_retries=1, extractor_name="simple")
    summary = service.run_job(job_id)

    assert summary["doc_id"] == "doc-1"
    assert summary["chars"] > 0
    assert summary["chunks"] >= 1
    job = store.get_job(job_id)
    assert job is not None
    assert job["status"] == "completed"
    assert job["stage"] == "completed"
    assert isinstance(job["summary"], dict)
    assert job["summary"]["doc_id"] == "doc-1"


def test_ingest_job_retries_failed_stage_then_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _MemoryJobStore()
    service = IngestPipelineService(MagicMock(), "neo4j", job_store=store)
    monkeypatch.setattr(
        ingest_mod,
        "_stage_graph_write",
        lambda *a, **k: {"written": {"chunks": 1, "entities": 1, "mentions": 1, "edges": 0}},
    )

    calls = {"count": 0}
    original = service._run_extraction_stage

    def _flaky_extract(
        job: dict[str, object], state: dict[str, object], extractor: object
    ) -> dict[str, object]:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient extract failure")
        return original(job, state, extractor)  # type: ignore[arg-type]

    monkeypatch.setattr(service, "_run_extraction_stage", _flaky_extract)

    spec = IngestJobSpec(
        input_path=_write_input(tmp_path, "Neo4j graph platform"),
        doc_id="doc-retry",
        title="Retry Doc",
    )
    job_id = service.enqueue_job(spec, max_retries=1, extractor_name="simple")
    summary = service.run_job(job_id)

    assert summary["doc_id"] == "doc-retry"
    job = store.get_job(job_id)
    assert job is not None
    assert job["status"] == "completed"
    assert job["attempt"] == 2


def test_ingest_job_marks_failed_after_retry_exhaustion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _MemoryJobStore()
    service = IngestPipelineService(MagicMock(), "neo4j", job_store=store)

    def _always_fail(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("extract failed permanently")

    monkeypatch.setattr(service, "_run_extraction_stage", _always_fail)

    spec = IngestJobSpec(
        input_path=_write_input(tmp_path, "failure text"),
        doc_id="doc-fail",
        title="Fail Doc",
    )
    job_id = service.enqueue_job(spec, max_retries=1, extractor_name="simple")

    with pytest.raises(RuntimeError, match="extract failed permanently"):
        service.run_job(job_id)

    job = store.get_job(job_id)
    assert job is not None
    assert job["status"] == "failed"
    assert job["stage"] == "extraction"
    assert job["attempt"] == 2
