"""Unit tests for config module."""

from __future__ import annotations

from neo4j_graphrag_kg.config import Settings


def test_settings_defaults() -> None:
    """Settings should have sensible defaults when no env is set."""
    s = Settings()
    assert s.neo4j_uri == "bolt://localhost:7687"
    assert s.neo4j_user == "neo4j"
    assert s.neo4j_password == ""
    assert s.neo4j_database == "neo4j"


def test_settings_from_env(monkeypatch: object) -> None:
    """Settings.from_env() should pick up environment variables."""
    import os

    monkeypatch.setattr(os, "environ", {  # type: ignore[attr-defined]
        "NEO4J_URI": "bolt://custom:7688",
        "NEO4J_USER": "admin",
        "NEO4J_PASSWORD": "secret",
        "NEO4J_DATABASE": "mydb",
    })
    s = Settings.from_env()
    assert s.neo4j_uri == "bolt://custom:7688"
    assert s.neo4j_user == "admin"
    assert s.neo4j_password == "secret"
    assert s.neo4j_database == "mydb"


def test_settings_frozen() -> None:
    """Settings dataclass should be immutable."""
    s = Settings()
    try:
        s.neo4j_uri = "bolt://other:7687"  # type: ignore[misc]
        assert False, "Should have raised"
    except AttributeError:
        pass
