#!/usr/bin/env bash
set -euo pipefail

echo "[smoke] Starting Neo4j..."
docker compose up -d

echo "[smoke] Checking connectivity..."
kg ping

echo "[smoke] Initializing schema..."
kg init-db

echo "[smoke] Ingesting demo document..."
kg ingest --input examples/demo.txt --doc-id demo --title "Demo"

echo "[smoke] Running read-only query..."
python - <<'PY'
from neo4j_graphrag_kg.config import get_settings
from neo4j_graphrag_kg.neo4j_client import close_driver, get_driver

settings = get_settings()
driver = get_driver(settings)
try:
    with driver.session(database=settings.neo4j_database) as session:
        row = session.run("MATCH (e:Entity) RETURN e.id AS id LIMIT 1").single()
    if row is None:
        raise SystemExit("Smoke check failed: query returned no rows.")
    print(f"[smoke] Query OK. Found entity id={row['id']}")
finally:
    close_driver()
PY

echo "[smoke] Success. Neo4j Browser: http://localhost:7474"
