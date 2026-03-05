"""Shared fixtures and markers for the test suite."""

from __future__ import annotations

import pytest
from neo4j import GraphDatabase

from neo4j_graphrag_kg.config import get_settings
from neo4j_graphrag_kg.neo4j_client import close_driver


def _neo4j_reachable() -> bool:
    """Return True if a local Neo4j instance is reachable."""
    settings = get_settings()
    driver = None
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        driver.verify_connectivity()
        return True
    except Exception:
        return False
    finally:
        if driver is not None:
            driver.close()


neo4j_available = pytest.mark.skipif(
    not _neo4j_reachable(),
    reason="Neo4j is not reachable - skipping integration test",
)


@pytest.fixture(autouse=True)
def _close_singleton_driver() -> None:
    """Ensure singleton Neo4j driver does not leak across tests."""
    yield
    close_driver()
