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
- Synchronous web execution path can bottleneck under load.
- Re-ingest reconciliation and directionality remain the main correctness risks.

## Prior Findings Status

| Finding | Previous | Current |
|---|---|---|
| `Document.created_at` mutated on re-ingest | Open | Fixed |
| Transient Neo4j write retry missing | Open | Fixed |
| `kg query` write-safety default | Open | Fixed (`--allow-write` escape hatch) |
| Durable staged ingest job state | Planned | Implemented |
| CI with Neo4j integration service | Open | Fixed |
| Strict `mypy` and `ruff` CI gate | Open | Fixed |
| Structured RAG trust metadata | Open | Fixed |

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

1. Synchronous web path can bottleneck under load.
2. Limited structured observability around throughput and retries.

### P2

1. Remaining ingest correctness work is still higher impact than new feature expansion.
2. Web UX still surfaces trust metadata in a minimal way.

## Recommended Next Moves

1. Land directionality + reconciliation work before broader feature expansion.
2. Add setup and integrity diagnostics (`kg doctor`, `kg check`).
3. Improve the web/UI presentation of trust metadata and evidence trails.

## Tracking Docs

- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_ROADMAP.md`
- `docs/V2_GITHUB_ISSUES.md`
