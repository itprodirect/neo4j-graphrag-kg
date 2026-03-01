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
```

### 4. Verify Everything Works

```bash
kg ping        # ✅ Neo4j is reachable
kg init-db     # ✅ Creates constraints & indexes
kg status      # ✅ Shows Neo4j version + counts
```

---

## 📖 Usage

### Ingest a Document

```bash
kg ingest --input examples/demo.txt --doc-id demo --title "Demo"
```

This runs the full pipeline: **read → chunk → extract → upsert**.

### Query the Graph

```bash
# List extracted entities
kg query --cypher "MATCH (e:Entity) RETURN e.name, e.type ORDER BY e.name LIMIT 25"

# Explore relationships
kg query --cypher "MATCH (e1)-[r:RELATED_TO]->(e2) RETURN e1.name, e2.name, r.confidence ORDER BY r.confidence DESC LIMIT 10"

# View chunks for a document
kg query --cypher "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE d.id = 'demo' RETURN c.id, left(c.text, 80) AS preview"
```

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
| `kg ingest` | Ingest a text file → chunk → extract → upsert |
| `kg query` | Run arbitrary Cypher and print results as a table |
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
| **Extract** | `extractor.py` | Identifies entities & co-occurrence relationships |
| **ID** | `ids.py` | Deterministic slugs for deduplication across documents |
| **Upsert** | `upsert.py` | Batched `UNWIND ... MERGE` writes to Neo4j |
| **Schema** | `schema.py` | `CREATE CONSTRAINT/INDEX IF NOT EXISTS` (Neo4j 5+) |

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
│   ├── extractor.py         # Entity extraction + edge builder
│   ├── upsert.py            # Batched MERGE operations
│   ├── ingest.py            # Pipeline orchestrator
│   └── py.typed             # PEP 561 type marker
├── tests/
│   ├── test_config.py               # Unit: settings
│   ├── test_ids.py                  # Unit: ID generation
│   ├── test_chunker.py              # Unit: chunking logic
│   ├── test_extractor.py            # Unit: extraction
│   ├── test_integration_ping.py     # Integration: connectivity
│   ├── test_integration_init_db.py  # Integration: schema setup
│   └── test_integration_ingest.py   # Integration: idempotency
├── examples/
│   └── demo.txt                     # Sample document for ingestion
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
- [ ] **Session 3** — LLM-powered entity/relationship extraction (OpenAI / Anthropic)
- [ ] **Session 4** — RAG query interface (natural language → Cypher → answer)
- [ ] **Session 5** — Visualization layer (React + D3/force-graph)

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
