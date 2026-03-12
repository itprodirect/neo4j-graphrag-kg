"""Typed service protocols for the neo4j-graphrag-kg platform.

These protocols define the contracts between pipeline orchestration
and storage backends.  Implementations satisfy the protocol via
structural subtyping (``typing.Protocol``), so third-party backends
can conform without importing this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# ---- constants re-used by IngestJobSpec and consumers ----

REPLACE_MODE_ATOMIC = "atomic"
REPLACE_MODE_NON_ATOMIC = "non_atomic"


# ---- data contracts ----


@dataclass(frozen=True)
class IngestJobSpec:
    """Input payload for a durable ingestion job."""

    input_path: Path
    doc_id: str
    title: str
    source: str = ""
    chunk_size: int = 1000
    chunk_overlap: int = 150
    replace_mode: str = REPLACE_MODE_ATOMIC


# ---- service protocols ----


@runtime_checkable
class JobStore(Protocol):
    """Durable storage for ingest job state."""

    def create_job(
        self,
        spec: IngestJobSpec,
        *,
        max_retries: int,
        extractor_name: str,
    ) -> str: ...

    def get_job(self, job_id: str) -> dict[str, Any] | None: ...

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
        started_at: str | None = ...,
        completed_at: str | None = ...,
        summary: dict[str, Any] | None = ...,
    ) -> None: ...

    def list_jobs(
        self,
        *,
        status: str | None = ...,
        limit: int = ...,
    ) -> list[dict[str, Any]]: ...


@runtime_checkable
class GraphStore(Protocol):
    """Abstraction over graph write operations."""

    def upsert_document(
        self, *, doc_id: str, title: str, source: str
    ) -> None: ...

    def upsert_chunks(self, rows: list[dict[str, Any]]) -> int: ...

    def upsert_entities(self, rows: list[dict[str, Any]]) -> int: ...

    def upsert_mentions(self, rows: list[dict[str, Any]]) -> int: ...

    def upsert_related(self, rows: list[dict[str, Any]]) -> int: ...

    def purge_document_subgraph(
        self, *, doc_id: str, batch_size: int = ...
    ) -> dict[str, int]: ...

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
        batch_size: int = ...,
    ) -> dict[str, Any]: ...
