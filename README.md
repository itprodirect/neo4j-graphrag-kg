<p align="center">
  <img src="https://img.shields.io/badge/Neo4j-008CC1?style=for-the-badge&logo=neo4j&logoColor=white" alt="Neo4j" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />
</p>

# 🧠 neo4j-graphrag-kg

**A lightweight, Neo4j-first knowledge graph toolkit for building GraphRAG pipelines.**

Turn unstructured text into a queryable knowledge graph in minutes — no heavy frameworks, no bloated dependencies. Just Neo4j, Python, and a clean CLI.

---

## ✨ What It Does

```
📄 Text Document
    ↓  chunk
📦 Chunks (configurable size + overlap)
    ↓  extract
🏷️  Entities + Relationships (heuristic or LLM)
    ↓  upsert (batched MERGE)
🔗 Neo4j Knowledge Graph
    ↓  query
💡 Answers via Cypher
```

This project gives you a **reusable foundation** for knowledge graph construction. Ingest documents, extract entities and relationships, and query the resulting graph — all through a single `kg` CLI command.

---

## 🚀 Quickstart

Get up and running in under 5 minutes.

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Docker & Docker Compose | Latest |
| Git Bash | Required on Windows |

### 1. Clone & Configure

```bash
git clone https://github.com/itprodirect/neo4j-graphrag-kg.git
cd neo4j-graphrag-kg

cp .env.example .env
# Edit .env → set a strong NEO4J_PASSWORD
```

### 2. Start Neo4j

```bash
docker compose up -d
```

### 3. Install the Package

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash)
# source .venv/bin/activate     # macOS / Linux

pip install -e ".[dev]"

# Optional: install LLM support (Anthropic + OpenAI)
pip install -e ".[llm]"

# Optional: install web UI (FastAPI + Uvicorn)
pip install -e ".[web]"

# Or install everything at once
pip install -e ".[dev,all]"
```

### 4. Verify Everything Works

```bash
pip install -e ".[dev]"
python -m pytest -q

bash scripts/smoke.sh
```

---

## 📖 Usage

### Ingest a Document (Heuristic Extractor)

```bash
kg ingest --input examples/demo.txt --doc-id demo --title "Demo"
```

This runs the full pipeline: **read → chunk → extract → upsert** using the default heuristic (regex) extractor. No API key needed.

### Ingest with LLM Extraction

```bash
# Install LLM dependencies (Anthropic + OpenAI SDKs)
pip install -e ".[llm]"

# Set your API key in .env (or pass --provider / --model flags)
# LLM_PROVIDER=anthropic
# LLM_API_KEY=sk-...

# Run with LLM extractor
kg ingest --input examples/demo_llm.txt --doc-id nexus --title "Nexus Corp" --extractor llm

# Or specify provider/model inline
kg ingest --input examples/demo_llm.txt --doc-id nexus --title "Nexus Corp" \
    --extractor llm --provider openai --model gpt-4o
```

The LLM extractor produces **typed entities** (Person, Organization, Location, Technology) and **labeled relationships** (WORKS_FOR, LOCATED_IN, USES) with confidence scores and evidence snippets.

### Ask Questions in Natural Language (RAG)

```bash
# Install LLM dependencies if not already installed
pip install -e ".[llm]"

# Ask a question — generates Cypher, executes, and produces an answer
kg ask "What entities are in the graph?"

# Just generate the Cypher without executing it
kg ask "How are Alice and Nexus related?" --cypher-only
```

The RAG pipeline: **question → schema introspection → text2cypher (LLM) → execute → answer generation (LLM)**. Includes automatic retry if the generated Cypher fails.

### Visualize the Graph

```bash
# Install web dependencies
pip install -e ".[web]"

# Launch the interactive graph explorer
kg serve
```

Opens a browser with an interactive D3.js force-directed graph visualization. Features:
- Color-coded nodes by label (Document, Chunk, Entity)
- Click to highlight connections and view details
- Search box to find and highlight entities
- Built-in Ask box for RAG queries
- Zoom and pan navigation

### Query the Graph (Raw Cypher)

```bash
# List extracted entities
kg query --cypher "MATCH (e:Entity) RETURN e.name, e.type ORDER BY e.name LIMIT 25"

