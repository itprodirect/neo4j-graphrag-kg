# Session Log

Chronological build log and program status snapshots.

## Session Timeline

| Session | Focus | Status |
|---|---|---|
| 1 | Project bootstrap and basic CLI | Complete |
| 2 | MVP ingest/query/reset pipeline | Complete |
| 3 | Pluggable extraction and LLM support | Complete |
| 4 | Correctness and API hardening | Complete |
| 5 | GraphRAG and web surface | Complete |
| 6 | Security and reliability pass | Complete |
| 7 | Durable ingest jobs and service boundary | Complete |
| 8 | V2 planning + synthetic investigation dataset | Complete |

---

## Session 1: Project Bootstrap

Highlights:

- Created `src` layout package and CLI skeleton.
- Added Neo4j connectivity commands (`ping`, `init-db`, `status`).
- Added initial schema constraints/indexes and basic tests.

## Session 2: MVP Ingestion and Query

Highlights:

- Added deterministic IDs (`ids.py`).
- Added chunking, heuristic extraction, batched upserts.
- Added `kg ingest`, `kg query`, `kg reset`.

## Session 3: Pluggable Extraction and LLM Support

Highlights:

- Added extractor interfaces and registry.
- Added `simple` and `llm` extractors.
- Added provider/model/entity typing config controls.

## Session 4: Correctness and API Hardening

Highlights:

- Improved extraction interface consistency.
- Improved optional SDK handling.
- Expanded regression coverage for known bug classes.

## Session 5: GraphRAG and Web Surface

Highlights:

- Added `kg ask` orchestration.
- Added FastAPI endpoints and D3 graph UI.
- Added read-only Cypher validation in query pipeline.

## Session 6: Security and Reliability Pass

Highlights:

- Hardened CORS and query safety checks.
- Added transient write retry/backoff in upsert path.
- Added security-focused tests.

## Session 7: Durable Ingest Jobs and Service Boundary

Highlights:

- Added staged ingest jobs with durable Neo4j-backed job state.
- Added `kg ingest-status` and `kg ingest-run`.
- Added service container boundary and integration coverage.

## Session 8: V2 Planning and Synthetic Investigation Dataset

Highlights:

- Added v2 blueprint, roadmap, and issue backlog docs.
- Added issue-creation automation script.
- Added synthetic claims/fraud/E&O dataset and query pack.

Notes:

- GitHub issue creation is pending valid `gh` authentication.

---

## Current Program Status (as of 2026-03-04)

- v1 foundation: stable and test-backed.
- v2 planning assets: complete.
- next execution target: phase 0 and phase 1 correctness items.

Related:

- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_ROADMAP.md`
- `docs/V2_GITHUB_ISSUES.md`
