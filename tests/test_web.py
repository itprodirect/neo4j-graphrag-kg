"""Tests for the FastAPI web server (graph API + RAG endpoint).

Unit tests mock the Neo4j driver and LLM calls.
Integration tests are skipped when Neo4j is not reachable.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from neo4j_graphrag_kg.web.app import app

client = TestClient(app)


# ====================================================================
# Helpers â€” mock driver / settings
# ====================================================================


def _mock_settings(**overrides: Any) -> MagicMock:
    """Return a mock Settings with sensible defaults."""
    s = MagicMock()
    s.neo4j_uri = "bolt://localhost:7687"
    s.neo4j_user = "neo4j"
    s.neo4j_password = "password"
    s.neo4j_database = "neo4j"
    s.llm_provider = "anthropic"
    s.llm_model = ""
    s.llm_api_key = ""
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


class _FakeNode:
    """Minimal mock of a Neo4j Node (only attributes the app checks)."""

    def __init__(self, eid: str, labels: set[str], props: dict[str, Any]) -> None:
        self.element_id = eid
        self.labels = frozenset(labels)
        self._props = props

    def items(self) -> list[tuple[str, Any]]:
        return list(self._props.items())

    def __iter__(self) -> Any:
        return iter(self._props.items())

    def __getitem__(self, key: str) -> Any:
        return self._props[key]


class _FakeRel:
    """Minimal mock of a Neo4j Relationship (only attributes the app checks)."""

    def __init__(
        self, rel_type: str, start: _FakeNode, end: _FakeNode, props: dict[str, Any]
    ) -> None:
        self.type = rel_type
        self.start_node = start
        self.end_node = end
        self._props = props

    def items(self) -> list[tuple[str, Any]]:
        return list(self._props.items())

    def __iter__(self) -> Any:
        return iter(self._props.items())


def _mock_driver_with_graph() -> MagicMock:
    """Return a mock driver that returns a simple graph."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)

    node1 = _FakeNode("4:abc:0", {"Entity"}, {"name": "Alice", "type": "Person"})
    node2 = _FakeNode("4:abc:1", {"Entity"}, {"name": "Nexus", "type": "Organization"})
    rel = _FakeRel("WORKS_FOR", node1, node2, {"confidence": 0.95})

    # Mock record: values() returns [node1, rel, node2]
    record = MagicMock()
    record.values.return_value = [node1, rel, node2]

    session.run.return_value = [record]
    return driver


# ====================================================================
# GET / â€” Static HTML page
# ====================================================================


class TestIndexPage:
    """Tests for the root endpoint serving the HTML page."""

    def test_index_returns_html(self) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_index_contains_d3(self) -> None:
        resp = client.get("/")
        assert "d3" in resp.text.lower()


# ====================================================================
# GET /api/status â€” Neo4j status
# ====================================================================


class TestStatusEndpoint:
    """Tests for the status endpoint."""

    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_status_returns_json(
        self, mock_settings: MagicMock, mock_get_driver: MagicMock
    ) -> None:
        settings = _mock_settings()
        mock_settings.return_value = settings

        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        # dbms.components() result
        ver_record = MagicMock()
        ver_record.__getitem__ = lambda self, k: {
            "name": "Neo4j", "versions": ["5.0.0"]
        }[k]

        # Count result
        count_record = MagicMock()
        count_record.__getitem__ = lambda self, k: {"nodes": 10, "rels": 5}[k]

        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=ver_record)),
            MagicMock(single=MagicMock(return_value=count_record)),
        ]
        mock_get_driver.return_value = driver

        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "nodes" in data
        assert "relationships" in data
        assert data["nodes"] == 10

    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_status_error_returns_500(
        self, mock_settings: MagicMock, mock_get_driver: MagicMock
    ) -> None:
        settings = _mock_settings()
        mock_settings.return_value = settings

        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        session.run.side_effect = Exception("Connection refused")
        mock_get_driver.return_value = driver

        resp = client.get("/api/status")
        assert resp.status_code == 500


# ====================================================================
# GET /api/graph â€” Full graph
# ====================================================================


