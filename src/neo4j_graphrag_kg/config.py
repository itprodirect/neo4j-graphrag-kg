"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _find_dotenv() -> Path | None:
    """Walk up from cwd to locate a .env file."""
    cur = Path.cwd()
    for parent in [cur, *cur.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None


def _load_env() -> None:
    """Load .env file if present."""
    dotenv_path = _find_dotenv()
    if dotenv_path is not None:
        load_dotenv(dotenv_path)


@dataclass(frozen=True)
class Settings:
    """Immutable settings for Neo4j connection."""

    neo4j_uri: str = field(default="bolt://localhost:7687")
    neo4j_user: str = field(default="neo4j")
    neo4j_password: str = field(default="")
    neo4j_database: str = field(default="neo4j")

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from environment variables (loads .env first)."""
        _load_env()
        return cls(
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        )


def get_settings() -> Settings:
    """Return a Settings instance from environment."""
    return Settings.from_env()
