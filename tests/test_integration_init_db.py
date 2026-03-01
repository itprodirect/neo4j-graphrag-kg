"""Integration test: kg init-db."""

from __future__ import annotations

from typer.testing import CliRunner

from neo4j_graphrag_kg.cli import app
from tests.conftest import neo4j_available

runner = CliRunner()


@neo4j_available
def test_init_db_succeeds() -> None:
    """kg init-db should exit 0 and report schema initialised."""
    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0
    assert "Schema initialised" in result.output


@neo4j_available
def test_init_db_idempotent() -> None:
    """Running init-db twice should succeed (IF NOT EXISTS)."""
    first = runner.invoke(app, ["init-db"])
    second = runner.invoke(app, ["init-db"])
    assert first.exit_code == 0
    assert second.exit_code == 0
