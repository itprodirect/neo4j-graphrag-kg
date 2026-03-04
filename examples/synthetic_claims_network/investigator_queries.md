# Investigator Query Pack

Starter Cypher queries for the synthetic claims network dataset.

## Query Pack Status (as of 2026-03-04)

- Optimized for readability over micro-optimizations.
- Safe defaults include explicit `LIMIT` clauses.
- Intended for investigation demos and exploratory analysis.

## 1) Entities Connected to Both Claims

```cypher
MATCH (c1:Entity {name: "CLM-2025-1187"})
MATCH (c2:Entity {name: "CLM-2025-1219"})
MATCH p = shortestPath((c1)-[*..6]-(c2))
RETURN p
LIMIT 5
```

## 2) Potential Collusion Chain Around Victor Hale

```cypher
MATCH p = (a:Entity {name: "Victor Hale"})-[*..4]-(b)
RETURN p
LIMIT 50
```

## 3) Entities Tied to Shared Bank Account

```cypher
MATCH (e:Entity)
WHERE toLower(e.name) CONTAINS toLower("BA-992041")
MATCH p = (e)-[*..3]-(x)
RETURN p
LIMIT 100
```

## 4) Policy Statement Contradictions

```cypher
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
WHERE e.name IN [
  "CLM-2023-4410",
  "HexaSol",
  "Plant 14",
  "Plant 9",
  "Maya Trent"
]
RETURN d.id AS doc_id, d.title AS title, e.name AS signal, left(c.text, 220) AS evidence
ORDER BY d.id, e.name
LIMIT 200
```

## 5) Reused Invoice Identifier Across Documents

```cypher
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
WHERE e.name = "INV-77841"
RETURN d.id, d.title, left(c.text, 180) AS snippet
LIMIT 50
```

## 6) High-Degree Entities (Ring-Like Hubs)

```cypher
MATCH (e:Entity)
OPTIONAL MATCH (e)-[r]-()
RETURN e.name AS entity, count(r) AS degree
ORDER BY degree DESC
LIMIT 25
```

## 7) Timeline View of Risky Entities

```cypher
MATCH (d:Document)-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->(e:Entity)
WHERE e.name IN [
  "Darren Pike",
  "Victor Hale",
  "Lighthouse Advisory LLC",
  "Apex Restoration Group",
  "Pinnacle Emergency Services"
]
RETURN d.id, d.title, collect(DISTINCT e.name) AS linked_entities
ORDER BY d.id
LIMIT 100
```

## 8) Typed Relationship View (Best with LLM Extraction)

```cypher
MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)
WHERE r.type IN [
  "WORKS_FOR",
  "PART_OF",
  "USES",
  "RELATED_TO"
]
RETURN a.name, r.type, b.name, r.confidence, left(r.evidence, 120) AS evidence
ORDER BY r.confidence DESC
LIMIT 100
```

## Optional Next Query

If you want a quick executive summary for demos:

```cypher
MATCH (e:Entity)
OPTIONAL MATCH (e)-[r]-()
RETURN e.name AS entity, count(r) AS links
ORDER BY links DESC
LIMIT 10
```
