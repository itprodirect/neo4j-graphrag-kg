"""Unit tests for the chunking module."""

from __future__ import annotations

import pytest

from neo4j_graphrag_kg.chunker import Chunk, chunk_text


class TestChunkText:
    def test_empty_string(self) -> None:
        assert chunk_text("") == []

    def test_whitespace_only(self) -> None:
        assert chunk_text("   \n\n  ") == []

    def test_short_text_single_chunk(self) -> None:
        text = "Hello world."
        result = chunk_text(text, chunk_size=100, chunk_overlap=10)
        assert len(result) == 1
        assert result[0].idx == 0
        assert result[0].text == "Hello world."

    def test_overlap_creates_overlapping_chunks(self) -> None:
        text = "A" * 100
        result = chunk_text(text, chunk_size=50, chunk_overlap=10)
        # Step = 50 - 10 = 40.  Starts: 0, 40, 80.
        assert len(result) == 3
        # Verify overlap: end of first chunk overlaps with start of second
        assert result[0].text[-10:] == result[1].text[:10]

    def test_idx_sequential(self) -> None:
        text = "X" * 200
        result = chunk_text(text, chunk_size=50, chunk_overlap=0)
        for i, c in enumerate(result):
            assert c.idx == i

    def test_overlap_must_be_less_than_size(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap must be < chunk_size"):
            chunk_text("hello", chunk_size=10, chunk_overlap=10)

    def test_overlap_larger_than_size_raises(self) -> None:
        with pytest.raises(ValueError):
            chunk_text("hello", chunk_size=10, chunk_overlap=20)

    def test_returns_chunk_dataclass(self) -> None:
        result = chunk_text("some text", chunk_size=100, chunk_overlap=0)
        assert isinstance(result[0], Chunk)
        assert isinstance(result[0].idx, int)
        assert isinstance(result[0].text, str)
