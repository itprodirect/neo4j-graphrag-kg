# AGENTS.md — Guidance for AI agents working in this repo

## Project overview
Neo4j-based Knowledge Graph for GraphRAG pipelines. Python 3.11+, minimal deps.

## Key conventions
- **Package layout**: `src/neo4j_graphrag_kg/` (src-layout).
- **CLI**: Typer-based, entry-point `kg` (via `[project.scripts]`).
- **Neo4j driver**: Singleton in `neo4j_client.py`; always use `get_driver()`.
- **Config**: Environment variables loaded via `python-dotenv`. Never log credentials.
- **Schema**: Neo4j 5+ syntax only (`IF NOT EXISTS`). No deprecated 4.x syntax.
- **Tests**: `pytest`. Integration tests use `neo4j_available` marker from `conftest.py` and skip when Neo4j is unreachable.
- **IDs**: Entity IDs are `slugify(name)` (deterministic, cross-doc dedup). Chunk IDs are `"{doc_id}::chunk::{idx}"`.
- **Neo4j writes**: Always use `UNWIND $rows AS row ... MERGE ...` inside explicit transactions. Never single-row MERGE in a Python loop.

## Commands
```
kg ping       — verify Neo4j connectivity
kg init-db    — create constraints & indexes (idempotent)
kg status     — show Neo4j version, node/rel counts, constraints
kg ingest     — ingest text file: chunk → extract → upsert
kg query      — run Cypher query, print results as table
kg reset      — drop all data (requires --confirm flag)
```

## Module map
- `ids.py` — slugify + deterministic ID generation
- `chunker.py` — fixed-size character chunker with overlap
- `extractor.py` — heuristic entity extraction + co-occurrence edges
- `upsert.py` — batched UNWIND MERGE operations (Document, Chunk, Entity, rels)
- `ingest.py` — pipeline orchestrator (read → chunk → extract → upsert)

## Security
- `.env` holds secrets; it is in `.gitignore` and `.dockerignore`.
- Docker Compose uses `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}` (never `none`).
- Never print or log passwords/tokens.

## Architecture docs
See `docs/DEV_NOTES.md` for detailed architecture, ID rules, and troubleshooting.
