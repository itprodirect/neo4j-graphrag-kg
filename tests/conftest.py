"""Shared fixtures and markers for the test suite."""

from __future__ import annotations

import pytest
from neo4j import GraphDatabase

from neo4j_graphrag_kg.config import get_settings


def _neo4j_reachable() -> bool:
    """Return True if a local Neo4j instance is reachable."""
    settings = get_settings()
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


neo4j_available = pytest.mark.skipif(
    not _neo4j_reachable(),
    reason="Neo4j is not reachable — skipping integration test",
)
