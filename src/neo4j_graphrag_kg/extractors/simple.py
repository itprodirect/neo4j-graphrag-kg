"""Simple heuristic entity extractor and co-occurrence edge builder.

No LLM required. Extracts capitalized phrases (1-4 tokens) and known
terms, de-duplicates via slugify, applies a frequency threshold, and
builds RELATED_TO edges from co-occurrence within the same chunk.

Implements ``BaseExtractor`` for the pluggable extractor architecture.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from neo4j_graphrag_kg.extractors.base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from neo4j_graphrag_kg.ids import slugify

# ---------------------------------------------------------------------------
# Well-known terms (lowercase) to always extract even if not capitalized.
# ---------------------------------------------------------------------------
KNOWN_TERMS: set[str] = {
    "neo4j", "cypher", "graphrag", "knowledge graph", "vector search",
    "graph database", "node", "relationship", "property graph",
    "large language model", "llm", "embedding", "retrieval augmented generation",
    "rag",
}


# Regex for capitalized phrases: 1-4 Title-Case words (ASCII + unicode letters).
_CAP_PHRASE_RE = re.compile(
    r"\b(?:[A-Z\u00C0-\u024F][\w]*(?:\s+[A-Z\u00C0-\u024F][\w]*){0,3})\b"
)

# Precompiled known-term patterns with word boundaries to avoid substring false positives.
# Terms are matched longest-first so multi-word terms are considered before short acronyms.
_KNOWN_TERMS_ORDERED = tuple(sorted(KNOWN_TERMS, key=len, reverse=True))
_KNOWN_TERM_PATTERNS: dict[str, re.Pattern[str]] = {
    term: re.compile(
        rf"(?<!\w){r'\s+'.join(re.escape(part) for part in term.split())}(?!\w)",
        re.IGNORECASE,
    )
    for term in _KNOWN_TERMS_ORDERED
}

# Minimum occurrences (across all chunks) to keep an entity.
MIN_FREQUENCY = 1


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _normalise_name(name: str) -> str:
    """Collapse whitespace, strip."""
    return re.sub(r"\s+", " ", name).strip()


def _display_name_for_term(term: str) -> str:
    """Render a stable display form for known terms."""
    if term in {"llm", "rag"}:
        return term.upper()
    return term.title()


def extract_entities_from_chunk(text: str) -> list[tuple[str, str]]:
    """Return (slug, display_name) pairs found in *text*.

    Finds capitalized phrases via regex and matches known terms
    (case-insensitive, boundary-aware). Returns de-duplicated list by slug.
    """
    found: dict[str, str] = {}  # slug -> display_name

    # 1. Capitalized phrases
    for match in _CAP_PHRASE_RE.finditer(text):
        name = _normalise_name(match.group())
        if len(name) < 2:
            continue
        slug = slugify(name)
        if slug and slug not in found:
            found[slug] = name

    # 2. Known terms (case-insensitive, boundary-aware scan)
    for term in _KNOWN_TERMS_ORDERED:
        if _KNOWN_TERM_PATTERNS[term].search(text):
            slug = slugify(term)
            if slug and slug not in found:
                found[slug] = _display_name_for_term(term)

    return list(found.items())


def extract_entities(
    chunks: list[tuple[str, str]],
    min_frequency: int = MIN_FREQUENCY,
) -> list[ExtractedEntity]:
    """Extract de-duplicated entities from a list of (chunk_id, text) pairs.

    Parameters
    ----------
    chunks:
        List of (chunk_id, chunk_text).
    min_frequency:
        Minimum number of chunks an entity must appear in.

    Returns
    -------
    list[ExtractedEntity]
    """
    freq: Counter[str] = Counter()
    slug_to_name: dict[str, str] = {}

    for _cid, text in chunks:
        for slug, name in extract_entities_from_chunk(text):
            freq[slug] += 1
            if slug not in slug_to_name:
                slug_to_name[slug] = name

    entities: list[ExtractedEntity] = []
    for slug, count in freq.items():
        if count >= min_frequency:
            entities.append(ExtractedEntity(
                name=slug_to_name[slug],
                type="Term",
            ))
    return sorted(entities, key=lambda e: e.name.lower())


# ---------------------------------------------------------------------------
# Co-occurrence edge builder
# ---------------------------------------------------------------------------

def build_edges(
    chunks: list[tuple[str, str]],
    doc_id: str,
    entity_set: set[str] | None = None,
) -> list[ExtractedRelationship]:
    """Build RELATED_TO edges from entity co-occurrence in each chunk.

    For every pair of entities that appear in the same chunk, create an
    edge. Confidence is normalized co-occurrence count against the max
    pair count across all chunks.

    Parameters
    ----------
    chunks:
        List of (chunk_id, chunk_text).
    doc_id:
        Document ID (stored as edge metadata).
    entity_set:
        Optional allowlist of entity slugs. If provided, only entities
        in this set generate edges.

    Returns
    -------
    list[ExtractedRelationship]
    """
    # Accumulate per-pair counts and evidence
    @dataclass
    class _Acc:
        count: int = 0
        evidence: list[str] = field(default_factory=list)
        chunk_ids: list[str] = field(default_factory=list)
        source_name: str = ""
        target_name: str = ""

    pair_acc: dict[tuple[str, str], _Acc] = {}
    slug_to_name: dict[str, str] = {}

    for cid, text in chunks:
        found = extract_entities_from_chunk(text)
        for slug, name in found:
            if slug not in slug_to_name:
                slug_to_name[slug] = name
        slugs = [s for s, _n in found if entity_set is None or s in entity_set]
        slugs = sorted(set(slugs))

        if len(slugs) < 2:
            continue

        for a, b in combinations(slugs, 2):
            key = (a, b)
            if key not in pair_acc:
                pair_acc[key] = _Acc(
                    source_name=slug_to_name.get(a, a),
                    target_name=slug_to_name.get(b, b),
                )
            acc = pair_acc[key]
            acc.count += 1
            acc.chunk_ids.append(cid)
            # Keep first evidence references only (to limit size)
            if len(acc.evidence) < 3:
                snippet = text[:120].replace("\n", " ")
                acc.evidence.append(f"chunk={cid}: {snippet}...")

    # Normalize confidence: max count across all pairs
    max_count = max((a.count for a in pair_acc.values()), default=1)

    edges: list[ExtractedRelationship] = []
    for (src, tgt), acc in sorted(pair_acc.items()):
        confidence = acc.count / max_count
        edges.append(ExtractedRelationship(
            source=acc.source_name,
            target=acc.target_name,
            type="RELATED_TO",
            confidence=round(confidence, 4),
            evidence="; ".join(acc.evidence[:2]),
        ))

    return edges


# ---------------------------------------------------------------------------
# SimpleExtractor — implements BaseExtractor
# ---------------------------------------------------------------------------

class SimpleExtractor(BaseExtractor):
    """Heuristic extractor that uses regex + known-term matching.

    No external dependencies or API keys required.
    """

    def extract(
        self,
        text: str,
        chunk_id: str,
        doc_id: str,
    ) -> ExtractionResult:
        """Extract entities and co-occurrence relationships from *text*."""
        found_pairs = extract_entities_from_chunk(text)

        entities = [
            ExtractedEntity(name=name, type="Term")
            for _slug, name in found_pairs
        ]

        # Build co-occurrence relationships within this single chunk
        slugs = sorted(set(s for s, _n in found_pairs))
        slug_to_name: dict[str, str] = {s: n for s, n in found_pairs}
        relationships: list[ExtractedRelationship] = []

        if len(slugs) >= 2:
            for a, b in combinations(slugs, 2):
                snippet = text[:120].replace("\n", " ")
                relationships.append(ExtractedRelationship(
                    source=slug_to_name.get(a, a),
                    target=slug_to_name.get(b, b),
                    type="RELATED_TO",
                    confidence=1.0,
                    evidence=f"chunk={chunk_id}: {snippet}...",
                ))

        return ExtractionResult(entities=entities, relationships=relationships)
