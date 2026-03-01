"""Base extractor protocol and shared dataclasses.

All extractors (heuristic, LLM, etc.) implement the ``BaseExtractor`` ABC
so that they can be swapped via the ``--extractor`` CLI flag.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Shared data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractedEntity:
    """An entity found by an extractor."""

    name: str
    type: str
    properties: dict[str, object] | None = field(default=None)


@dataclass(frozen=True)
class ExtractedRelationship:
    """A relationship between two entities found by an extractor."""

    source: str          # entity display-name (slugified at upsert time)
    target: str          # entity display-name
    type: str            # relationship type, e.g. "RELATED_TO", "WORKS_FOR"
    confidence: float = 1.0
    evidence: str = ""


@dataclass
class ExtractionResult:
    """Aggregated output of a single ``extract()`` call."""

    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------

class BaseExtractor(ABC):
    """Interface that every extractor must implement."""

    @abstractmethod
    def extract(
        self,
        text: str,
        chunk_id: str,
        doc_id: str,
    ) -> ExtractionResult:
        """Extract entities and relationships from *text*.

        Parameters
        ----------
        text:
            The chunk text to analyse.
        chunk_id:
            Deterministic chunk identifier (for provenance tracking).
        doc_id:
            Parent document identifier.

        Returns
        -------
        ExtractionResult
        """
        ...
