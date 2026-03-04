# AGENTS.md - Guidance for AI Agents in This Repository

## Purpose

This file defines the operating conventions for AI agents working on this codebase.
The goal is consistent, safe, and high-quality changes that improve product outcomes.

## Project Overview

- Project: Neo4j-based knowledge graph toolkit for GraphRAG pipelines
- Runtime: Python 3.11+
- Philosophy: lean dependencies, explicit behavior, deterministic IDs, batched writes

## Core Conventions

- Package layout: `src/neo4j_graphrag_kg/` (`src` layout)
- CLI: Typer-based entrypoint `kg` via `[project.scripts]`
- Neo4j driver: singleton in `neo4j_client.py`; always use `get_driver()`
- Config: environment variables through `python-dotenv`; never log credentials
- Schema: Neo4j 5+ syntax only (`IF NOT EXISTS`), no deprecated 4.x syntax
- Tests: `pytest`; integration tests use `neo4j_available` marker and skip if Neo4j is unreachable
- IDs:
  - Entity ID: `slugify(name)`
  - Chunk ID: `"{doc_id}::chunk::{idx}"`
- Writes: use `UNWIND $rows AS row ... MERGE ...` in transactions; never single-row MERGE loops in Python

## Current Command Surface

```text
kg ping          - verify Neo4j connectivity
kg init-db       - create constraints and indexes (idempotent)
kg status        - show Neo4j version, counts, constraints, and indexes
kg ingest        - enqueue/run staged ingest for a text file
kg ingest-status - inspect durable ingest job state
kg ingest-run    - run queued ingest job by ID
kg query         - run Cypher (read-only validated by default)
kg ask           - natural-language question to GraphRAG pipeline
kg serve         - run web UI/API service
kg reset         - drop all data (requires --confirm)
```

## Module Snapshot

- `ids.py` - deterministic ID generation helpers
- `chunker.py` - fixed-size text chunking with overlap
- `extractors/` - extraction layer (`simple`, `llm`) and shared interfaces
- `upsert.py` - batched Neo4j upsert operations
- `ingest.py` - staged ingestion orchestration and durable job state
- `rag/` - text2cypher + answer generation pipeline
- `web/` - FastAPI app and static graph UI

## Security and Safety

- `.env` contains secrets and must remain excluded from source control
- Docker Compose auth should remain `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`
- Never print or log passwords, tokens, or API keys
- Treat destructive operations as explicit opt-in actions only

## Documentation References

- Architecture and troubleshooting: `docs/DEV_NOTES.md`
- Current technical review: `docs/CODE_REVIEW.md`
- Program and roadmap context: `docs/V2_REBUILD_BLUEPRINT.md`, `docs/V2_ROADMAP.md`

## Working Style Expectations

- Prefer small, descriptive commits with clear scope
- Keep behavior changes and refactors separated when possible
- Include tests with behavior changes
- Optimize for maintainability, reliability, and user trust
