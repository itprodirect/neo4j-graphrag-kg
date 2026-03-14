"""RAG pipeline orchestrator: question → text2cypher → execute → answer.

Ties together text2cypher and answer generation with retry logic.
If Cypher execution fails, retries text2cypher once with the error.

NEVER logs API keys or full LLM prompts containing user data.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import neo4j as _neo4j
from neo4j import Driver

from neo4j_graphrag_kg.rag.answer import (
    RAGResponse,
    build_response_metadata,
    generate_answer,
)
from neo4j_graphrag_kg.rag.text2cypher import text_to_cypher, validate_cypher_readonly

logger = logging.getLogger(__name__)


def _execute_cypher(
    driver: Driver,
    database: str,
    cypher: str,
) -> list[dict[str, Any]]:
    """Execute a **read-only** Cypher query and return results as dicts.

    Uses a read-access session so the Neo4j server will also reject any
    write operations that slip through the application-level validator.

    Converts Neo4j types (Path, Node, Relationship) to strings for
    JSON serialization.
    """

    def _run_query(tx: Any) -> list[dict[str, Any]]:
        result = tx.run(cypher)
        rows: list[dict[str, Any]] = []
        for record in result:
            row: dict[str, Any] = {}
            for key in record.keys():
                val = record[key]
                # Convert Neo4j graph types to string representations
                if hasattr(val, "nodes") and hasattr(val, "relationships"):
                    # Path object
                    row[key] = str(val)
                elif hasattr(val, "element_id") and hasattr(val, "labels"):
                    # Node
                    row[key] = dict(val)
                elif hasattr(val, "element_id") and hasattr(val, "type"):
                    # Relationship
                    row[key] = dict(val)
                else:
                    row[key] = val
            rows.append(row)
        return rows

    with driver.session(
        database=database,
        default_access_mode=_neo4j.READ_ACCESS,
    ) as session:
        return session.execute_read(_run_query)


def ask(
    question: str,
    *,
    driver: Driver,
    database: str,
    provider: str = "anthropic",
    model: str = "",
    api_key: str = "",
    timeout: float = 60.0,
    cypher_only: bool = False,
) -> RAGResponse:
    """Run the full RAG pipeline: question → Cypher → execute → answer.

    Parameters
    ----------
    question:
        Natural language question about the knowledge graph.
    driver:
        Neo4j driver instance.
    database:
        Neo4j database name.
    provider / model / api_key:
        LLM configuration (same as extractor settings).
    cypher_only:
        If True, generate Cypher but skip execution and answer generation.

    Returns
    -------
    RAGResponse with question, cypher, results, answer, elapsed_s, and
    trust metadata derived from the executed query results.
    """
    t0 = time.perf_counter()

    logger.info("RAG query started")
    logger.debug("RAG question: %s", question)

    # Step 1: Generate Cypher
    cypher = text_to_cypher(
        question,
        driver=driver,
        database=database,
        provider=provider,
        model=model,
        api_key=api_key,
        timeout=timeout,
    )
    logger.debug("Generated Cypher (%d chars): %s", len(cypher), cypher)

    # Step 1b: Validate Cypher is read-only
    try:
        cypher = validate_cypher_readonly(cypher)
    except ValueError as ve:
        logger.warning("Cypher validation failed: %s", ve)
        elapsed = time.perf_counter() - t0
        return RAGResponse(
            question=question,
            cypher=cypher,
            results=[],
            answer=str(ve),
            elapsed_s=round(elapsed, 2),
            confidence=0.0,
            insufficient_evidence=True,
        )

    if cypher_only:
        elapsed = time.perf_counter() - t0
        return RAGResponse(
            question=question,
            cypher=cypher,
            elapsed_s=round(elapsed, 2),
            confidence=0.0,
            insufficient_evidence=True,
        )

    # Step 2: Execute Cypher (with retry on failure)
    results: list[dict[str, Any]] = []
    try:
        results = _execute_cypher(driver, database, cypher)
        logger.debug("Cypher returned %d rows", len(results))
    except Exception as exc:
        logger.warning("Cypher execution failed — retrying text2cypher")
        # Retry: regenerate Cypher with the error context
        retry_question = (
            f"{question}\n\n"
            f"(Previous Cypher failed with error: {exc}. "
            f"Previous query was: {cypher}. "
            f"Please fix the query.)"
        )
        try:
            cypher = text_to_cypher(
                retry_question,
                driver=driver,
                database=database,
                provider=provider,
                model=model,
                api_key=api_key,
                timeout=timeout,
            )
            # Validate the retry too
            cypher = validate_cypher_readonly(cypher)
            logger.debug("Retry generated Cypher (%d chars)", len(cypher))
            results = _execute_cypher(driver, database, cypher)
            logger.debug("Retry Cypher returned %d rows", len(results))
        except Exception as retry_exc:
            logger.error("Retry also failed")
            elapsed = time.perf_counter() - t0
            return RAGResponse(
                question=question,
                cypher=cypher,
                results=[],
                answer=(
                    f"I was unable to query the graph. "
                    f"The generated Cypher query failed: {retry_exc}"
                ),
                elapsed_s=round(elapsed, 2),
                confidence=0.0,
                insufficient_evidence=True,
            )

    citations, confidence, insufficient_evidence = build_response_metadata(results)

    # Step 3: Generate answer
    answer = generate_answer(
        question,
        cypher,
        results,
        provider=provider,
        model=model,
        api_key=api_key,
        timeout=timeout,
    )

    elapsed = time.perf_counter() - t0
    logger.info("RAG query completed: %d rows, %.2fs", len(results), elapsed)
    return RAGResponse(
        question=question,
        cypher=cypher,
        results=results,
        answer=answer,
        elapsed_s=round(elapsed, 2),
        citations=citations,
        confidence=confidence,
        insufficient_evidence=insufficient_evidence,
    )
