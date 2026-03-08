"""Pluggable extractor registry.

Usage::

    from neo4j_graphrag_kg.extractors import get_extractor

    ext = get_extractor("simple")
    ext = get_extractor("llm", provider="anthropic", model="claude-sonnet-4-20250514")
"""

from __future__ import annotations

from typing import Any

from neo4j_graphrag_kg.extractors.base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from neo4j_graphrag_kg.extractors.simple import SimpleExtractor

__all__ = [
    "BaseExtractor",
    "ExtractedEntity",
    "ExtractedRelationship",
    "ExtractionResult",
    "SimpleExtractor",
    "get_extractor",
    "EXTRACTORS",
]


def _get_llm_class() -> type[BaseExtractor]:
    """Lazily import LLMExtractor to avoid requiring SDK at import time."""
    from neo4j_graphrag_kg.extractors.llm import LLMExtractor

    return LLMExtractor


# Registry maps extractor name → callable that returns the class.
# "simple" is always available; "llm" is lazy-loaded.
EXTRACTORS: dict[str, type[BaseExtractor]] = {
    "simple": SimpleExtractor,
}


def get_extractor(name: str, **kwargs: Any) -> BaseExtractor:
    """Instantiate an extractor by name.

    Parameters
    ----------
    name:
        ``"simple"`` or ``"llm"``.
    **kwargs:
        Forwarded to the extractor constructor (e.g. provider, model,
        api_key, entity_types, relationship_types).

    Raises
    ------
    ValueError
        If *name* is not a registered extractor.
    """
    if name == "llm":
        cls = _get_llm_class()
        return cls(**kwargs)

    if name not in EXTRACTORS:
        available = ", ".join(sorted([*EXTRACTORS.keys(), "llm"]))
        raise ValueError(f"Unknown extractor {name!r}. Available: {available}")

    cls = EXTRACTORS[name]
    return cls(**kwargs)
