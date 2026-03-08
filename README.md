# neo4j-graphrag-kg

Neo4j-first knowledge graph tooling for GraphRAG pipelines.

Lean stack, explicit contracts, practical CLI. Fancy where useful, boring where it should be.

## At a Glance (as of 2026-03-08)

| Area | Status |
|---|---|
| Product stage | `v1 foundation stable`, `v2 plan approved` |
| Test run | `198 passed, 13 skipped` (`pytest -q`) |
| Recent work | Static-quality baseline, Neo4j integration CI, trust-aware RAG responses |
| Next focus | Phase 0/1 ingest correctness: relationship directionality and re-ingest reconciliation |

## What You Can Do Today

- Ingest documents into a Neo4j knowledge graph.
- Extract entities and relationships with either heuristic or LLM pipelines.
- Run read-safe Cypher from CLI.
- Ask natural-language questions through GraphRAG (`kg ask`) with citations and confidence signals.
- Explore graph structure in a web UI (`kg serve`).

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

## CLI Reference

| Command | Purpose |
|---|---|
| `kg ping` | Verify Neo4j connectivity |
| `kg init-db` | Create constraints/indexes (idempotent) |
| `kg status` | Show database status and schema summary |
| `kg ingest` | Queue and optionally run staged ingest job |
| `kg ingest-status` | Inspect durable ingest job state |
| `kg ingest-run` | Run queued ingest job by ID |
| `kg query` | Execute Cypher (read-only validated by default) |
| `kg ask` | Natural language question -> Cypher -> answer + trust metadata |
| `kg serve` | Start web UI/API |
| `kg reset` | Drop graph data (requires `--confirm`) |

## Synthetic Investigation Dataset

For fraud, misrepresentation, and E&O-style scenarios:

- Dataset: `examples/synthetic_claims_network/`
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

```text
Text file -> chunk -> extract -> normalize IDs -> batched upsert -> Neo4j
                                             \-> ask/query/web
```

Core modules live in `src/neo4j_graphrag_kg/`:

- `config.py` (settings)
- `neo4j_client.py` (driver lifecycle)
- `ingest.py` (staged pipeline + durable jobs)
- `extractors/` (`simple`, `llm`)
- `upsert.py` (batched writes)
- `rag/` (text2cypher + answer)
- `web/` (FastAPI + static UI)

## Documentation Map

- Developer notes: `docs/DEV_NOTES.md`
- Engineering review snapshot: `docs/CODE_REVIEW.md`
- Session/build history: `docs/SESSION_LOG.md`
- V2 blueprint: `docs/V2_REBUILD_BLUEPRINT.md`
- V2 phased roadmap: `docs/V2_ROADMAP.md`
- V2 issue backlog: `docs/V2_GITHUB_ISSUES.md`

## Roadmap

### Now

1. Execute v2 phase 0 and phase 1 ingest correctness items.
2. Improve onboarding diagnostics (`kg doctor`).
3. Add integrity diagnostics (`kg check`).

### Next

- Improve onboarding diagnostics (`kg doctor`).
- Add integrity diagnostics (`kg check`).
- Expand investigation workflow in web UI.

### Full Plan

See:

- `docs/V2_ROADMAP.md`
- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_GITHUB_ISSUES.md`

## Contributing and Commit Style

Prefer simple, reviewable commits:

- `feat(ingest): add reconciliation mode skeleton`
- `fix(rag): block unsafe call patterns`
- `docs(v2): clarify phase exit criteria`

One behavioral change plus tests per commit is the default.

## License

MIT

---

Built by humans and AI. Measured by usefulness, not adjectives.