class TestGraphEndpoint:
    """Tests for the full graph endpoint."""

    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_graph_returns_nodes_and_edges(
        self, mock_settings: MagicMock, mock_get_driver: MagicMock
    ) -> None:
        settings = _mock_settings()
        mock_settings.return_value = settings
        mock_get_driver.return_value = _mock_driver_with_graph()

        resp = client.get("/api/graph?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) >= 1
        assert len(data["edges"]) >= 1

    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_graph_limit_validation(
        self, mock_settings: MagicMock, mock_get_driver: MagicMock
    ) -> None:
        settings = _mock_settings()
        mock_settings.return_value = settings

        # limit < 1 should fail validation
        resp = client.get("/api/graph?limit=0")
        assert resp.status_code == 422

    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_graph_error_returns_500(
        self, mock_settings: MagicMock, mock_get_driver: MagicMock
    ) -> None:
        settings = _mock_settings()
        mock_settings.return_value = settings

        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        session.run.side_effect = Exception("Neo4j error")
        mock_get_driver.return_value = driver

        resp = client.get("/api/graph")
        assert resp.status_code == 500


# ====================================================================
# GET /api/graph/entity/{name}
# ====================================================================


class TestGraphEntityEndpoint:
    """Tests for the entity subgraph endpoint."""

    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_entity_endpoint_returns_data(
        self, mock_settings: MagicMock, mock_get_driver: MagicMock
    ) -> None:
        settings = _mock_settings()
        mock_settings.return_value = settings
        mock_get_driver.return_value = _mock_driver_with_graph()

        resp = client.get("/api/graph/entity/Alice")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data


# ====================================================================
# GET /api/graph/document/{doc_id}
# ====================================================================


class TestGraphDocumentEndpoint:
    """Tests for the document subgraph endpoint."""

    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_document_endpoint_returns_data(
        self, mock_settings: MagicMock, mock_get_driver: MagicMock
    ) -> None:
        settings = _mock_settings()
        mock_settings.return_value = settings

        # Empty graph is fine
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        session.run.return_value = []  # no results
        mock_get_driver.return_value = driver

        resp = client.get("/api/graph/document/test-doc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []


# ====================================================================
# POST /api/ask â€” RAG endpoint
# ====================================================================


class TestAskEndpoint:
    """Tests for the RAG ask endpoint."""

    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_ask_no_api_key_returns_400(self, mock_settings: MagicMock) -> None:
        settings = _mock_settings(llm_api_key="")
        mock_settings.return_value = settings

        resp = client.post("/api/ask", json={"question": "Who is Alice?"})
        assert resp.status_code == 400
        assert "LLM_API_KEY" in resp.json()["detail"]

    @patch("neo4j_graphrag_kg.rag.pipeline.text_to_cypher")
    @patch("neo4j_graphrag_kg.rag.pipeline._execute_cypher")
    @patch("neo4j_graphrag_kg.rag.pipeline.generate_answer")
    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_ask_with_mocked_pipeline(
        self,
        mock_settings: MagicMock,
        mock_get_driver: MagicMock,
        mock_answer: MagicMock,
        mock_exec: MagicMock,
        mock_t2c: MagicMock,
    ) -> None:
        settings = _mock_settings(llm_api_key="test-key")
        mock_settings.return_value = settings
        mock_get_driver.return_value = MagicMock()

        mock_t2c.return_value = "MATCH (n) RETURN n"
        mock_exec.return_value = [{"name": "Alice", "type": "Person"}]
        mock_answer.return_value = "Alice is a person."

        resp = client.post("/api/ask", json={"question": "Who is Alice?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["question"] == "Who is Alice?"
        assert "cypher" in data
        assert "answer" in data
        assert "elapsed_s" in data
        assert data["confidence"] > 0.0
        assert data["insufficient_evidence"] is False
        assert data["citations"][0]["row"] == 1
        assert "Alice" in data["citations"][0]["preview"]

    @patch("neo4j_graphrag_kg.rag.pipeline.text_to_cypher")
    @patch("neo4j_graphrag_kg.rag.pipeline._execute_cypher")
    @patch("neo4j_graphrag_kg.rag.pipeline.generate_answer")
    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_ask_marks_insufficient_evidence_when_no_rows(
        self,
        mock_settings: MagicMock,
        mock_get_driver: MagicMock,
        mock_answer: MagicMock,
        mock_exec: MagicMock,
        mock_t2c: MagicMock,
    ) -> None:
        settings = _mock_settings(llm_api_key="test-key")
        mock_settings.return_value = settings
        mock_get_driver.return_value = MagicMock()

        mock_t2c.return_value = "MATCH (n) RETURN n"
        mock_exec.return_value = []
        mock_answer.return_value = "I do not have enough evidence."

        resp = client.post("/api/ask", json={"question": "Who is Alice?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["citations"] == []
        assert data["confidence"] == 0.0
        assert data["insufficient_evidence"] is True

    def test_ask_missing_question_returns_422(self) -> None:
        """Missing 'question' field in request body."""
        resp = client.post("/api/ask", json={})
        assert resp.status_code == 422

    def test_ask_invalid_content_type_returns_422(self) -> None:
        """Non-JSON request should fail."""
        resp = client.post(
            "/api/ask",
            content="not json",
            headers={"content-type": "text/plain"},
        )
        assert resp.status_code == 422


# ====================================================================
# CORS â€” headers present
# ====================================================================


class TestCORS:
    """Verify CORS headers are present for allowed origins."""

    def test_cors_headers_on_allowed_origin(self) -> None:
        resp = client.options(
            "/api/status",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    def test_cors_rejects_disallowed_origin(self) -> None:
        resp = client.options(
            "/api/status",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware returns 400 for disallowed origins
        assert resp.status_code == 400

# ====================================================================
# GET /api/diagnostics - graph consistency indicators
# ====================================================================


class TestDiagnosticsEndpoint:
    """Tests for graph consistency diagnostics endpoint."""

    @patch("neo4j_graphrag_kg.web.app.get_driver")
    @patch("neo4j_graphrag_kg.web.app.get_settings")
    def test_diagnostics_returns_indicator_payload(
        self,
        mock_settings: MagicMock,
        mock_get_driver: MagicMock,
    ) -> None:
        settings = _mock_settings()
        mock_settings.return_value = settings

        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        row_docs = {"c": 1}
        row_chunks = {"c": 2}
        row_related = {"c": 0}
        session.run.side_effect = [
            MagicMock(single=MagicMock(return_value=row_docs)),
            MagicMock(single=MagicMock(return_value=row_chunks)),
            MagicMock(single=MagicMock(return_value=row_related)),
        ]

        mock_get_driver.return_value = driver

        resp = client.get("/api/diagnostics")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "attention"
        assert payload["stale_total"] == 3
        assert payload["checks"]["documents_without_chunks"] == 1
        assert payload["checks"]["orphan_chunks"] == 2


# ====================================================================
# GET /api/ingest/jobs - recent ingest history
# ====================================================================


class TestIngestJobsEndpoint:
    """Tests for ingest job history endpoint."""

    @patch("neo4j_graphrag_kg.web.app._get_services")
    def test_ingest_jobs_returns_recent_jobs(self, mock_get_services: MagicMock) -> None:
        jobs = MagicMock()
        jobs.list_jobs.return_value = [
            {
                "id": "ingest::doc-1",
                "doc_id": "doc-1",
                "status": "completed",
                "stage": "completed",
                "attempt": 1,
                "max_retries": 2,
                "updated_at": "2026-03-05T10:00:00+00:00",
                "completed_at": "2026-03-05T10:00:10+00:00",
                "error": "",
                "summary": {"chunks": 2, "entities": 3, "edges": 1},
            }
        ]

        ingest = MagicMock(jobs=jobs)
        services = MagicMock(ingest=ingest)
        mock_get_services.return_value = services

        resp = client.get("/api/ingest/jobs?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == "ingest::doc-1"
        assert data["jobs"][0]["status"] == "completed"
