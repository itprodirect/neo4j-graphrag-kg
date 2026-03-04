"""Integration tests for durable staged ingest jobs.

These tests require a reachable Neo4j instance and are skipped otherwise.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from textwrap import dedent

from neo4j import GraphDatabase
from typer.testing import CliRunner

from neo4j_graphrag_kg.cli import app
from neo4j_graphrag_kg.config import get_settings
from neo4j_graphrag_kg.ingest import IngestJobSpec, IngestPipelineService, _stage_parse_chunk
from tests.conftest import neo4j_available

runner = CliRunner()

_DEMO_TEXT = dedent("""\
    Neo4j is a leading graph database used for knowledge graphs.
    Cypher is the query language for Neo4j.
    GraphRAG combines graph databases with retrieval augmented generation.
""")


def _write_demo(tmp_path: Path) -> Path:
    p = tmp_path / "demo_jobs.txt"
    p.write_text(_DEMO_TEXT, encoding="utf-8")
    return p


def _extract_job_id(output: str) -> str:
    match = re.search(r"Queued ingest job:\s*(\S+)", output)
    assert match is not None, output
    return match.group(1)


def _extract_json_object(output: str) -> dict[str, object]:
    start = output.find("{")
    end = output.rfind("}")
    assert start >= 0 and end >= 0 and end > start, output
    return json.loads(output[start : end + 1])


def _single_value(cypher: str, key: str, **params: object) -> object:
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            record = session.run(cypher, params).single()
            return record[key] if record else None
    finally:
        driver.close()


def _reset_and_init() -> None:
    reset = runner.invoke(app, ["reset", "--confirm"])
    assert reset.exit_code == 0, reset.output
    init = runner.invoke(app, ["init-db"])
    assert init.exit_code == 0, init.output


@neo4j_available
def test_cli_queue_run_and_status_cycle(tmp_path: Path) -> None:
    """Queue -> status -> run -> status should persist completion + summary."""
    _reset_and_init()
    demo = _write_demo(tmp_path)

    doc_id = "jobs-e2e-doc"
    queued = runner.invoke(app, [
        "ingest",
        "--input", str(demo),
        "--doc-id", doc_id,
        "--title", "Jobs E2E",
        "--queue-only",
    ])
    assert queued.exit_code == 0, queued.output
    job_id = _extract_job_id(queued.output)

    status_before = runner.invoke(app, ["ingest-status", "--job-id", job_id])
    assert status_before.exit_code == 0, status_before.output
    payload_before = _extract_json_object(status_before.output)
    assert payload_before["status"] == "queued"
    assert payload_before["stage"] == "queued"

    run = runner.invoke(app, ["ingest-run", "--job-id", job_id])
    assert run.exit_code == 0, run.output
    assert f"Completed job {job_id}" in run.output

    status_after = runner.invoke(app, ["ingest-status", "--job-id", job_id])
    assert status_after.exit_code == 0, status_after.output
    payload_after = _extract_json_object(status_after.output)
    assert payload_after["status"] == "completed"
    assert payload_after["stage"] == "completed"
    assert isinstance(payload_after["summary"], dict)
    assert payload_after["summary"]["doc_id"] == doc_id

    doc_count = _single_value(
        "MATCH (d:Document {id: $doc_id}) RETURN count(d) AS c",
        "c",
        doc_id=doc_id,
    )
    assert doc_count == 1


@neo4j_available
def test_job_resumes_from_persisted_stage_after_restart(tmp_path: Path) -> None:
    """A queued job at stage_index=1 should resume without re-reading input."""
    _reset_and_init()
    settings = get_settings()
    demo = _write_demo(tmp_path)

    driver_1 = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        service_1 = IngestPipelineService(driver_1, settings.neo4j_database)
        spec = IngestJobSpec(
            input_path=demo,
            doc_id="resume-jobs-doc",
            title="Resume Jobs",
        )
        job_id = service_1.enqueue_job(spec, max_retries=0, extractor_name="simple")

        parse_state = _stage_parse_chunk(
            input_path=demo,
            doc_id=spec.doc_id,
            chunk_size=spec.chunk_size,
            chunk_overlap=spec.chunk_overlap,
        )
        service_1.jobs.save_progress(
            job_id=job_id,
            status="queued",
            stage="extraction",
            stage_index=1,
            attempt=0,
            state=parse_state,
            error="",
        )
    finally:
        driver_1.close()

    # Simulate process crash + source file disappearing after parse stage.
    demo.unlink(missing_ok=True)

    driver_2 = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        service_2 = IngestPipelineService(driver_2, settings.neo4j_database)
        summary = service_2.run_job("ingest::resume-jobs-doc")
        assert summary["doc_id"] == "resume-jobs-doc"
        assert summary["chunks"] > 0
        assert summary["entities"] > 0

        final_job = service_2.jobs.get_job("ingest::resume-jobs-doc")
        assert final_job is not None
        assert final_job["status"] == "completed"
        assert final_job["stage"] == "completed"
    finally:
        driver_2.close()


@neo4j_available
def test_enqueue_same_doc_id_reuses_single_job_node(tmp_path: Path) -> None:
    """Queueing same doc-id twice should upsert one durable IngestJob node."""
    _reset_and_init()
    demo = _write_demo(tmp_path)

    first = runner.invoke(app, [
        "ingest",
        "--input", str(demo),
        "--doc-id", "same-job-doc",
        "--title", "First Title",
        "--queue-only",
    ])
    assert first.exit_code == 0, first.output
    job_id_1 = _extract_job_id(first.output)

    second = runner.invoke(app, [
        "ingest",
        "--input", str(demo),
        "--doc-id", "same-job-doc",
        "--title", "Second Title",
        "--queue-only",
    ])
    assert second.exit_code == 0, second.output
    job_id_2 = _extract_job_id(second.output)

    assert job_id_1 == "ingest::same-job-doc"
    assert job_id_2 == job_id_1

    job_count = _single_value(
        "MATCH (j:IngestJob {id: $id}) RETURN count(j) AS c",
        "c",
        id=job_id_1,
    )
    assert job_count == 1

    title = _single_value(
        "MATCH (j:IngestJob {id: $id}) RETURN j.title AS title",
        "title",
        id=job_id_1,
    )
    assert title == "Second Title"
