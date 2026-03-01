# Developer Notes

## Architecture Overview

```
┌──────────┐     ┌─────────┐     ┌───────────┐     ┌──────────┐
│ Text File│────▶│ Chunker │────▶│ Extractor │────▶│  Upsert  │──▶ Neo4j
└──────────┘     └─────────┘     └───────────┘     └──────────┘
                  ~1000 chars     entities +         UNWIND $rows
                  150 overlap     co-occurrence       MERGE ...
```

**Pipeline stages** (all orchestrated in `ingest.py`):

1. **Read** — UTF-8 text file.
2. **Chunk** — fixed-size character chunks (default 1000 chars, 150 overlap).
3. **Extract** — heuristic entity extraction (capitalised phrases + known terms).
4. **Edges** — co-occurrence within the same chunk → `RELATED_TO`.
5. **Upsert** — batched UNWIND MERGE into Neo4j.

## ID Rules

| Type     | Formula                          | Example                |
|----------|----------------------------------|------------------------|
| Entity   | `slugify(name)`                  | `knowledge-graph`      |
| Chunk    | `"{doc_id}::chunk::{idx}"`       | `demo::chunk::0`       |
| Document | User-supplied `--doc-id`         | `demo`                 |

- **slugify**: NFKD normalise → lowercase → strip punctuation → collapse whitespace to hyphens.
- Entity IDs are deterministic so the same entity from different documents merges.
- Chunk IDs include the doc_id so chunks are scoped to their document.

## UNWIND Batching Rule

**All Neo4j writes** use the pattern:

```cypher
UNWIND $rows AS row
MERGE (n:Label {id: row.id})
SET n.prop = row.prop
```

inside an **explicit transaction** (`session.begin_transaction()`).

Never call single-row MERGE in a Python for-loop.  Batch size default: 500.

## Graph Model

```
(:Document {id, title, source, created_at})
  -[:HAS_CHUNK]->
(:Chunk {id, document_id, idx, text})
  -[:MENTIONS]->
(:Entity {id, name, type})
  -[:RELATED_TO {doc_id, chunk_id, extractor, confidence, evidence}]->
(:Entity)
```

Constraints (Neo4j 5+ `IF NOT EXISTS`):
- `Document.id` UNIQUE
- `Chunk.id` UNIQUE
- `Entity.id` UNIQUE

Indexes:
- `Entity.name`
- `Entity.type`
- `Chunk.document_id`

## Troubleshooting

### Auth errors

Make sure `.env` has `NEO4J_PASSWORD` matching the password used in
`docker compose up`.  Neo4j requires a password change on first run;
the compose file sets the initial password.

### Volume issues

Data persists in Docker volumes `neo4j_data` and `neo4j_logs`.
To start completely fresh:

```bash
docker compose down -v   # removes volumes
docker compose up -d
```

### Port conflicts

Default ports: 7474 (HTTP browser), 7687 (Bolt).
Change in `docker-compose.yml` if they clash.

### "No module named neo4j_graphrag_kg"

Ensure you installed in editable mode:

```bash
pip install -e ".[dev]"
```
