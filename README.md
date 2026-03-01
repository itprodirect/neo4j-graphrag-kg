# neo4j-graphrag-kg

Neo4j-based Knowledge Graph for GraphRAG pipelines.

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git Bash (Windows)

## Quickstart

### 1. Start Neo4j

```bash
cp .env.example .env
# Edit .env and set a strong NEO4J_PASSWORD
docker compose up -d
```

### 2. Install the package

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
```

### 3. Verify connectivity

```bash
kg ping
# Neo4j is reachable.
```

### 4. Initialise the schema

```bash
kg init-db
# Creates constraints and indexes (idempotent).
```

### 5. Check status

```bash
kg status
# Shows Neo4j version, node/relationship counts, and constraints.
```

## Session 2: Ingest Demo

After completing the quickstart above:

```bash
# Clear any existing data
kg reset --confirm

# Re-create constraints/indexes
kg init-db

# Ingest the demo document
kg ingest --input examples/demo.txt --doc-id demo --title "Demo"

# Check what was created
kg status

# Query entities
kg query --cypher "MATCH (e:Entity) RETURN e.name, e.type ORDER BY e.name LIMIT 25"

# Query relationships
kg query --cypher "MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity) RETURN e1.name, e2.name, r.confidence ORDER BY r.confidence DESC LIMIT 10"

# Query chunks for a document
kg query --cypher "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE d.id = 'demo' RETURN c.id, left(c.text, 80) AS preview"
```

The ingestion pipeline is **idempotent**: running `kg ingest` with the same `--doc-id` twice will not duplicate nodes or relationships.

## CLI Commands

| Command        | Description                                      |
|----------------|--------------------------------------------------|
| `kg ping`      | Verify Neo4j connectivity                        |
| `kg init-db`   | Create constraints & indexes (idempotent)        |
| `kg status`    | Show Neo4j version, counts, and constraints      |
| `kg ingest`    | Ingest a text file (chunk → extract → upsert)    |
| `kg query`     | Run a Cypher query and print results as a table   |
| `kg reset`     | Drop all data (requires `--confirm`)              |

## Running Tests

```bash
pytest -q
```

Integration tests are **skipped** automatically when Neo4j is not reachable.

## Project Structure

```
src/neo4j_graphrag_kg/
  __init__.py        # Package root
  cli.py             # Typer CLI (kg command)
  config.py          # Settings from environment
  neo4j_client.py    # Singleton Neo4j driver
  schema.py          # Constraints & indexes (Neo4j 5+)
  ids.py             # Slugify + deterministic IDs
  chunker.py         # Fixed-size character chunker
  extractor.py       # Heuristic entity extractor + edge builder
  upsert.py          # Batched UNWIND MERGE operations
  ingest.py          # Ingestion pipeline orchestrator
  py.typed           # PEP 561 marker
tests/
  test_config.py              # Unit: settings
  test_ids.py                 # Unit: slugify + IDs
  test_chunker.py             # Unit: chunking
  test_extractor.py           # Unit: extraction + edges
  test_integration_ping.py    # Integration: connectivity
  test_integration_init_db.py # Integration: schema
  test_integration_ingest.py  # Integration: idempotency
examples/
  demo.txt                    # Demo content for ingestion
docs/
  DEV_NOTES.md                # Architecture + troubleshooting
  SESSION_LOG.md              # Session-by-session changelog
```

## Security

- `.env` is in `.gitignore` and `.dockerignore` — never commit secrets.
- Docker Compose requires `NEO4J_PASSWORD` to be set (auth is always enabled).
- Credentials are never logged or printed.
