"""Integration test: kg ping."""

from __future__ import annotations

from typer.testing import CliRunner

from neo4j_graphrag_kg.cli import app
from tests.conftest import neo4j_available

runner = CliRunner()


@neo4j_available
def test_ping_succeeds() -> None:
    """kg ping should exit 0 when Neo4j is reachable."""
    result = runner.invoke(app, ["ping"])
    assert result.exit_code == 0
    assert "Neo4j is reachable" in result.output
