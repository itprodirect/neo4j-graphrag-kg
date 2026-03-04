# neo4j-graphrag-kg

Neo4j-first knowledge graph tooling for GraphRAG pipelines.

This repository is intentionally practical: clear CLI commands, deterministic IDs,
and batched graph writes. No framework maze, no magic.

## Project Status (as of 2026-03-04)

- Stage: `v1 stable foundation`, `v2 planned`, execution in progress.
- Test status: `186 passed, 11 skipped` (`pytest -q` on 2026-03-04).
- Recent additions:
  - Durable staged ingest jobs (`kg ingest`, `kg ingest-status`, `kg ingest-run`)
  - Read-only query safety defaults with `--allow-write` escape hatch
  - Synthetic fraud/E&O investigation dataset for realistic demos
- Current blockers:
  - GitHub CLI token is invalid locally, so issue auto-creation is prepared but not executed.

## What It Does Today

1. Ingests text documents into a Neo4j graph.
2. Chunks text, extracts entities/relationships (heuristic or LLM), and upserts in batches.
3. Supports ad-hoc Cypher querying from CLI.
4. Supports GraphRAG-style natural-language Q/A (`kg ask`).
5. Serves a lightweight graph explorer web UI (`kg serve`).

## Current CLI Surface

- `kg ping` - verify Neo4j connectivity.
- `kg init-db` - create constraints and indexes (idempotent).
- `kg status` - show Neo4j version, counts, constraints, indexes.
- `kg ingest` - queue and optionally run a staged ingest job.
- `kg ingest-status` - inspect durable ingest job state.
- `kg ingest-run` - run a queued ingest job by ID.
- `kg query` - run Cypher (read-only validated by default).
- `kg ask` - natural language question to Cypher and answer flow.
- `kg serve` - run web UI/API.
- `kg reset` - destructive reset (requires `--confirm`).

## Quickstart

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Neo4j credentials configured in `.env`

### Setup

```bash
git clone https://github.com/itprodirect/neo4j-graphrag-kg.git
cd neo4j-graphrag-kg
cp .env.example .env
# set NEO4J_PASSWORD in .env

docker compose up -d
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
```

### Validate

```bash
kg ping
kg init-db
pytest -q
```

### First Ingest

```bash
kg ingest --input examples/demo.txt --doc-id demo --title "Demo"
kg query --cypher "MATCH (e:Entity) RETURN e.name ORDER BY e.name LIMIT 25"
```

## Synthetic Investigation Dataset

For fraud, misrepresentation, and E&O style scenarios:

- Dataset docs: `examples/synthetic_claims_network/`
- Query pack: `examples/synthetic_claims_network/investigator_queries.md`
- Ingest script: `scripts/ingest-synthetic-claims.ps1`

```powershell
powershell -NoProfile -File scripts/ingest-synthetic-claims.ps1 -Extractor simple
```

LLM extraction variant:

```powershell
powershell -NoProfile -File scripts/ingest-synthetic-claims.ps1 -Extractor llm -Provider openai -Model gpt-4o
```

## Architecture Snapshot

- Package layout: `src/neo4j_graphrag_kg/`
- Core modules:
  - `config.py` for environment settings
  - `neo4j_client.py` for driver lifecycle
  - `ingest.py` for staged pipeline and durable jobs
  - `extractors/` for `simple` and `llm` extractor implementations
  - `upsert.py` for batched `UNWIND ... MERGE` writes
  - `rag/` for text2cypher and answer pipeline
  - `web/` for FastAPI + static graph UI

## Documentation Map

- Architecture and troubleshooting: `docs/DEV_NOTES.md`
- Engineering review snapshot: `docs/CODE_REVIEW.md`
- Build history and status log: `docs/SESSION_LOG.md`
- V2 blueprint: `docs/V2_REBUILD_BLUEPRINT.md`
- V2 phased roadmap: `docs/V2_ROADMAP.md`
- V2 issue backlog: `docs/V2_GITHUB_ISSUES.md`

## Roadmap

### Near-term (active)

1. Land v2 phase 0 and phase 1 work items:
   - relationship direction correctness
   - re-ingest reconciliation
   - typed service contracts
2. Enforce CI quality gates (`ruff`, `mypy`, Neo4j integration).
3. Improve evidence-rich RAG response contract (citations + confidence).

### Full plan

See:

- `docs/V2_ROADMAP.md`
- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_GITHUB_ISSUES.md`

## Contributing and Commit Style

Small, descriptive commits are preferred:

- `feat(ingest): add reconciliation mode skeleton`
- `fix(rag): block unsafe call patterns`
- `docs(v2): clarify phase exit criteria`

One behavior change plus tests per commit is the happy path.

## License

MIT

---

Built by humans and AI, with useful output as the only vanity metric.
