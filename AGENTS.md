# AGENTS.md — Guidance for AI agents working in this repo

## Project overview
Neo4j-based Knowledge Graph for GraphRAG pipelines. Python 3.11+, minimal deps.

## Key conventions
- **Package layout**: `src/neo4j_graphrag_kg/` (src-layout).
- **CLI**: Typer-based, entry-point `kg` (via `[project.scripts]`).
- **Neo4j driver**: Singleton in `neo4j_client.py`; always use `get_driver()`.
- **Config**: Environment variables loaded via `python-dotenv`. Never log credentials.
- **Schema**: Neo4j 5+ syntax only (`IF NOT EXISTS`). No deprecated 4.x syntax.
- **Tests**: `pytest`. Integration tests use `@pytest.mark.integration` and skip when Neo4j is unreachable.

## Commands
```
kg ping       — verify Neo4j connectivity
kg init-db    — create constraints & indexes (idempotent)
kg status     — show Neo4j version, node/rel counts, constraints
```

## Security
- `.env` holds secrets; it is in `.gitignore` and `.dockerignore`.
- Docker Compose uses `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}` (never `none`).
- Never print or log passwords/tokens.
