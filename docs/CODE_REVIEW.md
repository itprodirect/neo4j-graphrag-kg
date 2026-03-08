# Engineering Review Snapshot

Current-state review for maintainers.

## Review Date

- 2026-03-08

## Executive Summary

The repo is a strong v1 base for Neo4j-first GraphRAG.

Strengths:

- Clear module boundaries and practical CLI surface.
- Deterministic IDs and batched write patterns.
- Broad test suite with quick local feedback.
- Security defaults ahead of many early-stage projects.

Priority gaps:

- Relationship direction correctness in staged extraction writes.
- Re-ingest reconciliation for changed source content.
- Neo4j integration execution in CI.
- Citation-rich RAG output contracts for trust and auditability.

## Prior Findings Status

| Finding | Previous | Current |
|---|---|---|
| `Document.created_at` mutated on re-ingest | Open | Fixed |
| Transient Neo4j write retry missing | Open | Fixed |
| `kg query` write-safety default | Open | Fixed (`--allow-write` escape hatch) |
| Durable staged ingest job state | Planned | Implemented |
| CI with Neo4j integration service | Open | Open |
| Strict `mypy` and `ruff` CI gate | Open | Fixed |

## Strengths to Preserve

1. `UNWIND ... MERGE` write contract in `upsert.py`.
2. Extractor abstractions in `extractors/`.
3. CLI ergonomics and operational command naming.
4. Minimal core dependency strategy.

## Risk Register

### P0

1. Potential directionality loss for typed relationships.
2. Potential stale graph artifacts after changed-source re-ingest.

### P1

1. Neo4j integration tests not consistently run in CI.
2. Synchronous web path can bottleneck under load.

### P2

1. Limited structured observability around throughput/retries.
2. RAG output lacks structured citation/confidence fields.

## Recommended Next Moves

1. Execute phase 0 and phase 1 v2 backlog items.
2. Land directionality + reconciliation work before broader feature expansion.
3. Add Neo4j service-backed integration coverage in CI.
4. Upgrade RAG contract to include evidence and insufficiency signaling.

## Tracking Docs

- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_ROADMAP.md`
- `docs/V2_GITHUB_ISSUES.md`
