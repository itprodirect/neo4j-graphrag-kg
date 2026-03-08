"""Unit tests for staged ingest jobs with durable state and retries."""

from __future__ import annotations

import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any
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
    assert job["summary"]["replace_mode"] == "atomic"
    assert job["summary"]["purged"] == {"chunks": 0, "related_edges": 0}
    assert job["summary"]["written"]["chunks"] == 1


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

def test_run_job_serializes_concurrent_calls_for_same_doc_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _MemoryJobStore()
    service = IngestPipelineService(MagicMock(), "neo4j", job_store=store)

    calls = {"graph": 0}
    call_lock = threading.Lock()

    def _slow_graph_write(*_args: object, **_kwargs: object) -> dict[str, object]:
        with call_lock:
            calls["graph"] += 1
        time.sleep(0.2)
        return {
            "written": {"chunks": 1, "entities": 1, "mentions": 1, "edges": 0}
        }

    monkeypatch.setattr(ingest_mod, "_stage_graph_write", _slow_graph_write)

    spec = IngestJobSpec(
        input_path=_write_input(tmp_path, "Neo4j concurrency test"),
        doc_id="doc-concurrent",
        title="Concurrent Doc",
    )
    job_id = service.enqueue_job(spec, max_retries=0, extractor_name="simple")

    results: list[dict[str, Any]] = []
    errors: list[Exception] = []

    def _runner() -> None:
        try:
            results.append(service.run_job(job_id))
        except Exception as exc:  # pragma: no cover - assertion below checks empty
            errors.append(exc)

    t1 = threading.Thread(target=_runner)
    t2 = threading.Thread(target=_runner)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == []
    assert len(results) == 2
    assert results[0]["doc_id"] == "doc-concurrent"
    assert results[1]["doc_id"] == "doc-concurrent"
    assert calls["graph"] == 1


def test_ingest_job_retries_graph_write_without_reparsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _MemoryJobStore()
    service = IngestPipelineService(MagicMock(), "neo4j", job_store=store)

    counts = {"parse": 0, "extract": 0, "graph": 0}

    original_parse = service._run_parse_stage
    original_extract = service._run_extraction_stage

    def _tracked_parse(job: dict[str, object]) -> dict[str, object]:
        counts["parse"] += 1
        return original_parse(job)

    def _tracked_extract(
        job: dict[str, object],
        state: dict[str, object],
        extractor: object,
    ) -> dict[str, object]:
        counts["extract"] += 1
        return original_extract(job, state, extractor)  # type: ignore[arg-type]

    def _flaky_graph_write(
        _job: dict[str, object],
        _state: dict[str, object],
    ) -> dict[str, object]:
        counts["graph"] += 1
        if counts["graph"] == 1:
            raise RuntimeError("graph write transient failure")
        return {
            "written": {"chunks": 1, "entities": 1, "mentions": 1, "edges": 0}
        }

    monkeypatch.setattr(service, "_run_parse_stage", _tracked_parse)
    monkeypatch.setattr(service, "_run_extraction_stage", _tracked_extract)
    monkeypatch.setattr(service, "_run_graph_write_stage", _flaky_graph_write)

    spec = IngestJobSpec(
        input_path=_write_input(tmp_path, "Neo4j retry test"),
        doc_id="doc-graph-retry",
        title="Retry Graph Write",
    )
    job_id = service.enqueue_job(spec, max_retries=1, extractor_name="simple")

    summary = service.run_job(job_id)

    assert summary["doc_id"] == "doc-graph-retry"
    assert counts == {"parse": 1, "extract": 1, "graph": 2}

    job = store.get_job(job_id)
    assert job is not None
    assert job["status"] == "completed"
    assert job["attempt"] == 2
