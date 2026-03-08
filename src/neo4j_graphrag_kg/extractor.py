"""Backward-compatibility shim — imports from ``extractors.simple``.

.. deprecated::
    Import from ``neo4j_graphrag_kg.extractors.simple`` instead.
"""

from neo4j_graphrag_kg.extractors.simple import (
    KNOWN_TERMS,
    MIN_FREQUENCY,
    ExtractedEdge,
    ExtractedEntity,
    SimpleExtractor,
    build_edges,
    extract_entities,
    extract_entities_from_chunk,
)

__all__ = [
    "ExtractedEntity",
    "ExtractedEdge",
    "KNOWN_TERMS",
    "MIN_FREQUENCY",
    "SimpleExtractor",
    "build_edges",
    "extract_entities",
    "extract_entities_from_chunk",
]
