"""Unit tests for kg doctor setup diagnostics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from neo4j_graphrag_kg.cli import app

runner = CliRunner()


def _settings(**overrides: object) -> MagicMock:
    settings = MagicMock()
    settings.neo4j_uri = "bolt://localhost:7687"
    settings.neo4j_database = "neo4j"
    settings.neo4j_password = "password"
    settings.extractor_type = "simple"
    settings.llm_provider = "anthropic"
    settings.llm_api_key = ""
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli._module_available")
@patch("neo4j_graphrag_kg.cli._find_local_dotenv")
@patch("neo4j_graphrag_kg.cli.build_service_container")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
def test_doctor_succeeds_for_simple_core_setup(
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_build_container: MagicMock,
    mock_find_dotenv: MagicMock,
    mock_module_available: MagicMock,
    mock_close_driver: MagicMock,
) -> None:
    mock_get_settings.return_value = _settings()
    mock_get_driver.return_value = MagicMock()
    graph = MagicMock()
    graph.verify_connectivity.return_value = None
    mock_build_container.return_value = MagicMock(graph=graph)
    mock_find_dotenv.return_value = None
    mock_module_available.side_effect = lambda name: False

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Doctor: ok" in result.output
    assert "[ok] neo4j_connectivity" in result.output
    assert "[info] ask: kg ask is disabled until LLM_API_KEY is configured." in result.output
    assert "[info] serve: Install -e '.[web]' to enable kg serve." in result.output
    mock_close_driver.assert_called_once()


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli._module_available")
@patch("neo4j_graphrag_kg.cli._find_local_dotenv")
@patch("neo4j_graphrag_kg.cli.build_service_container")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
def test_doctor_fails_when_password_missing(
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_build_container: MagicMock,
    mock_find_dotenv: MagicMock,
    mock_module_available: MagicMock,
    mock_close_driver: MagicMock,
) -> None:
    mock_get_settings.return_value = _settings(neo4j_password="")
    mock_get_driver.return_value = MagicMock()
    mock_build_container.return_value = MagicMock(graph=MagicMock())
    mock_find_dotenv.return_value = Path("C:/repo/.env")
    mock_module_available.side_effect = lambda name: False

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Doctor: attention" in result.output
    assert "NEO4J_PASSWORD is empty." in result.output
    mock_close_driver.assert_called_once()


@patch("neo4j_graphrag_kg.cli.close_driver")
@patch("neo4j_graphrag_kg.cli._module_available")
@patch("neo4j_graphrag_kg.cli._find_local_dotenv")
@patch("neo4j_graphrag_kg.cli.build_service_container")
@patch("neo4j_graphrag_kg.cli.get_driver")
@patch("neo4j_graphrag_kg.cli.get_settings")
def test_doctor_json_fails_for_llm_extractor_missing_provider_package(
    mock_get_settings: MagicMock,
    mock_get_driver: MagicMock,
    mock_build_container: MagicMock,
    mock_find_dotenv: MagicMock,
    mock_module_available: MagicMock,
    mock_close_driver: MagicMock,
) -> None:
    mock_get_settings.return_value = _settings(
        extractor_type="llm",
        llm_provider="anthropic",
        llm_api_key="test-key",
    )
    mock_get_driver.return_value = MagicMock()
    graph = MagicMock()
    graph.verify_connectivity.return_value = None
    mock_build_container.return_value = MagicMock(graph=graph)
    mock_find_dotenv.return_value = Path("C:/repo/.env")
    mock_module_available.side_effect = lambda name: False if name == "anthropic" else True

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 1
    assert '"status": "attention"' in result.output
    assert '"active_extractor"' in result.output
    assert '"ask"' in result.output
    assert '"anthropic"' in result.output
    mock_close_driver.assert_called_once()