# Explore relationships
kg query --cypher "MATCH (e1)-[r:RELATED_TO]->(e2) RETURN e1.name, e2.name, r.type, r.confidence ORDER BY r.confidence DESC LIMIT 10"

# View chunks for a document
kg query --cypher "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE d.id = 'demo' RETURN c.id, left(c.text, 80) AS preview"
```

`kg query` is **read-only by default** and validates Cypher before execution.
Use `--allow-write` only for intentional destructive/admin operations.

```bash
# Read-only validation is enabled by default
kg query --cypher "MATCH (n) RETURN count(n) AS c"

# Explicitly bypass read-only validation
kg query --allow-write --cypher "MATCH (n) DETACH DELETE n RETURN count(*) AS deleted"
```

If validation fails, `kg query` exits with code 1 and does not execute the query.

### Reset & Rebuild

```bash
kg reset --confirm   # Wipe all data
kg init-db           # Recreate schema
```

> **Idempotent by design** — running `kg ingest` with the same `--doc-id` twice will never duplicate nodes or relationships.

---

## 🛠️ CLI Reference

| Command | Description |
|---------|-------------|
| `kg ping` | Verify Neo4j connectivity |
| `kg init-db` | Create constraints & indexes (idempotent, Neo4j 5+) |
| `kg status` | Show Neo4j version, node/relationship counts, constraints |
| `kg ingest` | Ingest a text file → chunk → extract → upsert (`--extractor simple\|llm`) |
| `kg query` | Run arbitrary Cypher and print results as a table |
| `kg ask` | Natural language question → Cypher → answer (RAG pipeline) |
| `kg serve` | Launch the web UI with interactive graph visualization |
| `kg reset` | Drop all data (requires `--confirm` flag) |

Run `kg --help` or `kg <command> --help` for full options.

---

## 🏗️ Architecture

### Graph Schema

```
(:Document {id, title, source, created_at})
    -[:HAS_CHUNK]->
(:Chunk {id, document_id, idx, text})
    -[:MENTIONS]->
(:Entity {id, name, type})

