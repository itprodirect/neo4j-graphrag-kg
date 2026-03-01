"""Fixed-size character chunker with configurable overlap."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """One contiguous text chunk."""

    idx: int
    text: str


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[Chunk]:
    """Split *text* into overlapping chunks of approximately *chunk_size* chars.

    Parameters
    ----------
    text:
        The full document text (UTF-8).
    chunk_size:
        Target number of characters per chunk (default 1000).
    chunk_overlap:
        Number of overlapping characters between consecutive chunks
        (default 150).  Must be < chunk_size.

    Returns
    -------
    list[Chunk]
        Ordered list of Chunk(idx, text) objects.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be < chunk_size")

    text = text.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    step = chunk_size - chunk_overlap
    start = 0
    idx = 0

    while start < len(text):
        end = start + chunk_size
        segment = text[start:end].strip()
        if segment:
            chunks.append(Chunk(idx=idx, text=segment))
            idx += 1
        start += step

    return chunks
