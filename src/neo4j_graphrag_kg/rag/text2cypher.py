"""Text-to-Cypher: convert natural language questions to Cypher queries.

Uses the configured LLM provider (anthropic or openai) with the graph
schema fetched dynamically from Neo4j.  SDKs are imported lazily.

NEVER logs or prints API keys.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from neo4j import Driver

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------

_SCHEMA_QUERY_FULL = """\
CALL db.schema.nodeTypeProperties() YIELD nodeType, propertyName
RETURN DISTINCT nodeType, collect(DISTINCT propertyName) AS properties
"""

_SCHEMA_RELS_FULL = """\
CALL db.schema.relTypeProperties() YIELD relType, propertyName
RETURN DISTINCT relType, collect(DISTINCT propertyName) AS properties
"""


def get_graph_schema(driver: Driver, database: str) -> str:
    """Fetch the graph schema as a human-readable string.

    Tries ``db.schema.nodeTypeProperties()`` first; falls back to
    ``db.labels()`` / ``db.relationshipTypes()`` if not available.
    """
    try:
        return _schema_full(driver, database)
    except Exception:
        logger.debug("Full schema introspection unavailable, using fallback")
        return _schema_fallback(driver, database)


def _schema_full(driver: Driver, database: str) -> str:
    parts: list[str] = []
    with driver.session(database=database) as session:
        # Nodes
        node_rows = list(session.run(_SCHEMA_QUERY_FULL))
        if node_rows:
            parts.append("Node labels and properties:")
            for row in node_rows:
                props = ", ".join(row["properties"]) if row["properties"] else "(none)"
                parts.append(f"  {row['nodeType']}: {props}")

        # Relationships
        rel_rows = list(session.run(_SCHEMA_RELS_FULL))
        if rel_rows:
            parts.append("Relationship types and properties:")
            for row in rel_rows:
                props = ", ".join(row["properties"]) if row["properties"] else "(none)"
                parts.append(f"  {row['relType']}: {props}")

    if not parts:
        raise RuntimeError("No schema data returned")
    return "\n".join(parts)


def _schema_fallback(driver: Driver, database: str) -> str:
    parts: list[str] = []
    with driver.session(database=database) as session:
        labels = [r["label"] for r in session.run("CALL db.labels() YIELD label")]
        rel_types = [
            r["relationshipType"]
            for r in session.run(
                "CALL db.relationshipTypes() YIELD relationshipType"
            )
        ]
        prop_keys = [
            r["propertyKey"]
            for r in session.run("CALL db.propertyKeys() YIELD propertyKey")
        ]

    if labels:
        parts.append(f"Node labels: {', '.join(labels)}")
    if rel_types:
        parts.append(f"Relationship types: {', '.join(rel_types)}")
    if prop_keys:
        parts.append(f"Property keys: {', '.join(prop_keys)}")
    return "\n".join(parts) or "(empty graph)"


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a Cypher query expert for Neo4j knowledge graphs.
Given a natural language question and the graph schema below, generate a \
Cypher query that answers the question.

Graph schema:
{schema}

Few-shot examples:
Q: What entities are in the graph?
MATCH (e:Entity) RETURN e.name, e.type ORDER BY e.name LIMIT 25

Q: How are X and Y related?
MATCH p=shortestPath((a:Entity)-[*..5]-(b:Entity)) WHERE a.name =~ '(?i).*X.*' AND b.name =~ '(?i).*Y.*' RETURN p

Q: What documents mention entity X?
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity) WHERE e.name =~ '(?i).*X.*' RETURN DISTINCT d.title, d.id

Q: Show me all relationships for entity X
MATCH (e:Entity)-[r]->(other) WHERE e.name =~ '(?i).*X.*' RETURN e.name, type(r), r.type, other.name LIMIT 50

Rules:
- Generate READ-ONLY Cypher queries only. NEVER generate CREATE, MERGE, DELETE, SET, REMOVE, or DROP statements.
- Return ONLY the Cypher query, no explanation, no markdown fences.
- Use case-insensitive regex matching (=~) for entity name lookups.
- Always include a LIMIT clause to avoid huge result sets.
- Do NOT use APOC procedures.
"""

_USER_PROMPT = "Question: {question}"

_FENCE_RE = re.compile(r"```(?:cypher)?\s*\n?(.*?)\n?\s*```", re.DOTALL)

# ---------------------------------------------------------------------------
# Read-only Cypher validation
# ---------------------------------------------------------------------------

