"""Ingestion pipeline with staged execution and durable job state."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neo4j import Driver

from neo4j_graphrag_kg.chunker import chunk_text
from neo4j_graphrag_kg.extractors.base import BaseExtractor, ExtractionResult
from neo4j_graphrag_kg.extractors.simple import SimpleExtractor
from neo4j_graphrag_kg.ids import chunk_id as make_chunk_id
from neo4j_graphrag_kg.ids import edge_id as make_edge_id
from neo4j_graphrag_kg.ids import slugify
from neo4j_graphrag_kg.protocols import (
    REPLACE_MODE_ATOMIC as _PROTO_REPLACE_MODE_ATOMIC,
)
from neo4j_graphrag_kg.protocols import (
    REPLACE_MODE_NON_ATOMIC as _PROTO_REPLACE_MODE_NON_ATOMIC,
)
from neo4j_graphrag_kg.protocols import (
    GraphStore,
    IngestJobSpec,
    JobStore,
)
from neo4j_graphrag_kg.upsert import Neo4jGraphStore

logger = logging.getLogger(__name__)

# Re-export from protocols for backward compatibility.
REPLACE_MODE_ATOMIC = _PROTO_REPLACE_MODE_ATOMIC
REPLACE_MODE_NON_ATOMIC = _PROTO_REPLACE_MODE_NON_ATOMIC
_REPLACE_MODES = {REPLACE_MODE_ATOMIC, REPLACE_MODE_NON_ATOMIC}

# Explicit re-exports for backward compatibility.
__all__ = [
    "IngestJobSpec",
    "IngestPipelineService",
    "Neo4jIngestJobStore",
    "REPLACE_MODE_ATOMIC",
    "REPLACE_MODE_NON_ATOMIC",
    "ingest_file",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_to_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _json_loads(value: str, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _extractor_label(extractor: BaseExtractor) -> str:
    extractor_name = type(extractor).__name__.lower()
    return "simple" if "simple" in extractor_name else "llm"


def _normalize_replace_mode(mode: str | None) -> str:
    raw = str(mode or REPLACE_MODE_ATOMIC).strip().lower().replace("-", "_")
    if raw not in _REPLACE_MODES:
        raise ValueError(
            f"Unknown replace_mode: {mode!r}. Use '{REPLACE_MODE_ATOMIC}' "
            f"or '{REPLACE_MODE_NON_ATOMIC}'."
        )
    return raw

def _stage_parse_chunk(
    *,
    input_path: Path,
    doc_id: str,
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, Any]:
    logger.info("Reading %s", input_path)
    text = input_path.read_text(encoding="utf-8")
    logger.info("Read %d characters", len(text))

    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    logger.info("Created %d chunks (size=%d, overlap=%d)", len(chunks), chunk_size, chunk_overlap)

    chunk_rows = [
        {
            "id": make_chunk_id(doc_id, c.idx),
            "document_id": doc_id,
            "idx": c.idx,
            "text": c.text,
        }
        for c in chunks
    ]
    return {
        "chars": len(text),
        "chunk_rows": chunk_rows,
    }


def _stage_extract(
    *,
    doc_id: str,
    chunk_rows: list[dict[str, Any]],
    extractor: BaseExtractor,
) -> dict[str, Any]:
    ext_label = _extractor_label(extractor)

    all_entities: dict[str, dict[str, str]] = {}
    all_mentions: list[dict[str, str]] = []
    edge_acc: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in chunk_rows:
        cid_raw = row.get("id")
        text_raw = row.get("text")
        if not isinstance(cid_raw, str) or not isinstance(text_raw, str):
            continue

        result: ExtractionResult = extractor.extract(
            text=text_raw,
            chunk_id=cid_raw,
            doc_id=doc_id,
        )

        for ent in result.entities:
            slug = slugify(ent.name)
            if slug and slug not in all_entities:
                all_entities[slug] = {"name": ent.name, "type": ent.type}
            if slug:
                all_mentions.append({"chunk_id": cid_raw, "entity_id": slug})

        for rel in result.relationships:
            src_slug = slugify(rel.source)
            tgt_slug = slugify(rel.target)
            if not src_slug or not tgt_slug or src_slug == tgt_slug:
                continue
            if src_slug not in all_entities:
                all_entities[src_slug] = {"name": rel.source, "type": "Term"}
            if tgt_slug not in all_entities:
                all_entities[tgt_slug] = {"name": rel.target, "type": "Term"}

            rel_type = rel.type or "RELATED_TO"
            key = (src_slug, tgt_slug, rel_type)

            if key not in edge_acc:
                edge_acc[key] = {
                    "source_id": src_slug,
                    "target_id": tgt_slug,
                    "doc_id": doc_id,
                    "chunk_id": cid_raw,
                    "extractor": ext_label,
                    "confidence": rel.confidence,
                    "evidence": rel.evidence,
                    "type": rel_type,
                    "_count": 1,
                    "_evidence_parts": [rel.evidence] if rel.evidence else [],
                }
            else:
                acc = edge_acc[key]
                acc["_count"] += 1
                if rel.evidence and len(acc["_evidence_parts"]) < 3:
                    acc["_evidence_parts"].append(rel.evidence)

    max_count = max((e["_count"] for e in edge_acc.values()), default=1)
    relationship_rows: list[dict[str, Any]] = []
    for _key, acc in sorted(edge_acc.items()):
        confidence = round(acc["_count"] / max_count, 4)
        evidence = "; ".join(acc["_evidence_parts"][:2])
        relationship_rows.append({
            "id": make_edge_id(
                doc_id,
                acc["chunk_id"],
                acc["source_id"],
                ext_label,
                acc["target_id"],
                rel_type=acc["type"],
            ),
            "source_id": acc["source_id"],
            "target_id": acc["target_id"],
            "doc_id": doc_id,
            "chunk_id": acc["chunk_id"],
            "extractor": ext_label,
            "confidence": confidence,
            "evidence": evidence,
            "type": acc["type"],
        })

    entity_rows = [
        {"id": slug, "name": info["name"], "type": info["type"]}
        for slug, info in all_entities.items()
    ]

    seen_mentions: set[tuple[str, str]] = set()
    deduped_mentions: list[dict[str, str]] = []
    for mention in all_mentions:
        mention_key = (mention["chunk_id"], mention["entity_id"])
        if mention_key not in seen_mentions:
            seen_mentions.add(mention_key)
            deduped_mentions.append(mention)

    logger.info("Extracted %d unique entities via extractor", len(entity_rows))
    logger.info("Found %d relationships via extractor", len(relationship_rows))
    return {
        "entity_rows": entity_rows,
        "mention_rows": deduped_mentions,
        "relationship_rows": relationship_rows,
    }


def _stage_graph_write(
    graph_store: GraphStore,
    *,
    doc_id: str,
    title: str,
    source: str,
    chunk_rows: list[dict[str, Any]],
    entity_rows: list[dict[str, Any]],
    mention_rows: list[dict[str, Any]],
    relationship_rows: list[dict[str, Any]],
    replace_mode: str = REPLACE_MODE_ATOMIC,
) -> dict[str, Any]:
    mode = _normalize_replace_mode(replace_mode)

    if mode == REPLACE_MODE_ATOMIC:
        result = graph_store.replace_document_subgraph_atomic(
            doc_id=doc_id,
            title=title,
            source=source,
            chunk_rows=chunk_rows,
            entity_rows=entity_rows,
            mention_rows=mention_rows,
            relationship_rows=relationship_rows,
        )
        result["replace_mode"] = mode
        return result

    purged = graph_store.purge_document_subgraph(doc_id=doc_id)
    graph_store.upsert_document(doc_id=doc_id, title=title, source=source)
    graph_store.upsert_chunks(chunk_rows)
    graph_store.upsert_entities(entity_rows)
    graph_store.upsert_mentions(mention_rows)
    graph_store.upsert_related(relationship_rows)
    return {
        "replace_mode": mode,
        "purged": purged,
        "written": {
            "chunks": len(chunk_rows),
            "entities": len(entity_rows),
            "mentions": len(mention_rows),
            "edges": len(relationship_rows),
        },
    }

def _build_summary(
    *,
    doc_id: str,
    chars: int,
    chunk_rows: list[dict[str, Any]],
    entity_rows: list[dict[str, Any]],
    mention_rows: list[dict[str, Any]],
    relationship_rows: list[dict[str, Any]],
    elapsed_s: float,
    graph_write_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_result = graph_write_result if isinstance(graph_write_result, dict) else {}
    raw_mode = raw_result.get("replace_mode")
    replace_mode = (
        _normalize_replace_mode(raw_mode)
        if isinstance(raw_mode, str) and raw_mode.strip()
        else REPLACE_MODE_ATOMIC
    )
    raw_purged = raw_result.get("purged")
    purged_source = raw_purged if isinstance(raw_purged, dict) else {}
    raw_written = raw_result.get("written")
    written_source = raw_written if isinstance(raw_written, dict) else {}

    purged = {
        "chunks": int(purged_source.get("chunks", 0) or 0),
        "related_edges": int(purged_source.get("related_edges", 0) or 0),
        "entities": int(purged_source.get("entities", 0) or 0),
    }
    written = {
        "chunks": int(written_source.get("chunks", len(chunk_rows)) or 0),
        "entities": int(written_source.get("entities", len(entity_rows)) or 0),
        "mentions": int(written_source.get("mentions", len(mention_rows)) or 0),
        "edges": int(written_source.get("edges", len(relationship_rows)) or 0),
    }

    return {
        "doc_id": doc_id,
        "chars": chars,
        "chunks": len(chunk_rows),
        "entities": len(entity_rows),
        "mentions": len(mention_rows),
        "edges": len(relationship_rows),
        "replace_mode": replace_mode,
        "purged": purged,
        "written": written,
        "elapsed_s": round(elapsed_s, 2),
    }


_UPSERT_JOB = """\
UNWIND $rows AS row
MERGE (j:IngestJob {id: row.id})
SET j.created_at = row.created_at,
    j.doc_id = row.doc_id,
    j.title = row.title,
    j.source = row.source,
    j.input_path = row.input_path,
    j.chunk_size = row.chunk_size,
    j.chunk_overlap = row.chunk_overlap,
    j.extractor_name = row.extractor_name,
    j.replace_mode = row.replace_mode,
    j.status = row.status,
    j.stage = row.stage,
    j.stage_index = row.stage_index,
    j.attempt = row.attempt,
    j.max_retries = row.max_retries,
    j.error = row.error,
    j.state_json = row.state_json,
    j.summary_json = row.summary_json,
    j.updated_at = row.updated_at,
    j.started_at = row.started_at,
    j.completed_at = row.completed_at
