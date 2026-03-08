"""FastAPI web server for graph visualization and RAG queries.

Endpoints:
  GET  /                        → serves the visualization HTML page
  GET  /api/graph?limit=200     → full graph data (nodes + edges) as JSON
  GET  /api/graph/entity/{name} → subgraph around an entity (2 hops)
  GET  /api/graph/document/{id} → subgraph for a specific document
  POST /api/ask                 → RAG query (question → answer)
  GET  /api/status              → Neo4j status as JSON

All endpoints use the existing singleton Neo4j driver.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from neo4j_graphrag_kg.config import get_settings
from neo4j_graphrag_kg.neo4j_client import get_driver
from neo4j_graphrag_kg.services import GraphService, ServiceContainer, build_service_container

logger = logging.getLogger(__name__)

app = FastAPI(title="neo4j-graphrag-kg", version="0.1.0")

# CORS — restricted to configured origins (default: localhost:8000).
# Set CORS_ORIGINS=* in .env to allow all origins (opt-in only).
_cors_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_services() -> ServiceContainer:
    """Build runtime service container for the current request."""
    settings = get_settings()
    driver = get_driver(settings)
    return build_service_container(settings, driver=driver)


def _get_graph_service() -> GraphService:
    """Return a graph service built from runtime settings + injected driver."""
    return _get_services().graph


def _node_to_dict(node: Any) -> dict[str, Any]:
    """Convert a Neo4j Node to a serialisable dict."""
    labels = list(node.labels) if hasattr(node, "labels") else []
    props = dict(node) if hasattr(node, "items") else {}
    return {
        "id": props.get("id", str(node.element_id)),
        "labels": labels,
        "properties": props,
    }


def _rel_to_dict(rel: Any) -> dict[str, Any]:
    """Convert a Neo4j Relationship to a serialisable dict."""
    props = dict(rel) if hasattr(rel, "items") else {}
    return {
        "type": rel.type if hasattr(rel, "type") else "UNKNOWN",
        "properties": props,
        "start_node_element_id": (
            str(rel.start_node.element_id) if hasattr(rel, "start_node") else ""
        ),
        "end_node_element_id": (
            str(rel.end_node.element_id) if hasattr(rel, "end_node") else ""
        ),
    }


def _graph_query(cypher: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a Cypher query and return {nodes: [...], edges: [...]}."""
    graph = _get_graph_service()
    nodes_map: dict[str, dict[str, Any]] = {}
    edges_list: list[dict[str, Any]] = []

    with graph.session() as session:
        result = session.run(cypher, params or {})
        for record in result:
            for value in record.values():
                if hasattr(value, "labels"):
                    # Node
                    nid = str(value.element_id)
                    if nid not in nodes_map:
                        nd = _node_to_dict(value)
                        nd["_element_id"] = nid
                        nodes_map[nid] = nd
                elif hasattr(value, "type") and hasattr(value, "start_node"):
                    # Relationship
                    start_eid = str(value.start_node.element_id)
                    end_eid = str(value.end_node.element_id)
                    rd = _rel_to_dict(value)
                    rd["source"] = start_eid
                    rd["target"] = end_eid
                    edges_list.append(rd)
                    # Ensure endpoints are in nodes_map
                    if start_eid not in nodes_map:
                        nodes_map[start_eid] = _node_to_dict(value.start_node)
                        nodes_map[start_eid]["_element_id"] = start_eid
                    if end_eid not in nodes_map:
                        nodes_map[end_eid] = _node_to_dict(value.end_node)
                        nodes_map[end_eid]["_element_id"] = end_eid
                elif hasattr(value, "nodes") and hasattr(value, "relationships"):
                    # Path
                    for node in value.nodes:
                        nid = str(node.element_id)
                        if nid not in nodes_map:
                            nd = _node_to_dict(node)
                            nd["_element_id"] = nid
                            nodes_map[nid] = nd
                    for rel in value.relationships:
                        start_eid = str(rel.start_node.element_id)
                        end_eid = str(rel.end_node.element_id)
                        rd = _rel_to_dict(rel)
                        rd["source"] = start_eid
                        rd["target"] = end_eid
                        edges_list.append(rd)

    return {"nodes": list(nodes_map.values()), "edges": edges_list}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def index() -> FileResponse:
    """Serve the visualization HTML page."""
    html_path = _STATIC_DIR / "index.html"
    if not html_path.is_file():
        raise HTTPException(status_code=404, detail="Visualization page not found")
    return FileResponse(html_path, media_type="text/html")


@app.get("/api/graph")
async def graph_full(limit: int = Query(200, ge=1, le=1000)) -> JSONResponse:
    """Return the full graph data (nodes + edges) as JSON."""
    cypher = (
        f"MATCH (n)-[r]->(m) "
        f"RETURN n, r, m LIMIT {limit}"
    )
    try:
        data = _graph_query(cypher)
        return JSONResponse(data)
    except Exception as exc:
        logger.error("GET /api/graph failed: %s", exc)
        raise HTTPException(status_code=500, detail="Query execution failed")


_MAX_SUBGRAPH_LIMIT = 1000


