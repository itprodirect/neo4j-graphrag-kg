"""Unit tests for the LLM extractor with MOCKED API responses.

Never calls real APIs. Tests JSON parsing, retry logic, error handling,
and entity type constraint pass-through.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from neo4j_graphrag_kg.extractors.llm import (
    LLMExtractor,
    _parse_json_response,
    _safe_float,
)

# ---------------------------------------------------------------------------
# JSON parsing tests
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    def test_plain_json(self) -> None:
        raw = json.dumps({"entities": [], "relationships": []})
        result = _parse_json_response(raw)
        assert result == {"entities": [], "relationships": []}

    def test_markdown_fenced_json(self) -> None:
        raw = (
            '```json\n'
            '{"entities": [{"name": "Neo4j", "type": "Technology"}], '
            '"relationships": []}\n```'
        )
        result = _parse_json_response(raw)
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Neo4j"

    def test_markdown_fenced_no_lang(self) -> None:
        raw = '```\n{"entities": [], "relationships": []}\n```'
        result = _parse_json_response(raw)
        assert result == {"entities": [], "relationships": []}

    def test_json_with_surrounding_text(self) -> None:
        raw = 'Here is the output:\n{"entities": [], "relationships": []}\nDone.'
        result = _parse_json_response(raw)
        assert result == {"entities": [], "relationships": []}

    def test_malformed_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse JSON"):
            _parse_json_response("not json at all")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_json_response("")


class TestSafeFloat:
    def test_normal_float(self) -> None:
        assert _safe_float(0.85) == 0.85

    def test_string_float(self) -> None:
        assert _safe_float("0.7") == 0.7

    def test_clamped_above(self) -> None:
        assert _safe_float(5.0) == 1.0

    def test_clamped_below(self) -> None:
        assert _safe_float(-1.0) == 0.0

    def test_invalid_returns_default(self) -> None:
        assert _safe_float("not-a-number") == 1.0

    def test_none_returns_default(self) -> None:
        assert _safe_float(None) == 1.0


# ---------------------------------------------------------------------------
# LLMExtractor instantiation tests
# ---------------------------------------------------------------------------

class TestLLMExtractorInit:
    def test_missing_api_key_raises(self) -> None:
        with pytest.raises(ValueError, match="LLM_API_KEY is required"):
            LLMExtractor(provider="anthropic", api_key="")

    def test_invalid_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMExtractor(provider="invalid", api_key="test-key")

    def test_anthropic_default_model(self) -> None:
        ext = LLMExtractor(provider="anthropic", api_key="test-key")
        assert ext._model == "claude-sonnet-4-20250514"

    def test_openai_default_model(self) -> None:
        ext = LLMExtractor(provider="openai", api_key="test-key")
        assert ext._model == "gpt-4o"

    def test_custom_model(self) -> None:
        ext = LLMExtractor(provider="anthropic", api_key="k", model="my-model")
        assert ext._model == "my-model"

    def test_entity_types_passed_through(self) -> None:
        types = ["Person", "Org"]
        ext = LLMExtractor(provider="anthropic", api_key="k", entity_types=types)
        assert ext._entity_types == types
        # Verify types appear in the system prompt
        prompt = ext._build_system_prompt()
        assert "Person" in prompt
        assert "Org" in prompt


# ---------------------------------------------------------------------------
# LLMExtractor.extract() with mocked API
# ---------------------------------------------------------------------------

def _make_mock_response(entities: list[dict], relationships: list[dict]) -> str:
    """Build a valid JSON response string."""
    return json.dumps({"entities": entities, "relationships": relationships})


class TestLLMExtractorExtract:
    """Tests with mocked LLM API calls."""

    def _make_extractor(self, response: str) -> LLMExtractor:
        """Create an extractor with a mocked _call_fn."""
        ext = LLMExtractor(provider="anthropic", api_key="test-key-123")
        ext._call_fn = MagicMock(return_value=response)
        return ext

    def test_valid_json_parsed_correctly(self) -> None:
        response = _make_mock_response(
            entities=[
                {"name": "Alice", "type": "Person", "evidence": "Alice is CEO"},
                {"name": "Nexus", "type": "Organization", "evidence": "Nexus Corp"},
            ],
            relationships=[
                {
                    "source": "Alice",
                    "target": "Nexus",
                    "type": "WORKS_FOR",
                    "confidence": 0.95,
                    "evidence": "Alice works at Nexus",
                },
            ],
        )
        ext = self._make_extractor(response)
        result = ext.extract("Alice is the CEO of Nexus Corp.", "c0", "d0")

        assert len(result.entities) == 2
        assert result.entities[0].name == "Alice"
        assert result.entities[0].type == "Person"
        assert result.entities[1].name == "Nexus"

        assert len(result.relationships) == 1
        assert result.relationships[0].source == "Alice"
        assert result.relationships[0].target == "Nexus"
        assert result.relationships[0].type == "WORKS_FOR"
        assert result.relationships[0].confidence == 0.95

    def test_markdown_fenced_response_handled(self) -> None:
        inner = _make_mock_response(
            entities=[{"name": "Bob", "type": "Person", "evidence": "Bob"}],
            relationships=[],
        )
        response = f"```json\n{inner}\n```"
        ext = self._make_extractor(response)
        result = ext.extract("Bob is here.", "c0", "d0")
        assert len(result.entities) == 1
        assert result.entities[0].name == "Bob"

    def test_malformed_json_triggers_retry(self) -> None:
        """First call returns bad JSON, retry returns good JSON."""
        good_response = _make_mock_response(
            entities=[{"name": "X", "type": "Concept", "evidence": "X"}],
            relationships=[],
        )
        ext = LLMExtractor(provider="anthropic", api_key="test-key")
        # First call returns bad JSON, second call returns good JSON
        ext._call_fn = MagicMock(side_effect=["not json {{{", good_response])
        result = ext.extract("text about X", "c0", "d0")
        assert len(result.entities) == 1
        assert ext._call_fn.call_count == 2

    def test_api_failure_retries(self) -> None:
        """API call fails once then succeeds."""
        good_response = _make_mock_response(
            entities=[{"name": "Y", "type": "Concept", "evidence": "Y"}],
            relationships=[],
        )
        ext = LLMExtractor(provider="anthropic", api_key="test-key", max_retries=1)
        ext._call_fn = MagicMock(side_effect=[
            RuntimeError("API error"),
            good_response,
        ])
        result = ext.extract("text about Y", "c0", "d0")
        assert len(result.entities) == 1

    def test_empty_entities_skipped(self) -> None:
        response = _make_mock_response(
            entities=[
                {"name": "", "type": "Person", "evidence": ""},  # empty name
                {"name": "Valid", "type": "Concept", "evidence": "valid"},
            ],
            relationships=[],
        )
        ext = self._make_extractor(response)
        result = ext.extract("text", "c0", "d0")
        assert len(result.entities) == 1
        assert result.entities[0].name == "Valid"

    def test_confidence_clamped(self) -> None:
        response = _make_mock_response(
            entities=[],
            relationships=[
                {"source": "A", "target": "B", "type": "USES",
                 "confidence": 5.0, "evidence": "high"},
            ],
        )
        ext = self._make_extractor(response)
        result = ext.extract("text", "c0", "d0")
        assert result.relationships[0].confidence == 1.0

    def test_returns_empty_on_total_parse_failure(self) -> None:
        """Both LLM calls return unparseable JSON → empty result."""
        ext = LLMExtractor(provider="anthropic", api_key="test-key")
        ext._call_fn = MagicMock(return_value="garbage garbage garbage")
        result = ext.extract("text", "c0", "d0")
        assert result.entities == []
        assert result.relationships == []
