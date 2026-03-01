"""Deterministic ID generation for entities, chunks, and edges.

Rules:
- entity_id = slugify(name): lowercase, trim, collapse whitespace,
  remove punctuation, replace spaces with hyphens.
- chunk_id  = "{doc_id}::chunk::{idx}" (zero-based index).
- edge_id   = "{doc_id}::{chunk_id}::{source_id}::{extractor}::{target_id}".
"""

from __future__ import annotations

import re
import unicodedata

# Characters allowed in a slug (letters, digits, hyphens, spaces kept temporarily).
_SLUG_STRIP_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"[\s]+")
_SYMBOL_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b([a-z0-9]+)\+\+(?=\W|$)"), r"\1-plus-plus"),
    (re.compile(r"(?i)\b([a-z0-9]+)#(?=\W|$)"), r"\1-sharp"),
)


def slugify(text: str) -> str:
    """Convert *text* to a stable, URL-safe slug.

    1. NFKD-normalize and strip combining marks.
    2. Lowercase.
    3. Rewrite symbol-heavy tokens (e.g., C++ -> c-plus-plus, C# -> c-sharp).
    4. Remove everything except word chars, whitespace, hyphens.
    5. Collapse runs of whitespace into a single hyphen.
    6. Strip leading/trailing hyphens.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()

    for pattern, replacement in _SYMBOL_REWRITES:
        text = pattern.sub(replacement, text)

    text = _SLUG_STRIP_RE.sub("", text)
    text = _WHITESPACE_RE.sub("-", text)
    text = text.strip("-")
    return text


def entity_id(name: str) -> str:
    """Deterministic entity ID from its display name."""
    return slugify(name)


def chunk_id(doc_id: str, idx: int) -> str:
    """Deterministic chunk ID from document ID and zero-based index."""
    return f"{doc_id}::chunk::{idx}"


def edge_id(
    doc_id: str,
    chunk_id: str,
    source_id: str,
    extractor: str,
    target_id: str,
    rel_type: str = "",
) -> str:
    """Deterministic relationship ID for RELATED_TO edges.

    When *rel_type* is provided (and non-empty), it is appended so that
    (A)-[WORKS_FOR]->(B) and (A)-[LOCATED_IN]->(B) produce distinct IDs.
    """
    base = f"{doc_id}::{chunk_id}::{source_id}::{extractor}::{target_id}"
    if rel_type:
        return f"{base}::{rel_type}"
    return base
