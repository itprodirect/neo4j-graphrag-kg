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


def _csv_to_list(val: str) -> list[str]:
    """Split a comma-separated string into a trimmed list."""
    return [v.strip() for v in val.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    """Immutable settings for Neo4j connection and LLM extraction."""

    # Neo4j
    neo4j_uri: str = field(default="bolt://localhost:7687")
    neo4j_user: str = field(default="neo4j")
    neo4j_password: str = field(default="")
    neo4j_database: str = field(default="neo4j")

    # Extractor
    extractor_type: str = field(default="simple")

    # LLM
    llm_provider: str = field(default="anthropic")
    llm_model: str = field(default="")
    llm_api_key: str = field(default="")

    # Schema constraints for LLM extraction
    entity_types: list[str] = field(default_factory=lambda: [
        "Person", "Organization", "Location", "Technology", "Concept",
    ])
    relationship_types: list[str] = field(default_factory=lambda: [
        "WORKS_FOR", "LOCATED_IN", "RELATED_TO", "USES", "PART_OF",
    ])

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from environment variables (loads .env first)."""
        _load_env()

        entity_types_str = os.getenv(
            "ENTITY_TYPES",
            "Person,Organization,Location,Technology,Concept",
        )
        relationship_types_str = os.getenv(
            "RELATIONSHIP_TYPES",
            "WORKS_FOR,LOCATED_IN,RELATED_TO,USES,PART_OF",
        )

        return cls(
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
            extractor_type=os.getenv("EXTRACTOR_TYPE", "simple"),
            llm_provider=os.getenv("LLM_PROVIDER", "anthropic"),
            llm_model=os.getenv("LLM_MODEL", ""),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            entity_types=_csv_to_list(entity_types_str),
            relationship_types=_csv_to_list(relationship_types_str),
        )


def get_settings() -> Settings:
    """Return a Settings instance from environment."""
    return Settings.from_env()
