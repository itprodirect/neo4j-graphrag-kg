"""Unit tests for schema statement definitions."""

from __future__ import annotations

from neo4j_graphrag_kg.schema import ALL_STATEMENTS

_RELATED_TO_ID_UNIQUE = (
    "CREATE CONSTRAINT related_to_id_unique IF NOT EXISTS "
    "FOR ()-[r:RELATED_TO]-() REQUIRE r.id IS UNIQUE"
)
_INGEST_JOB_ID_UNIQUE = (
    "CREATE CONSTRAINT ingest_job_id_unique IF NOT EXISTS "
    "FOR (j:IngestJob) REQUIRE j.id IS UNIQUE"
)


def test_all_statements_include_related_to_constraint_name() -> None:
    assert any("related_to_id_unique" in stmt for stmt in ALL_STATEMENTS)


def test_all_statements_include_related_to_constraint_statement() -> None:
    assert _RELATED_TO_ID_UNIQUE in ALL_STATEMENTS


def test_all_statements_include_ingest_job_constraint_statement() -> None:
    assert _INGEST_JOB_ID_UNIQUE in ALL_STATEMENTS


def test_all_statements_include_ingest_job_status_index() -> None:
    assert any("ingest_job_status_idx" in stmt for stmt in ALL_STATEMENTS)