"""


class Neo4jIngestJobStore:
    """Durable job table backed by :IngestJob nodes in Neo4j."""

    def __init__(self, driver: Driver, database: str) -> None:
        self._driver = driver
        self._database = database

    def create_job(
        self,
        spec: IngestJobSpec,
        *,
        max_retries: int,
        extractor_name: str,
    ) -> str:
        now = _utc_now_iso()
        doc_slug = slugify(spec.doc_id) or spec.doc_id
        job_id = f"ingest::{doc_slug}"
        job: dict[str, Any] = {
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
            "replace_mode": _normalize_replace_mode(spec.replace_mode),
            "status": "queued",
            "stage": "queued",
            "stage_index": 0,
            "attempt": 0,
            "max_retries": max(0, max_retries),
            "error": "",
            "state": {},
            "summary": {},
        }
        self._save_job(job)
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._driver.session(database=self._database) as session:
            record = session.run(
                "MATCH (j:IngestJob {id: $id}) RETURN j{.*} AS job",
                id=job_id,
            ).single()
        if not record:
            return None
        raw = dict(record["job"])
        return self._decode_job(raw)

    def list_jobs(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        query = (
            "MATCH (j:IngestJob) "
            "WHERE ($status IS NULL OR j.status = $status) "
            "RETURN j{.*} AS job "
            "ORDER BY j.updated_at DESC "
            "LIMIT $limit"
        )
        with self._driver.session(database=self._database) as session:
            records = list(session.run(query, status=status, limit=safe_limit))
        jobs: list[dict[str, Any]] = []
        for record in records:
            raw = dict(record["job"])
            jobs.append(self._decode_job(raw))
        return jobs

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
        job = self.get_job(job_id)
        if job is None:
            raise ValueError(f"Ingest job not found: {job_id}")

        job["status"] = status
        job["stage"] = stage
        job["stage_index"] = stage_index
        job["attempt"] = attempt
        job["error"] = error
        job["updated_at"] = _utc_now_iso()
        if started_at is not None:
            job["started_at"] = started_at
        if completed_at is not None:
            job["completed_at"] = completed_at
        job["state"] = state
        if summary is not None:
            job["summary"] = summary
        self._save_job(job)

    def _decode_job(self, raw: dict[str, Any]) -> dict[str, Any]:
        job = dict(raw)
        state_json = job.get("state_json")
        summary_json = job.get("summary_json")
        job["state"] = _json_loads(state_json if isinstance(state_json, str) else "", {})
        job["summary"] = _json_loads(summary_json if isinstance(summary_json, str) else "", {})
        job["replace_mode"] = _normalize_replace_mode(
            str(job.get("replace_mode", REPLACE_MODE_ATOMIC))
        )
        return job

    def _save_job(self, job: dict[str, Any]) -> None:
        row = {
            "id": job["id"],
            "created_at": job.get("created_at") or _utc_now_iso(),
            "updated_at": job.get("updated_at") or _utc_now_iso(),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "doc_id": job["doc_id"],
            "title": job["title"],
            "source": job.get("source", ""),
            "input_path": job["input_path"],
            "chunk_size": int(job.get("chunk_size", 1000)),
            "chunk_overlap": int(job.get("chunk_overlap", 150)),
            "extractor_name": str(job.get("extractor_name", "simple")),
            "replace_mode": _normalize_replace_mode(
                str(job.get("replace_mode", REPLACE_MODE_ATOMIC))
            ),
            "status": str(job.get("status", "queued")),
            "stage": str(job.get("stage", "queued")),
            "stage_index": int(job.get("stage_index", 0)),
            "attempt": int(job.get("attempt", 0)),
            "max_retries": int(job.get("max_retries", 0)),
            "error": str(job.get("error", "")),
            "state_json": _json_dumps(job.get("state", {})),
            "summary_json": _json_dumps(job.get("summary", {})),
        }

        def _write(tx: Any, rows: list[dict[str, Any]]) -> None:
            tx.run(_UPSERT_JOB, rows=rows).consume()

        with self._driver.session(database=self._database) as session:
            session.execute_write(_write, [row])


class IngestPipelineService:
    """Asynchronous staged ingestion with durable Neo4j job state."""

    _STAGES: tuple[str, ...] = (
        "parse_chunk",
        "extraction",
        "graph_write",
        "post_processing",
    )

    def __init__(
        self,
        driver: Driver,
        database: str,
        *,
        job_store: JobStore | None = None,
        graph_store: GraphStore | None = None,
    ) -> None:
        self._driver = driver
        self._database = database
        self._job_store: JobStore = job_store or Neo4jIngestJobStore(driver, database)
        self._graph_store: GraphStore = graph_store or Neo4jGraphStore(driver, database)
        self._doc_run_locks: dict[str, threading.Lock] = {}
        self._doc_run_locks_guard = threading.Lock()

    @property
    def jobs(self) -> JobStore:
        return self._job_store

    def _lock_for_doc(self, doc_id: str) -> threading.Lock:
        key = doc_id or "__missing_doc_id__"
        with self._doc_run_locks_guard:
            existing = self._doc_run_locks.get(key)
            if existing is not None:
                return existing
            created = threading.Lock()
            self._doc_run_locks[key] = created
            return created

    def enqueue_job(
        self,
        spec: IngestJobSpec,
        *,
        max_retries: int = 2,
        extractor_name: str = "simple",
    ) -> str:
        return self._job_store.create_job(
            spec,
            max_retries=max_retries,
            extractor_name=extractor_name,
        )

    def run_job(
        self,
        job_id: str,
        *,
        extractor: BaseExtractor | None = None,
    ) -> dict[str, Any]:
        job = self._job_store.get_job(job_id)
        if job is None:
            raise ValueError(f"Ingest job not found: {job_id}")

        lock = self._lock_for_doc(str(job.get("doc_id") or job_id))
        with lock:
            return asyncio.run(self.run_job_async(job_id, extractor=extractor))

    async def run_job_async(
        self,
        job_id: str,
        *,
        extractor: BaseExtractor | None = None,
    ) -> dict[str, Any]:
        active_extractor = extractor or SimpleExtractor()

        while True:
            job = self._job_store.get_job(job_id)
            if job is None:
                raise ValueError(f"Ingest job not found: {job_id}")
            if job.get("status") == "completed":
                summary = job.get("summary")
                if isinstance(summary, dict):
                    return summary
                raise RuntimeError(f"Ingest job {job_id} has invalid summary payload")
            if job.get("status") == "failed":
                raise RuntimeError(str(job.get("error", "Ingest job failed")))

            max_retries = int(job.get("max_retries", 0))
            attempt = int(job.get("attempt", 0)) + 1
            state = dict(job.get("state", {}))
            stage_index = int(job.get("stage_index", 0))
            if stage_index < 0:
                stage_index = 0
            if stage_index > len(self._STAGES):
                stage_index = len(self._STAGES)
            current_stage = self._STAGES[min(stage_index, len(self._STAGES) - 1)]
            started_at = str(job.get("started_at") or _utc_now_iso())

            self._job_store.save_progress(
                job_id=job_id,
                status="running",
                stage=current_stage,
                stage_index=stage_index,
                attempt=attempt,
                state=state,
                error="",
                started_at=started_at,
            )

            failing_stage_index = stage_index
            try:
                for idx in range(stage_index, len(self._STAGES)):
                    stage = self._STAGES[idx]
                    failing_stage_index = idx
                    self._job_store.save_progress(
                        job_id=job_id,
                        status="running",
                        stage=stage,
                        stage_index=idx,
                        attempt=attempt,
                        state=state,
                        error="",
                    )
                    updates = await self._run_stage_async(
                        stage=stage,
                        job=job,
                        state=state,
                        extractor=active_extractor,
                    )
                    state.update(updates)
                    self._job_store.save_progress(
                        job_id=job_id,
                        status="running",
                        stage=stage,
                        stage_index=idx + 1,
                        attempt=attempt,
                        state=state,
                        error="",
                    )

                summary_raw = state.get("summary")
                if not isinstance(summary_raw, dict):
                    raise RuntimeError("Post-processing stage did not produce a summary")

                self._job_store.save_progress(
                    job_id=job_id,
                    status="completed",
                    stage="completed",
                    stage_index=len(self._STAGES),
                    attempt=attempt,
                    state=state,
                    error="",
                    completed_at=_utc_now_iso(),
                    summary=summary_raw,
                )
                return summary_raw
            except Exception as exc:
                retryable = attempt <= max_retries
                next_status = "queued" if retryable else "failed"
                next_stage = (
                    self._STAGES[failing_stage_index]
                    if failing_stage_index < len(self._STAGES)
                    else self._STAGES[-1]
                )
                self._job_store.save_progress(
                    job_id=job_id,
                    status=next_status,
                    stage=next_stage,
                    stage_index=failing_stage_index,
                    attempt=attempt,
                    state=state,
                    error=str(exc),
                )
                if retryable:
                    logger.warning(
                        "Ingest job %s failed at %s (attempt %d/%d), retrying",
                        job_id,
                        next_stage,
                        attempt,
                        max_retries + 1,
                    )
                    continue
                logger.exception(
                    "Ingest job %s failed after %d attempts", job_id, attempt
                )
                raise

    async def _run_stage_async(
        self,
        *,
        stage: str,
        job: dict[str, Any],
        state: dict[str, Any],
        extractor: BaseExtractor,
    ) -> dict[str, Any]:
        if stage == "parse_chunk":
            return await asyncio.to_thread(self._run_parse_stage, job)
        if stage == "extraction":
            return await asyncio.to_thread(self._run_extraction_stage, job, state, extractor)
        if stage == "graph_write":
            return await asyncio.to_thread(self._run_graph_write_stage, job, state)
        if stage == "post_processing":
            return await asyncio.to_thread(self._run_post_processing_stage, job, state)
        raise ValueError(f"Unknown stage: {stage}")

    def _run_parse_stage(self, job: dict[str, Any]) -> dict[str, Any]:
        return _stage_parse_chunk(
            input_path=Path(str(job["input_path"])),
            doc_id=str(job["doc_id"]),
            chunk_size=int(job["chunk_size"]),
            chunk_overlap=int(job["chunk_overlap"]),
        )

    def _run_extraction_stage(
        self,
        job: dict[str, Any],
        state: dict[str, Any],
        extractor: BaseExtractor,
    ) -> dict[str, Any]:
        chunk_rows_raw = state.get("chunk_rows")
        if not isinstance(chunk_rows_raw, list):
            raise RuntimeError("Extraction stage requires chunk_rows from parse_chunk stage")
        chunk_rows = [row for row in chunk_rows_raw if isinstance(row, dict)]
        return _stage_extract(
            doc_id=str(job["doc_id"]),
            chunk_rows=chunk_rows,
            extractor=extractor,
        )

    def _run_graph_write_stage(
        self,
        job: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        chunk_rows = [row for row in state.get("chunk_rows", []) if isinstance(row, dict)]
        entity_rows = [row for row in state.get("entity_rows", []) if isinstance(row, dict)]
        mention_rows = [row for row in state.get("mention_rows", []) if isinstance(row, dict)]
        relationship_rows = [
            row for row in state.get("relationship_rows", []) if isinstance(row, dict)
        ]
        return _stage_graph_write(
            self._graph_store,
            doc_id=str(job["doc_id"]),
            title=str(job["title"]),
            source=str(job.get("source", "")),
            chunk_rows=chunk_rows,
            entity_rows=entity_rows,
            mention_rows=mention_rows,
            relationship_rows=relationship_rows,
            replace_mode=str(job.get("replace_mode", REPLACE_MODE_ATOMIC)),
        )
    def _run_post_processing_stage(
        self,
        job: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        created_dt = _parse_iso_to_utc(str(job.get("created_at")))
        if created_dt is None:
            elapsed = 0.0
        else:
            elapsed = max(0.0, (datetime.now(timezone.utc) - created_dt).total_seconds())

        chunk_rows = [row for row in state.get("chunk_rows", []) if isinstance(row, dict)]
        entity_rows = [row for row in state.get("entity_rows", []) if isinstance(row, dict)]
        mention_rows = [row for row in state.get("mention_rows", []) if isinstance(row, dict)]
        relationship_rows = [
            row for row in state.get("relationship_rows", []) if isinstance(row, dict)
        ]

        chars_raw = state.get("chars", 0)
        chars = chars_raw if isinstance(chars_raw, int) else 0

        summary = _build_summary(
            doc_id=str(job["doc_id"]),
            chars=chars,
            chunk_rows=chunk_rows,
            entity_rows=entity_rows,
            mention_rows=mention_rows,
            relationship_rows=relationship_rows,
            elapsed_s=elapsed,
            graph_write_result={
                "replace_mode": state.get("replace_mode"),
                "purged": state.get("purged"),
                "written": state.get("written"),
            },
        )
        return {"summary": summary}


def ingest_file(
    driver: Driver,
    database: str,
    *,
    input_path: Path,
    doc_id: str,
    title: str,
    source: str = "",
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    extractor: BaseExtractor | None = None,
    replace_mode: str = REPLACE_MODE_ATOMIC,
    graph_store: GraphStore | None = None,
) -> dict[str, Any]:
    """Run synchronous ingest for one file (compatibility wrapper)."""
    active_extractor = extractor or SimpleExtractor()
    active_store = graph_store or Neo4jGraphStore(driver, database)
    t0 = time.perf_counter()

    parse_state = _stage_parse_chunk(
        input_path=input_path,
        doc_id=doc_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    parse_rows_raw = parse_state["chunk_rows"]
    if not isinstance(parse_rows_raw, list):
        raise RuntimeError("parse_chunk stage did not produce chunk_rows")
    parse_rows = [row for row in parse_rows_raw if isinstance(row, dict)]

    extract_state = _stage_extract(
        doc_id=doc_id,
        chunk_rows=parse_rows,
        extractor=active_extractor,
    )
    entity_rows = [row for row in extract_state["entity_rows"] if isinstance(row, dict)]
    mention_rows = [row for row in extract_state["mention_rows"] if isinstance(row, dict)]
    relationship_rows = [
        row for row in extract_state["relationship_rows"] if isinstance(row, dict)
    ]

    graph_write_result = _stage_graph_write(
        active_store,
        doc_id=doc_id,
        title=title,
        source=source,
        chunk_rows=parse_rows,
        entity_rows=entity_rows,
        mention_rows=mention_rows,
        relationship_rows=relationship_rows,
        replace_mode=replace_mode,
    )

    chars_raw = parse_state.get("chars", 0)
    chars = chars_raw if isinstance(chars_raw, int) else 0
    summary = _build_summary(
        doc_id=doc_id,
        chars=chars,
        chunk_rows=parse_rows,
        entity_rows=entity_rows,
        mention_rows=mention_rows,
        relationship_rows=relationship_rows,
        elapsed_s=time.perf_counter() - t0,
        graph_write_result=graph_write_result,
    )
    logger.info("Ingestion complete: %s", summary)
    return summary