(:Entity)-[:RELATED_TO {doc_id, chunk_id, evidence, confidence, extractor}]->(:Entity)
```

### Pipeline Flow

| Stage | Module | What It Does |
|-------|--------|-------------|
| **Read** | `ingest.py` | Loads UTF-8 text files |
| **Chunk** | `chunker.py` | Fixed-size splits with configurable overlap |
| **Extract** | `extractors/` | Heuristic (`simple`) or LLM-powered (`llm`) entity/relationship extraction |
| **ID** | `ids.py` | Deterministic slugs for deduplication across documents |
| **Upsert** | `upsert.py` | Batched `UNWIND ... MERGE` writes to Neo4j |
| **Schema** | `schema.py` | `CREATE CONSTRAINT/INDEX IF NOT EXISTS` (Neo4j 5+) |
| **Text2Cypher** | `rag/text2cypher.py` | Schema introspection + LLM-generated Cypher from natural language |
| **Answer** | `rag/answer.py` | LLM generates grounded answers from Cypher results |
| **Pipeline** | `rag/pipeline.py` | Orchestrates text2cypher → execute → answer with retry |
| **Web** | `web/app.py` | FastAPI server with graph API + RAG endpoints |
| **Viz** | `web/static/index.html` | D3.js force-directed graph visualization |

### Design Principles

- **Neo4j-first** — the graph database is the center of gravity, not an afterthought
- **Minimal dependencies** — no LangChain, no Unstructured, no heavy frameworks
- **Idempotent everything** — MERGE-based writes, deterministic IDs, safe to re-run
- **Batched writes** — all Neo4j operations use `UNWIND` for performance
- **Singleton driver** — one Neo4j driver instance, reused across the application
- **Secrets never logged** — credentials stay in `.env`, never printed or committed

---

## 📁 Project Structure

```
neo4j-graphrag-kg/
├── src/neo4j_graphrag_kg/
│   ├── __init__.py          # Package root
│   ├── cli.py               # Typer CLI (kg command)
│   ├── config.py            # Settings from environment
│   ├── neo4j_client.py      # Singleton Neo4j driver
│   ├── schema.py            # Constraints & indexes
│   ├── ids.py               # Deterministic ID generation
│   ├── chunker.py           # Fixed-size character chunker
│   ├── extractor.py         # Backward-compat shim → extractors/
│   ├── extractors/
│   │   ├── __init__.py      # Registry: get_extractor("simple"|"llm")
│   │   ├── base.py          # BaseExtractor ABC + shared dataclasses
│   │   ├── simple.py        # Heuristic extractor (regex + co-occurrence)
│   │   └── llm.py           # LLM extractor (Anthropic / OpenAI)
│   ├── upsert.py            # Batched MERGE operations
│   ├── ingest.py            # Pipeline orchestrator
│   ├── rag/
│   │   ├── __init__.py      # Re-exports ask, RAGResponse
│   │   ├── text2cypher.py   # Schema introspection + Cypher generation
│   │   ├── answer.py        # RAGResponse + answer generation
│   │   └── pipeline.py      # Orchestrator with retry logic
│   ├── web/
│   │   ├── __init__.py      # Web package marker
│   │   ├── app.py           # FastAPI application
│   │   └── static/
│   │       └── index.html   # D3.js graph visualization
│   └── py.typed             # PEP 561 type marker
├── tests/
│   ├── test_config.py               # Unit: settings
│   ├── test_ids.py                  # Unit: ID generation
│   ├── test_chunker.py              # Unit: chunking logic
│   ├── test_extractor.py            # Unit: heuristic extraction
│   ├── test_extractors_base.py      # Unit: base protocol + dataclasses
│   ├── test_extractors_llm.py       # Unit: LLM extractor (mocked)
│   ├── test_fixes_session4.py       # Unit: Session 4 fixes
│   ├── test_rag.py                  # Unit: RAG pipeline (mocked)
│   ├── test_web.py                  # Unit: web API (mocked)
│   ├── test_integration_ping.py     # Integration: connectivity
│   ├── test_integration_init_db.py  # Integration: schema setup
│   └── test_integration_ingest.py   # Integration: idempotency
├── examples/
│   ├── demo.txt                     # Sample document (heuristic extractor)
│   └── demo_llm.txt                # Rich entity document (LLM extractor)
├── docs/
│   ├── DEV_NOTES.md                 # Architecture & troubleshooting
│   └── SESSION_LOG.md               # Build session changelog
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── .gitignore
├── .dockerignore
├── AGENTS.md                        # AI coding agent guardrails
└── README.md
```

---

## 🧪 Testing

```bash
pytest -q
```

Integration tests automatically **skip** when Neo4j is not reachable — so `pytest` always works, whether or not Docker is running.

---

## 🔒 Security

- `.env` is listed in both `.gitignore` and `.dockerignore` — secrets are never committed
- Neo4j auth is always enabled (`NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`)
- Credentials are never logged, printed, or exposed in error messages

---

## 🗺️ Roadmap

- [x] **Session 1** — Project scaffold, Neo4j connection, CLI (`ping`, `init-db`, `status`)
- [x] **Session 2** — Ingestion pipeline with heuristic extractor (`ingest`, `query`, `reset`)
- [x] **Session 3** — LLM-powered entity/relationship extraction (OpenAI / Anthropic)
- [x] **Session 4** — Code review fixes (relationship type persistence, ImportError handling, unified extractor interface, type validation)
- [x] **Session 5** — RAG query pipeline (`kg ask`) + interactive graph visualization (`kg serve`)

---

## 🤝 Contributing

This project is built in the open. If you find it useful or want to contribute, feel free to open an issue or PR.

---

## 📄 License

MIT

---

<p align="center">
  Built with 🧱 by <a href="https://github.com/itprodirect">IT Pro Direct</a>
</p>
