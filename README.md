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

## CLI Commands

| Command      | Description                                  |
|--------------|----------------------------------------------|
| `kg ping`    | Verify Neo4j connectivity                    |
| `kg init-db` | Create constraints & indexes (idempotent)    |
| `kg status`  | Show Neo4j version, counts, and constraints  |

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
  py.typed           # PEP 561 marker
tests/
  test_config.py              # Unit tests
  test_integration_ping.py    # Integration (skip if no Neo4j)
  test_integration_init_db.py # Integration (skip if no Neo4j)
```

## Security

- `.env` is in `.gitignore` and `.dockerignore` — never commit secrets.
- Docker Compose requires `NEO4J_PASSWORD` to be set (auth is always enabled).
- Credentials are never logged or printed.
