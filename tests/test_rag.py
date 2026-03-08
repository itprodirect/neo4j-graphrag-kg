"""Tests for the RAG pipeline (text2cypher, answer, pipeline).

All tests run without an API key — LLM calls are mocked.
Integration tests that need Neo4j are skipped when it is unreachable.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from neo4j_graphrag_kg.rag.answer import RAGResponse, _format_results, generate_answer
from neo4j_graphrag_kg.rag.pipeline import ask
from neo4j_graphrag_kg.rag.text2cypher import (
    _strip_cypher,
    get_graph_schema,
    text_to_cypher,
)

# ====================================================================
# _strip_cypher — fence / preamble stripping
# ====================================================================


class TestStripCypher:
    """Unit tests for _strip_cypher helper."""

    def test_plain_cypher(self) -> None:
        raw = "MATCH (n:Entity) RETURN n LIMIT 10"
        assert _strip_cypher(raw) == raw

    def test_fenced_cypher(self) -> None:
        raw = "```cypher\nMATCH (n) RETURN n\n```"
        assert _strip_cypher(raw) == "MATCH (n) RETURN n"

    def test_fenced_no_language(self) -> None:
        raw = "```\nMATCH (n) RETURN n LIMIT 5\n```"
        assert _strip_cypher(raw) == "MATCH (n) RETURN n LIMIT 5"

    def test_preamble_before_cypher(self) -> None:
        raw = "Here is the Cypher query:\nMATCH (n) RETURN n"
        assert _strip_cypher(raw) == "MATCH (n) RETURN n"

    def test_with_keyword(self) -> None:
        raw = "WITH n AS x\nRETURN x"
        assert _strip_cypher(raw) == "WITH n AS x\nRETURN x"

    def test_optional_match(self) -> None:
        raw = "OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m"
        assert _strip_cypher(raw) == raw

    def test_whitespace_only(self) -> None:
        raw = "   \n  \n  "
        assert _strip_cypher(raw) == ""

    def test_multiline_fenced(self) -> None:
        raw = "```cypher\nMATCH (n:Entity)\nWHERE n.name = 'Alice'\nRETURN n\n```"
        result = _strip_cypher(raw)
        assert "MATCH" in result
        assert "Alice" in result


# ====================================================================
# _format_results
# ====================================================================


class TestFormatResults:
    """Unit tests for result formatting."""

    def test_empty_results(self) -> None:
        assert _format_results([]) == "(no results)"

    def test_single_row(self) -> None:
        rows = [{"name": "Alice", "age": 30}]
        text = _format_results(rows)
        assert "Row 1" in text
        assert "Alice" in text
        assert "30" in text

    def test_truncation(self) -> None:
        rows = [{"i": i} for i in range(60)]
        text = _format_results(rows, max_rows=50)
        assert "10 more rows truncated" in text

    def test_no_truncation_at_limit(self) -> None:
        rows = [{"i": i} for i in range(50)]
        text = _format_results(rows, max_rows=50)
        assert "truncated" not in text


# ====================================================================
# RAGResponse dataclass
# ====================================================================


class TestRAGResponse:
    """RAGResponse dataclass tests."""

    def test_defaults(self) -> None:
        r = RAGResponse(question="q", cypher="c")
        assert r.results == []
        assert r.answer == ""
        assert r.elapsed_s == 0.0

    def test_full_fields(self) -> None:
        r = RAGResponse(
            question="What?",
            cypher="MATCH (n) RETURN n",
            results=[{"name": "A"}],
            answer="A is the answer",
            elapsed_s=1.23,
        )
        assert r.question == "What?"
        assert len(r.results) == 1
        assert r.elapsed_s == 1.23


# ====================================================================
# text_to_cypher — validation and mocked calls
# ====================================================================


class TestTextToCypher:
    """text_to_cypher with mocked LLM and driver."""

    def _make_mock_driver(self, schema_rows: list[dict] | None = None) -> MagicMock:
        """Create a mock Neo4j driver with schema results."""
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        if schema_rows is None:
            # Default: return some labels so fallback works
            session.run.side_effect = [
                # db.schema.nodeTypeProperties() fails → triggers fallback
                Exception("Procedure not found"),
            ]
            # Re-mock for fallback path — use a fresh session for second attempt

        return driver

    def test_missing_api_key_raises(self) -> None:
        driver = MagicMock()
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            text_to_cypher("test", driver=driver, database="neo4j", api_key="")

    def test_invalid_provider_raises(self) -> None:
        driver = MagicMock()
        with pytest.raises(ValueError, match="Unsupported"):
            text_to_cypher(
                "test",
                driver=driver,
                database="neo4j",
                api_key="key-123",
                provider="gemini",
            )

    @patch("neo4j_graphrag_kg.rag.text2cypher.get_graph_schema")
    def test_anthropic_call(self, mock_schema: MagicMock) -> None:
        mock_schema.return_value = "Node labels: Entity"
        mock_call = MagicMock(return_value="MATCH (n:Entity) RETURN n LIMIT 10")
        driver = MagicMock()

        with patch.dict(
            "neo4j_graphrag_kg.rag.text2cypher._PROVIDERS",
            {"anthropic": mock_call},
        ):
            result = text_to_cypher(
                "What entities are in the graph?",
                driver=driver,
                database="neo4j",
                api_key="test-key",
                provider="anthropic",
            )
        assert "MATCH" in result
        assert "Entity" in result
        mock_call.assert_called_once()

    @patch("neo4j_graphrag_kg.rag.text2cypher.get_graph_schema")
    def test_openai_call(self, mock_schema: MagicMock) -> None:
        mock_schema.return_value = "Node labels: Entity"
        mock_call = MagicMock(return_value="```cypher\nMATCH (n) RETURN n\n```")
        driver = MagicMock()

        with patch.dict(
            "neo4j_graphrag_kg.rag.text2cypher._PROVIDERS",
            {"openai": mock_call},
        ):
            result = text_to_cypher(
                "Show all nodes",
                driver=driver,
                database="neo4j",
                api_key="test-key",
                provider="openai",
            )
        assert result == "MATCH (n) RETURN n"
        mock_call.assert_called_once()

    @patch("neo4j_graphrag_kg.rag.text2cypher.get_graph_schema")
    def test_default_model_anthropic(self, mock_schema: MagicMock) -> None:
        mock_schema.return_value = "Node labels: Entity"
        mock_call = MagicMock(return_value="MATCH (n) RETURN n")
        driver = MagicMock()

        with patch.dict(
            "neo4j_graphrag_kg.rag.text2cypher._PROVIDERS",
            {"anthropic": mock_call},
        ):
            text_to_cypher(
                "test",
                driver=driver,
                database="neo4j",
                api_key="key",
                provider="anthropic",
                model="",
            )
        # Default model should be claude-*
        call_args = mock_call.call_args
        assert "claude" in call_args[0][1].lower()


# ====================================================================
# generate_answer — validation and mocked calls
# ====================================================================


class TestGenerateAnswer:
    """generate_answer with mocked LLM."""

    def test_missing_api_key_raises(self) -> None:
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            generate_answer("q", "c", [], api_key="")

    def test_invalid_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            generate_answer("q", "c", [], api_key="key", provider="gemini")

    def test_generates_answer(self) -> None:
        mock_call = MagicMock(return_value="  Alice is a person.  ")
        with patch.dict(
            "neo4j_graphrag_kg.rag.answer._PROVIDERS",
            {"anthropic": mock_call},
        ):
            answer = generate_answer(
                "Who is Alice?",
                "MATCH (n) RETURN n",
                [{"name": "Alice", "type": "Person"}],
                api_key="test-key",
                provider="anthropic",
            )
        assert answer == "Alice is a person."
        mock_call.assert_called_once()

    def test_empty_results_still_calls_llm(self) -> None:
        mock_call = MagicMock(return_value="No results were found.")
        with patch.dict(
            "neo4j_graphrag_kg.rag.answer._PROVIDERS",
            {"anthropic": mock_call},
        ):
            answer = generate_answer(
                "Who?",
                "MATCH (n) RETURN n",
                [],
                api_key="test-key",
                provider="anthropic",
            )
        assert "No results" in answer


# ====================================================================
# Pipeline — ask() with mocked internals
# ====================================================================


class TestPipelineAsk:
    """ask() orchestrator tests with mocked text2cypher and execute."""

    @patch("neo4j_graphrag_kg.rag.pipeline.generate_answer")
    @patch("neo4j_graphrag_kg.rag.pipeline._execute_cypher")
    @patch("neo4j_graphrag_kg.rag.pipeline.text_to_cypher")
    def test_full_pipeline(
        self,
        mock_t2c: MagicMock,
        mock_exec: MagicMock,
        mock_answer: MagicMock,
    ) -> None:
        mock_t2c.return_value = "MATCH (n:Entity) RETURN n.name"
        mock_exec.return_value = [{"n.name": "Alice"}]
        mock_answer.return_value = "Alice is an entity."
        driver = MagicMock()

        resp = ask(
            "Who is Alice?",
            driver=driver,
            database="neo4j",
            api_key="test-key",
        )
        assert isinstance(resp, RAGResponse)
        assert resp.question == "Who is Alice?"
        assert "MATCH" in resp.cypher
        assert resp.results == [{"n.name": "Alice"}]
        assert resp.answer == "Alice is an entity."
        assert resp.elapsed_s >= 0

    @patch("neo4j_graphrag_kg.rag.pipeline.text_to_cypher")
    def test_cypher_only_mode(self, mock_t2c: MagicMock) -> None:
        mock_t2c.return_value = "MATCH (n) RETURN n"
        driver = MagicMock()

        resp = ask(
            "All nodes?",
            driver=driver,
            database="neo4j",
            api_key="test-key",
            cypher_only=True,
        )
        assert resp.cypher == "MATCH (n) RETURN n LIMIT 100"
        assert resp.results == []
        assert resp.answer == ""

    @patch("neo4j_graphrag_kg.rag.pipeline.generate_answer")
    @patch("neo4j_graphrag_kg.rag.pipeline._execute_cypher")
    @patch("neo4j_graphrag_kg.rag.pipeline.text_to_cypher")
    def test_retry_on_cypher_failure(
        self,
        mock_t2c: MagicMock,
        mock_exec: MagicMock,
        mock_answer: MagicMock,
    ) -> None:
        """If first Cypher execution fails, retry text2cypher with error."""
        mock_t2c.side_effect = [
            "BAD CYPHER",  # first attempt
            "MATCH (n) RETURN n",  # retry
        ]
        mock_exec.side_effect = [
            Exception("SyntaxError"),  # first exec fails
            [{"name": "ok"}],  # retry exec succeeds
        ]
        mock_answer.return_value = "Got it."
        driver = MagicMock()

        resp = ask(
            "test",
            driver=driver,
            database="neo4j",
            api_key="test-key",
        )
        assert resp.answer == "Got it."
        assert mock_t2c.call_count == 2
        assert mock_exec.call_count == 2

    @patch("neo4j_graphrag_kg.rag.pipeline._execute_cypher")
    @patch("neo4j_graphrag_kg.rag.pipeline.text_to_cypher")
    def test_both_attempts_fail(
        self,
        mock_t2c: MagicMock,
        mock_exec: MagicMock,
    ) -> None:
        """Both Cypher attempts fail → error in answer."""
        mock_t2c.side_effect = ["BAD1", "BAD2"]
        mock_exec.side_effect = [
            Exception("Error1"),
            Exception("Error2"),
        ]
        driver = MagicMock()

        resp = ask(
            "test",
            driver=driver,
            database="neo4j",
            api_key="test-key",
        )
        assert "unable to query" in resp.answer.lower()
        assert resp.results == []


# ====================================================================
# Schema introspection — mocked driver
# ====================================================================


class TestSchemaIntrospection:
    """get_graph_schema with mocked Neo4j sessions."""

    def test_fallback_schema(self) -> None:
        """When full schema procedures fail, fallback provides labels."""
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        # First call: full schema fails
        # Second context manager: fallback calls
        call_count = 0

        def run_side_effect(query: str, *args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if "nodeTypeProperties" in query or "relTypeProperties" in query:
                raise Exception("Procedure not found")
            if "db.labels" in query:
                row = MagicMock()
                row.__getitem__ = lambda self, k: "Entity"
                return [row]
            if "db.relationshipTypes" in query:
                row = MagicMock()
                row.__getitem__ = lambda self, k: "RELATED_TO"
                return [row]
            if "db.propertyKeys" in query:
                row = MagicMock()
                row.__getitem__ = lambda self, k: "name"
                return [row]
            return []

        session.run.side_effect = run_side_effect

        schema = get_graph_schema(driver, "neo4j")
        assert "Entity" in schema

    def test_full_schema(self) -> None:
        """When full schema procedures work, returns detailed schema."""
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        def run_side_effect(query: str, *args: Any, **kwargs: Any) -> Any:
            if "nodeTypeProperties" in query:
                row = MagicMock()
                row.__getitem__ = lambda self, k: {
                    "nodeType": ":`Entity`",
                    "properties": ["name", "type"],
                }[k]
                return [row]
            if "relTypeProperties" in query:
                row = MagicMock()
                row.__getitem__ = lambda self, k: {
                    "relType": ":`RELATED_TO`",
                    "properties": ["confidence"],
                }[k]
                return [row]
            return []

        session.run.side_effect = run_side_effect

        schema = get_graph_schema(driver, "neo4j")
        assert "Entity" in schema
        assert "RELATED_TO" in schema
