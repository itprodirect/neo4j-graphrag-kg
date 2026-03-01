"""Singleton Neo4j driver wrapper with lifecycle management."""

from __future__ import annotations

import atexit

from neo4j import GraphDatabase, Driver

from neo4j_graphrag_kg.config import Settings, get_settings

_driver: Driver | None = None


def get_driver(settings: Settings | None = None) -> Driver:
    """Return the singleton Neo4j driver, creating it on first call."""
    global _driver
    if _driver is not None:
        return _driver

    cfg = settings or get_settings()
    _driver = GraphDatabase.driver(
        cfg.neo4j_uri,
        auth=(cfg.neo4j_user, cfg.neo4j_password),
    )
    atexit.register(close_driver)
    return _driver


def close_driver() -> None:
    """Close the singleton driver if open."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
