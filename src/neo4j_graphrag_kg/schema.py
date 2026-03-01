"""Neo4j 5+ schema: idempotent constraints and indexes."""

from __future__ import annotations

# --- Constraints (IF NOT EXISTS) -------------------------------------------

CONSTRAINTS: list[str] = [
    (
        "CREATE CONSTRAINT document_id_unique IF NOT EXISTS "
        "FOR (d:Document) REQUIRE d.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS "
        "FOR (c:Chunk) REQUIRE c.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
        "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
    ),
]

# --- Indexes (IF NOT EXISTS) -----------------------------------------------

INDEXES: list[str] = [
    (
        "CREATE INDEX entity_name_idx IF NOT EXISTS "
        "FOR (e:Entity) ON (e.name)"
    ),
    (
        "CREATE INDEX entity_type_idx IF NOT EXISTS "
        "FOR (e:Entity) ON (e.type)"
    ),
    (
        "CREATE INDEX chunk_document_id_idx IF NOT EXISTS "
        "FOR (c:Chunk) ON (c.document_id)"
    ),
]

ALL_STATEMENTS: list[str] = CONSTRAINTS + INDEXES

# TODO: Add vector index support once LLM extraction is in place.
