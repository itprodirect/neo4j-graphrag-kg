# Session Log

## Session 1 — Project Bootstrap

**Goal:** Clean, Neo4j-first Python project scaffold with working CLI.

**What changed:**
- Created src-layout package `neo4j_graphrag_kg`
- `pyproject.toml` with neo4j, typer, python-dotenv deps
- Docker Compose for Neo4j 5 Community (auth enabled)
- CLI commands: `kg ping`, `kg init-db`, `kg status`
- Schema: constraints + indexes (Neo4j 5+ IF NOT EXISTS)
- Singleton Neo4j driver with atexit cleanup
- Unit + integration tests (skip when Neo4j unreachable)
- README with Windows Git Bash quickstart

---

## Session 2 — MVP Ingestion + Query + Reset

**Goal:** Deterministic, idempotent ingestion pipeline with no LLM.

**What changed:**

### New modules
- `ids.py` — slugify + deterministic entity_id / chunk_id
- `chunker.py` — fixed-size character chunker with overlap
- `extractor.py` — heuristic entity extraction (capitalised phrases + known terms) + co-occurrence edge builder
- `upsert.py` — batched UNWIND MERGE for all node/rel types
- `ingest.py` — pipeline orchestrator (read → chunk → extract → upsert)

### New CLI commands
- `kg ingest --input PATH --doc-id ID --title TITLE [--source] [--chunk-size] [--chunk-overlap]`
- `kg query --cypher "..."` — prints results as aligned table
- `kg reset --confirm` — batched DETACH DELETE with safety flag

### Tests
- Unit tests: `test_ids.py` (12), `test_chunker.py` (8), `test_extractor.py` (12)
- Integration: `test_integration_ingest.py` — reset, ingest twice, verify idempotency

### Docs
- `examples/demo.txt` — 4 paragraphs about graph databases + GraphRAG
- `docs/DEV_NOTES.md` — architecture, ID rules, batching rule, troubleshooting
- `docs/SESSION_LOG.md` — this file

**How to run:**

```bash
source .venv/Scripts/activate
kg reset --confirm
kg init-db
kg ingest --input examples/demo.txt --doc-id demo --title "Demo"
kg status
kg query --cypher "MATCH (e:Entity) RETURN e.name, e.type ORDER BY e.name LIMIT 25"
pytest -q
```

**Next steps:**
- LLM-based entity extraction (replace heuristic with Claude/OpenAI)
- Vector embeddings on chunks/entities for semantic search
- `kg search` command combining vector + graph traversal
- Relationship type extraction (beyond generic RELATED_TO)
- Multi-document ingestion (directory/glob support)
- CI/CD pipeline
