# Developer Notes

Technical notes for maintainers and contributors.

## Snapshot (as of 2026-03-08)

| Topic | Status |
|---|---|
| Runtime surface | Stable for v1 workflows |
| Durable ingest jobs | Implemented |
| Query safety defaults | Implemented |
| v2 planning docs | Implemented (`docs/V2_*.md`) |
| CI static quality gates | Implemented (`ruff`, `mypy`, `pytest`) |
| Neo4j integration CI | Implemented |
| RAG trust metadata | Implemented (`citations`, `confidence`, `insufficient_evidence`) |
| v2 refactor execution | Planned |

## Core Flow

```text
Text file -> chunk -> extract -> normalize IDs -> batched upsert -> Neo4j
```

## Module Guide

| Module | Responsibility |
|---|---|
| `config.py` | Environment-backed settings (`python-dotenv`) |
| `neo4j_client.py` | Singleton Neo4j driver lifecycle |
| `schema.py` | Neo4j 5+ constraints and indexes (`IF NOT EXISTS`) |
| `chunker.py` | Fixed-size chunking with overlap |
| `extractors/` | Pluggable extraction (`simple`, `llm`) |
| `ingest.py` | Staged orchestration + durable job state |
| `upsert.py` | Batched transactional writes + transient retry |
| `rag/` | Text-to-Cypher, query execution, answer generation, trust metadata |
| `web/app.py` | API + static graph UI |

## Invariants

### IDs

- Entity ID: `slugify(name)`
- Chunk ID: `"{doc_id}::chunk::{idx}"`
- Relationship ID: deterministic composition of doc/chunk/endpoints/extractor/type

### Writes

- Use `UNWIND $rows AS row ... MERGE ...` for graph writes.
- Avoid single-row MERGE loops in Python.
- Keep write operations in explicit or managed transactions.

### Safety

- Never log API keys or credentials.
- Read-only validation is default for ad-hoc query execution.
- Destructive commands require explicit user intent.

## Current Gaps

1. Preserve relationship direction end-to-end in staged extraction writes.
2. Reconcile stale graph artifacts when source documents change.
3. Improve onboarding diagnostics for local setup and dependency issues.

Backlog source: `docs/V2_GITHUB_ISSUES.md`.

## Troubleshooting

### Cannot connect to Neo4j

- Verify `.env` values:
  - `NEO4J_URI`
  - `NEO4J_USER`
  - `NEO4J_PASSWORD`
- Check container state:

```bash
docker compose ps
docker compose logs neo4j
```

### Local fresh reset

```bash
docker compose down -v
docker compose up -d
kg init-db
```

### Import errors

```bash
pip install -e ".[dev]"
```

### Test behavior

- Unit tests run without Neo4j.
- Integration tests skip when Neo4j is unreachable.

```bash
pytest -q
```

## Related Docs

- `README.md`
- `docs/CODE_REVIEW.md`
- `docs/SESSION_LOG.md`
- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_ROADMAP.md`