@app.get("/api/graph/entity/{name}")
async def graph_entity(
    name: str,
    limit: int = Query(200, ge=1, le=1000),
) -> JSONResponse:
    """Return subgraph around a specific entity (2 hops)."""
    safe_limit = min(limit, _MAX_SUBGRAPH_LIMIT)
    # Use parameterised CONTAINS instead of regex to prevent ReDoS
    cypher = (
        "MATCH (e:Entity) WHERE toLower(e.name) CONTAINS toLower($term) "
        "OPTIONAL MATCH p=(e)-[*..2]-(other) "
        f"RETURN e, p LIMIT {safe_limit}"
    )
    params = {"term": name}
    try:
        data = _graph_query(cypher, params)
        return JSONResponse(data)
    except Exception as exc:
        logger.error("GET /api/graph/entity failed: %s", exc)
        raise HTTPException(status_code=500, detail="Query execution failed")


@app.get("/api/graph/document/{doc_id}")
async def graph_document(
    doc_id: str,
    limit: int = Query(200, ge=1, le=1000),
) -> JSONResponse:
    """Return subgraph for a specific document."""
    safe_limit = min(limit, _MAX_SUBGRAPH_LIMIT)
    cypher = (
        "MATCH (d:Document {id: $doc_id})-[r1:HAS_CHUNK]->(c:Chunk) "
        "OPTIONAL MATCH (c)-[r2:MENTIONS]->(e:Entity) "
        f"RETURN d, r1, c, r2, e LIMIT {safe_limit}"
    )
    params = {"doc_id": doc_id}
    try:
        data = _graph_query(cypher, params)
        return JSONResponse(data)
    except Exception as exc:
        logger.error("GET /api/graph/document failed: %s", exc)
        raise HTTPException(status_code=500, detail="Query execution failed")


class AskRequest(BaseModel):
    question: str


@app.post("/api/ask")
async def ask_endpoint(req: AskRequest) -> JSONResponse:
    """RAG query: question → Cypher → execute → answer."""
    settings = get_settings()

    if not settings.llm_api_key:
        raise HTTPException(
            status_code=400,
            detail="LLM_API_KEY not configured. Set it in .env.",
        )

    from neo4j_graphrag_kg.rag.pipeline import ask as rag_ask

    services = _get_services()
    try:
        response = rag_ask(
            req.question,
            driver=services.driver,
            database=services.graph.database,
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
        )
        return JSONResponse({
            "question": response.question,
            "cypher": response.cypher,
            "answer": response.answer,
            "row_count": len(response.results),
            "elapsed_s": response.elapsed_s,
            "citations": response.citations,
            "confidence": response.confidence,
            "insufficient_evidence": response.insufficient_evidence,
        })
    except Exception as exc:
        logger.error("POST /api/ask failed: %s", exc)
        raise HTTPException(status_code=500, detail="RAG query failed")


@app.get("/api/status")
async def status_endpoint() -> JSONResponse:
    """Return Neo4j status as JSON."""
    services = _get_services()
    try:
        with services.graph.session() as session:
            # Version
            ver_row = session.run(
                "CALL dbms.components() YIELD name, versions RETURN name, versions"
            ).single()
            version = (
                f"{ver_row['name']} {ver_row['versions'][0]}"
                if ver_row else "unknown"
            )

            # Counts
            counts = session.run(
                "MATCH (n) "
                "OPTIONAL MATCH ()-[r]->() "
                "RETURN count(DISTINCT n) AS nodes, count(DISTINCT r) AS rels"
            ).single()

        return JSONResponse({
            "version": version,
            "nodes": counts["nodes"] if counts else 0,
            "relationships": counts["rels"] if counts else 0,
        })
    except Exception as exc:
        logger.error("GET /api/status failed: %s", exc)
        raise HTTPException(status_code=500, detail="Service unavailable")

@app.get("/api/ingest/jobs")
async def ingest_jobs_endpoint(
    limit: int = Query(10, ge=1, le=50),
) -> JSONResponse:
    """Return recent ingest jobs for UI history and troubleshooting."""
    services = _get_services()
    try:
        jobs_raw = services.ingest.jobs.list_jobs(limit=limit)
        jobs: list[dict[str, Any]] = []
        for job in jobs_raw:
            summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
            jobs.append({
                "id": str(job.get("id", "")),
                "doc_id": str(job.get("doc_id", "")),
                "status": str(job.get("status", "unknown")),
                "stage": str(job.get("stage", "unknown")),
                "attempt": int(job.get("attempt", 0)),
                "max_retries": int(job.get("max_retries", 0)),
                "updated_at": str(job.get("updated_at", "")),
                "completed_at": str(job.get("completed_at", "")),
                "error": str(job.get("error", "")),
                "summary": summary,
            })
        return JSONResponse({"jobs": jobs})
    except Exception as exc:
        logger.error("GET /api/ingest/jobs failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not load ingest history")


@app.get("/api/diagnostics")
async def diagnostics_endpoint() -> JSONResponse:
    """Return lightweight graph consistency indicators for stale-data visibility."""
    services = _get_services()
    try:
        return JSONResponse(services.graph.diagnostics())
    except Exception as exc:
        logger.error("GET /api/diagnostics failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not load diagnostics")