_WRITE_CLAUSES_RE = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH\s+DELETE|SET|REMOVE|DROP|LOAD\s+CSV)\b",
    re.IGNORECASE,
)
_DBMS_CALL_RE = re.compile(r"\bCALL\s+dbms\b", re.IGNORECASE)
_MULTI_STATEMENT_RE = re.compile(r";\s*\S")
_HAS_LIMIT_RE = re.compile(r"\bLIMIT\b", re.IGNORECASE)

_DEFAULT_RAG_LIMIT = 100


def validate_cypher_readonly(cypher: str) -> str:
    """Validate that a Cypher query is read-only and inject LIMIT if missing.

    Raises ``ValueError`` if the query contains write clauses, admin calls,
    or multiple statements (semicolon-separated).

    Returns the (possibly LIMIT-injected) Cypher string.
    """
    stripped = cypher.strip()
    if not stripped:
        raise ValueError("Empty Cypher query")

    # Reject write clauses
    m = _WRITE_CLAUSES_RE.search(stripped)
    if m:
        raise ValueError(
            f"LLM-generated Cypher contains a write clause ({m.group()!r}) "
            "and was blocked for safety. Only read-only queries are allowed."
        )

    # Reject admin procedure calls
    if _DBMS_CALL_RE.search(stripped):
        raise ValueError(
            "LLM-generated Cypher contains a 'CALL dbms' admin call "
            "and was blocked for safety."
        )

    # Reject multi-statement queries
    if _MULTI_STATEMENT_RE.search(stripped):
        raise ValueError(
            "LLM-generated Cypher contains multiple statements (semicolons) "
            "and was blocked for safety."
        )

    # Inject LIMIT if missing
    if not _HAS_LIMIT_RE.search(stripped):
        stripped = stripped.rstrip().rstrip(";")
        stripped += f" LIMIT {_DEFAULT_RAG_LIMIT}"

    return stripped


def _strip_cypher(raw: str) -> str:
    """Extract Cypher from LLM response, stripping fences/preamble."""
    text = raw.strip()
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    # Find first line that looks like Cypher
    for line in text.split("\n"):
        line = line.strip()
        if line.upper().startswith(("MATCH", "CALL", "RETURN", "WITH", "OPTIONAL", "CREATE", "MERGE", "UNWIND")):
            # Take from this line to end
            idx = text.index(line)
            return text[idx:].strip()
    return text


# ---------------------------------------------------------------------------
# Provider call wrappers (same pattern as extractors/llm.py)
# ---------------------------------------------------------------------------

def _call_anthropic(api_key: str, model: str, system: str, user: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "The 'anthropic' package is required for RAG queries with "
            "provider='anthropic'. Install it with: pip install -e \".[anthropic]\""
        )
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(
        block.text for block in message.content if hasattr(block, "text")
    )


def _call_openai(api_key: str, model: str, system: str, user: str) -> str:
    try:
        import openai
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for RAG queries with "
            "provider='openai'. Install it with: pip install -e \".[openai]\""
        )
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


_PROVIDERS: dict[str, Any] = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def text_to_cypher(
    question: str,
    *,
    driver: Driver,
    database: str,
    provider: str = "anthropic",
    model: str = "",
    api_key: str = "",
) -> str:
    """Convert a natural language *question* to a Cypher query.

    Returns the generated Cypher string.
    """
    if not api_key:
        raise ValueError(
            "LLM_API_KEY is required for RAG queries. "
            "Set it in .env or as an environment variable."
        )
    if provider not in _PROVIDERS:
        raise ValueError(
            f"Unsupported LLM provider {provider!r}. "
            f"Choose from: {', '.join(_PROVIDERS)}"
        )

    resolved_model = model or (
        "claude-sonnet-4-20250514" if provider == "anthropic" else "gpt-4o"
    )
    call_fn = _PROVIDERS[provider]

    schema = get_graph_schema(driver, database)
    logger.debug("Graph schema:\n%s", schema)

    system = _SYSTEM_PROMPT.format(schema=schema)
    user = _USER_PROMPT.format(question=question)

    t0 = time.perf_counter()
    raw = call_fn(api_key, resolved_model, system, user)
    elapsed = time.perf_counter() - t0
    logger.info("text2cypher LLM call took %.2fs", elapsed)

    cypher = _strip_cypher(raw)
    logger.debug("Generated Cypher: %s", cypher)
    return cypher
