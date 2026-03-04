"""Unit tests for durable ingest CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from neo4j_graphrag_kg.cli import app

runner = CliRunner()


def _mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.extractor_type = "simple"
    settings.llm_provider = "anthropic"
    settings.llm_model = ""
    settings.llm_api_key = ""
    settings.entity_types = ["Person"]
    settings.relationship_types = ["RELATED_TO"]
    settings.neo4j_database = "neo4j"
    return settings


def _write_input(tmp_path: Path) -> Path:
    p = tmp_path / "doc.txt"
    p.write_text("Neo4j graph test", encoding="utf-8")
    return p


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli._build_extractor")
@patch("neo4j_graphrag_kg.cli.build_service_container")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
def test_ingest_queue_only_creates_job_without_running(
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_build_container: MagicMock,
    mock_build_extractor: MagicMock,
    mock_close_driver: MagicMock,
    tmp_path: Path,
) -> None:
    mock_get_settings.return_value = _mock_settings()
    mock_get_driver.return_value = MagicMock()
    mock_build_extractor.return_value = ("simple", MagicMock())

    ingest_service = MagicMock()
    ingest_service.enqueue_job.return_value = "ingest::doc-1"
    container = MagicMock(ingest=ingest_service)
    mock_build_container.return_value = container

    result = runner.invoke(app, [
        "ingest",
        "--input",
        str(_write_input(tmp_path)),
        "--doc-id",
        "doc-1",
        "--title",
        "Doc 1",
        "--queue-only",
    ])

    assert result.exit_code == 0
    assert "Queued ingest job: ingest::doc-1" in result.output
    ingest_service.run_job.assert_not_called()
    mock_close_driver.assert_called_once()


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli.build_service_container")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
def test_ingest_status_returns_error_for_unknown_job(
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_build_container: MagicMock,
    mock_close_driver: MagicMock,
) -> None:
    mock_get_settings.return_value = _mock_settings()
    mock_get_driver.return_value = MagicMock()

    jobs = MagicMock()
    jobs.get_job.return_value = None
    ingest_service = MagicMock(jobs=jobs)
    mock_build_container.return_value = MagicMock(ingest=ingest_service)

    result = runner.invoke(app, ["ingest-status", "--job-id", "missing-job"])

    assert result.exit_code == 1
    assert "Job not found: missing-job" in result.output
    mock_close_driver.assert_called_once()


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli._build_extractor")
@patch("neo4j_graphrag_kg.cli.build_service_container")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
def test_ingest_run_processes_existing_job(
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_build_container: MagicMock,
    mock_build_extractor: MagicMock,
    mock_close_driver: MagicMock,
) -> None:
    mock_get_settings.return_value = _mock_settings()
    mock_get_driver.return_value = MagicMock()
    mock_build_extractor.return_value = ("simple", MagicMock())

    jobs = MagicMock()
    jobs.get_job.return_value = {"id": "ingest::doc-2", "extractor_name": "simple"}
    ingest_service = MagicMock(jobs=jobs)
    ingest_service.run_job.return_value = {
        "chunks": 2,
        "entities": 3,
        "edges": 1,
        "elapsed_s": 0.42,
    }
    mock_build_container.return_value = MagicMock(ingest=ingest_service)

    result = runner.invoke(app, ["ingest-run", "--job-id", "ingest::doc-2"])

    assert result.exit_code == 0
    assert "Completed job ingest::doc-2: 2 chunks, 3 entities, 1 edges in 0.42s" in result.output
    ingest_service.run_job.assert_called_once()
    mock_close_driver.assert_called_once()
