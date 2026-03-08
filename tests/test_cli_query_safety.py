"""Unit tests for kg query read-only safety defaults."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from neo4j_graphrag_kg.cli import app

runner = CliRunner()


def _mock_driver_and_session() -> tuple[MagicMock, MagicMock]:
    driver = MagicMock()
    session_cm = MagicMock()
    session = MagicMock()
    session_cm.__enter__.return_value = session
    session_cm.__exit__.return_value = False
    driver.session.return_value = session_cm
    return driver, session


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
@patch("neo4j_graphrag_kg.cli.validate_cypher_readonly")
def test_query_blocks_write_cypher_by_default(
    mock_validate: MagicMock,
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_close_driver: MagicMock,
) -> None:
    raw_query = "MATCH (n) DELETE n"
    mock_validate.side_effect = ValueError("write clause")
    mock_get_settings.return_value = MagicMock(neo4j_database="neo4j")
    driver, session = _mock_driver_and_session()
    mock_get_driver.return_value = driver

    result = runner.invoke(app, ["query", "--cypher", raw_query])

    assert result.exit_code == 1
    mock_validate.assert_called_once_with(raw_query)
    session.run.assert_not_called()
    mock_close_driver.assert_called_once()


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
@patch("neo4j_graphrag_kg.cli.validate_cypher_readonly")
def test_query_allow_write_bypasses_validation(
    mock_validate: MagicMock,
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_close_driver: MagicMock,
) -> None:
    raw_query = "MATCH (n) DETACH DELETE n RETURN 3 AS deleted"
    mock_get_settings.return_value = MagicMock(neo4j_database="neo4j")
    driver, session = _mock_driver_and_session()
    mock_get_driver.return_value = driver
    session.run.return_value = [{"deleted": 3}]

    result = runner.invoke(app, ["query", "--cypher", raw_query, "--allow-write"])

    assert result.exit_code == 0
    mock_validate.assert_not_called()
    session.run.assert_called_once_with(raw_query)
    mock_close_driver.assert_called_once()


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli.build_service_container")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
def test_check_graph_returns_zero_for_clean_graph(
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_build_container: MagicMock,
    mock_close_driver: MagicMock,
) -> None:
    mock_get_settings.return_value = MagicMock(neo4j_database="neo4j")
    mock_get_driver.return_value = MagicMock()

    graph = MagicMock()
    graph.diagnostics.return_value = {
        "status": "ok",
        "stale_total": 0,
        "checks": {
            "documents_without_chunks": 0,
            "orphan_chunks": 0,
            "related_edges_without_document": 0,
            "orphan_entities": 0,
        },
    }
    mock_build_container.return_value = MagicMock(graph=graph)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert "Graph integrity: ok" in result.output
    assert "orphan_entities=0" in result.output
    mock_close_driver.assert_called_once()


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli.build_service_container")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
def test_check_graph_returns_nonzero_for_stale_artifacts(
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_build_container: MagicMock,
    mock_close_driver: MagicMock,
) -> None:
    mock_get_settings.return_value = MagicMock(neo4j_database="neo4j")
    mock_get_driver.return_value = MagicMock()

    graph = MagicMock()
    graph.diagnostics.return_value = {
        "status": "attention",
        "stale_total": 3,
        "checks": {
            "documents_without_chunks": 1,
            "orphan_chunks": 0,
            "related_edges_without_document": 0,
            "orphan_entities": 2,
        },
    }
    mock_build_container.return_value = MagicMock(graph=graph)

    result = runner.invoke(app, ["check", "--json"])

    assert result.exit_code == 1
    assert '"status": "attention"' in result.output
    assert '"orphan_entities": 2' in result.output
    mock_close_driver.assert_called_once()
