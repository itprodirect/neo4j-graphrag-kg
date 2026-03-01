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

**Next steps:** → Completed in Session 3 (LLM extraction)

---

## Session 3 — LLM-Powered Extraction + Pluggable Architecture

**Goal:** Add LLM-based entity/relationship extraction with a pluggable
extractor architecture supporting Anthropic (Claude) and OpenAI.

**What changed:**

### New modules
- `extractors/base.py` — `BaseExtractor` ABC, shared dataclasses (`ExtractedEntity`, `ExtractedRelationship`, `ExtractionResult`)
- `extractors/simple.py` — Migrated heuristic extractor, implements `BaseExtractor`, preserves legacy standalone functions
- `extractors/llm.py` — `LLMExtractor` with dual-provider support (Anthropic + OpenAI), JSON parsing with retry, temperature=0
- `extractors/__init__.py` — Registry with `get_extractor("simple"|"llm", **kwargs)` factory, lazy LLM imports

### Modified modules
- `extractor.py` — Now a backward-compat shim re-exporting from `extractors.simple`
- `ingest.py` — Accepts optional `extractor: BaseExtractor` param; pluggable path deduplicates entities by slug, batches all upserts
- `config.py` — Added `extractor_type`, `llm_provider`, `llm_model`, `llm_api_key`, `entity_types`, `relationship_types`
- `cli.py` — New flags: `--extractor`, `--provider`, `--model`, `--entity-types`
- `pyproject.toml` — Optional deps: `.[anthropic]`, `.[openai]`, `.[llm]`
- `.env.example` — Added LLM + schema constraint vars

### Tests
- `test_extractors_base.py` — 9 tests for dataclasses + ABC enforcement
- `test_extractors_llm.py` — 15 tests with mocked API (JSON parsing, retry, confidence clamping, error handling)
- All 84 tests pass (zero regressions from Session 2)

### Demo content
- `examples/demo_llm.txt` — 5 paragraphs about fictional "Nexus Technologies" with rich named entities (people, organizations, locations, technologies)

### Design decisions
- **Base package has zero new deps** — anthropic/openai SDKs loaded lazily only when LLM extractor is instantiated
- **Dual type system** — Legacy types (with `.id`, `.source_id`) preserved for standalone functions; base types for pluggable interface
- **Backward compatible** — All existing imports via `extractor.py` shim continue to work
- **Schema-guided extraction** — Entity/relationship types passed in system prompt to constrain LLM output
- **Never logs API keys** — Keys only used inside provider call functions

**How to run:**

```bash
source .venv/Scripts/activate

# Heuristic extractor (default — no API key needed)
kg ingest --input examples/demo.txt --doc-id demo --title "Demo"

# LLM extractor (requires LLM_API_KEY in .env or --provider/--model flags)
pip install -e ".[llm]"
kg ingest --input examples/demo_llm.txt --doc-id nexus --title "Nexus Corp" --extractor llm

# Compare results
kg query --cypher "MATCH (e:Entity) RETURN e.name, e.type ORDER BY e.type, e.name"
```

**Next steps:**
- Vector embeddings on chunks/entities for semantic search
- `kg search` command combining vector + graph traversal
- Multi-document ingestion (directory/glob support)
- RAG query interface (natural language → Cypher → answer)
- CI/CD pipeline
