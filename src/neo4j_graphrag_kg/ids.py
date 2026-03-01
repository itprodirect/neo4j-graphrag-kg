"""Deterministic ID generation for entities and chunks.

Rules:
- entity_id = slugify(name): lowercase, trim, collapse whitespace,
  remove punctuation, replace spaces with hyphens.
- chunk_id  = "{doc_id}::chunk::{idx}" (zero-based index).
"""

from __future__ import annotations

import re
import unicodedata

# Characters allowed in a slug (letters, digits, hyphens, spaces kept temporarily).
_SLUG_STRIP_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"[\s]+")


def slugify(text: str) -> str:
    """Convert *text* to a stable, URL-safe slug.

    1. NFKD-normalise and strip combining marks.
    2. Lowercase.
    3. Remove everything except word-chars, whitespace, hyphens.
    4. Collapse runs of whitespace / hyphens into a single hyphen.
    5. Strip leading/trailing hyphens.
    """
    # Normalise unicode → ASCII-safe form
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
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
