# Developer Notes

Technical notes for maintainers and contributors.

## Status Snapshot (as of 2026-03-04)

- Runtime surface is stable for v1 workflows.
- Durable ingest jobs are implemented.
- Read-only Cypher safety defaults are in place for query paths.
- v2 blueprint and roadmap are documented in `docs/V2_*.md`.

## Core Architecture

Pipeline flow:

```text
Text file -> chunk -> extract -> normalize IDs -> batched upsert -> Neo4j
```

Major modules:

- `config.py`: environment-backed settings (`python-dotenv`)
- `neo4j_client.py`: singleton Neo4j driver lifecycle
- `schema.py`: Neo4j 5+ constraints and indexes (`IF NOT EXISTS`)
- `chunker.py`: fixed-size chunking with overlap
- `extractors/`: pluggable extraction layer (`simple`, `llm`)
- `ingest.py`: staged orchestration + durable job state
- `upsert.py`: batched transactional writes with retry on transient errors
- `rag/`: text-to-Cypher, execution, answer generation
- `web/app.py`: API + static graph UI

## Invariants

### ID Rules

- Entity ID: `slugify(name)`
- Chunk ID: `"{doc_id}::chunk::{idx}"`
- Relationship ID: deterministic from doc, chunk, endpoints, extractor, and type

### Write Rules

- Use `UNWIND $rows AS row ... MERGE ...` for all graph writes.
- Do not perform single-row MERGE in Python loops.
- Keep writes in explicit/managed transactions.

### Safety Rules

- Never log credentials or API keys.
- Read-only validation is the default for ad-hoc query execution.
- Destructive actions require explicit opt-in flags.

## Current Gaps to Track

1. Relationship direction must be preserved end-to-end in all extraction paths.
2. Re-ingest of changed source should reconcile stale graph artifacts.
3. CI should enforce lint/type checks and run a Neo4j-backed integration job.
4. RAG response contract needs explicit citations and evidence quality signaling.

These items are tracked in `docs/V2_GITHUB_ISSUES.md`.

## Troubleshooting

### Cannot connect to Neo4j

- Confirm `.env` values:
  - `NEO4J_URI`
  - `NEO4J_USER`
  - `NEO4J_PASSWORD`
- Check container health:

```bash
docker compose ps
docker compose logs neo4j
```

### Fresh reset for local dev

```bash
docker compose down -v
docker compose up -d
kg init-db
```

### Package import errors

Install editable package from repo root:

```bash
pip install -e ".[dev]"
```

### Test behavior

- Unit tests should run without Neo4j.
- Integration tests are marked and skip if Neo4j is unreachable.

```bash
pytest -q
```

## Related Docs

- `README.md`
- `docs/CODE_REVIEW.md`
- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_ROADMAP.md`
