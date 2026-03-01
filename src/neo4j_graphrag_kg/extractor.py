"""Simple heuristic entity extractor and co-occurrence edge builder.

No LLM required.  Extracts capitalised phrases (1–4 tokens) and known
terms, de-duplicates via slugify, applies a frequency threshold, and
builds RELATED_TO edges from co-occurrence within the same chunk.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from neo4j_graphrag_kg.ids import entity_id, slugify

# ---------------------------------------------------------------------------
# Well-known terms (lowercase) to always extract even if not capitalised.
# ---------------------------------------------------------------------------
KNOWN_TERMS: set[str] = {
    "neo4j", "cypher", "graphrag", "knowledge graph", "vector search",
    "graph database", "node", "relationship", "property graph",
    "large language model", "llm", "embedding", "retrieval augmented generation",
    "rag",
}

# Regex for capitalised phrases: 1–4 Title-Case words (ASCII + unicode letters).
_CAP_PHRASE_RE = re.compile(
    r"\b(?:[A-Z\u00C0-\u024F][\w]*(?:\s+[A-Z\u00C0-\u024F][\w]*){0,3})\b"
)

# Minimum occurrences (across all chunks) to keep an entity.
MIN_FREQUENCY = 1


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractedEntity:
    """An entity extracted from the text."""

    id: str          # slugified
    name: str        # original display form
    type: str        # e.g. "Term"


@dataclass(frozen=True)
class ExtractedEdge:
    """A co-occurrence edge between two entities in a chunk."""

    source_id: str
    target_id: str
    doc_id: str
    chunk_id: str
    confidence: float
    evidence: str    # short reference back to the chunk


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _normalise_name(name: str) -> str:
    """Collapse whitespace, strip."""
    return re.sub(r"\s+", " ", name).strip()


def extract_entities_from_chunk(text: str) -> list[tuple[str, str]]:
    """Return (slug, display_name) pairs found in *text*.

    Finds capitalised phrases via regex and matches known terms
    (case-insensitive).  Returns de-duplicated list by slug.
    """
    found: dict[str, str] = {}  # slug → display_name

    # 1. Capitalised phrases
    for match in _CAP_PHRASE_RE.finditer(text):
        name = _normalise_name(match.group())
        if len(name) < 2:
            continue
        slug = slugify(name)
        if slug and slug not in found:
            found[slug] = name

    # 2. Known terms (case-insensitive scan)
    text_lower = text.lower()
    for term in KNOWN_TERMS:
        if term in text_lower:
            slug = slugify(term)
            if slug and slug not in found:
                # Use title-case as canonical display form
                found[slug] = term.title()

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
                id=slug,
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
) -> list[ExtractedEdge]:
    """Build RELATED_TO edges from entity co-occurrence in each chunk.

    For every pair of entities that appear in the same chunk, create an
    edge.  Confidence is normalised co-occurrence count (per chunk: each
    co-occurring pair scores 1/C(n,2) where n = entity count in chunk).

    Parameters
    ----------
    chunks:
        List of (chunk_id, chunk_text).
    doc_id:
        Document ID (stored as edge metadata).
    entity_set:
        Optional allowlist of entity slugs.  If provided, only entities
        in this set generate edges.

    Returns
    -------
    list[ExtractedEdge]
    """
    # Accumulate per-pair counts and evidence
    @dataclass
    class _Acc:
        count: int = 0
        evidence: list[str] = field(default_factory=list)
        chunk_ids: list[str] = field(default_factory=list)

    pair_acc: dict[tuple[str, str], _Acc] = {}

    for cid, text in chunks:
        found = extract_entities_from_chunk(text)
        slugs = [s for s, _n in found if entity_set is None or s in entity_set]
        slugs = sorted(set(slugs))

        if len(slugs) < 2:
            continue

        n_pairs = len(slugs) * (len(slugs) - 1) // 2
        pair_score = 1.0 / n_pairs if n_pairs > 0 else 1.0

        for a, b in combinations(slugs, 2):
            key = (a, b)
            if key not in pair_acc:
                pair_acc[key] = _Acc()
            acc = pair_acc[key]
            acc.count += 1
            acc.chunk_ids.append(cid)
            # Keep first evidence reference only (to limit size)
            if len(acc.evidence) < 3:
                snippet = text[:120].replace("\n", " ")
                acc.evidence.append(f"chunk={cid}: {snippet}...")

    # Normalise confidence: max count across all pairs
    max_count = max((a.count for a in pair_acc.values()), default=1)

    edges: list[ExtractedEdge] = []
    for (src, tgt), acc in sorted(pair_acc.items()):
        confidence = acc.count / max_count
        edges.append(ExtractedEdge(
            source_id=src,
            target_id=tgt,
            doc_id=doc_id,
            chunk_id=acc.chunk_ids[0],  # representative chunk
            confidence=round(confidence, 4),
            evidence="; ".join(acc.evidence[:2]),
        ))

    return edges
