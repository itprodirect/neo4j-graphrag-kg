# Investigator Query Pack

These queries are starting points after ingesting the synthetic corpus.

## 1) Entities connected to both claims

```cypher
MATCH (c1:Entity {name: "CLM-2025-1187"})
MATCH (c2:Entity {name: "CLM-2025-1219"})
MATCH p = shortestPath((c1)-[*..6]-(c2))
RETURN p
LIMIT 5
```

## 2) Potential collusion chain around Victor Hale

```cypher
MATCH p = (a:Entity {name: "Victor Hale"})-[*..4]-(b)
RETURN p
LIMIT 50
```

## 3) Find entities tied to shared bank account

```cypher
MATCH (e:Entity)
WHERE toLower(e.name) CONTAINS toLower("BA-992041")
MATCH p = (e)-[*..3]-(x)
RETURN p
LIMIT 100
```

## 4) Policy statement contradictions

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

## 5) Reused invoice identifier across documents

```cypher
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity)
WHERE e.name = "INV-77841"
RETURN d.id, d.title, left(c.text, 180) AS snippet
LIMIT 50
```

## 6) High-degree entities (ring-like hubs)

```cypher
MATCH (e:Entity)
OPTIONAL MATCH (e)-[r]-()
RETURN e.name AS entity, count(r) AS degree
ORDER BY degree DESC
LIMIT 25
```

## 7) Document timeline by risky entities

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

## 8) Typed relationship view (best with LLM extraction)

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

