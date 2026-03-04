# Engineering Review Snapshot

A current-state review of the repository, updated for the latest implementation status.

## Review Date

- 2026-03-04

## Executive Summary

The repo is a strong v1 foundation for Neo4j-first GraphRAG workflows.

What is strong:

- Clear module boundaries and pragmatic CLI surface.
- Deterministic IDs and batched graph writes.
- Broad test coverage with fast local runs.
- Security posture above typical early-stage baselines.

What still needs focused work:

- Directional relationship correctness through extraction and persistence.
- Re-ingest reconciliation for changed source content.
- CI quality gate enforcement for lint/type/integration.
- Citation-rich RAG response contracts for trust and auditability.

## Status of Prior Findings

| Finding | Previous Status | Current Status |
|---|---|---|
| `Document.created_at` mutated on re-ingest | Open | Fixed |
| Transient Neo4j write retry missing | Open | Fixed |
| `kg query` write safety default | Open | Fixed (`--allow-write` escape hatch) |
| Durable staged ingest job state | Planned | Implemented |
| CI with Neo4j integration service | Open | Open |
| Strict mypy/ruff in CI | Open | Open |

## Strengths to Preserve

1. `UNWIND ... MERGE` write contract in `upsert.py`.
2. Typed extractor abstractions in `extractors/`.
3. Practical CLI workflows and operational command naming.
4. Minimal dependency footprint for core functionality.

## Risk Register (Current)

### P0

1. Directionality loss risk for typed relationships in staged extraction path.
2. Re-ingest of changed documents may leave stale artifacts.

### P1

1. Missing hard CI gate on lint and type checks.
2. Integration tests not consistently exercised in CI runtime.
3. Web/API request handlers can block under heavier concurrent load.

### P2

1. Limited observability around throughput and retry behavior.
2. RAG response lacks structured citations/confidence output.

## Recommended Next Moves

1. Execute v2 phase 0 and phase 1 backlog.
2. Add reconciliation mode and relationship direction regression tests first.
3. Enforce CI gates (`ruff`, `mypy`, Neo4j-backed integration job).
4. Upgrade RAG answer contract with citations and insufficiency signaling.

## Tracking References

- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_ROADMAP.md`
- `docs/V2_GITHUB_ISSUES.md`
