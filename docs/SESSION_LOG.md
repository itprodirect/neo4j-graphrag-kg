# Session Log

Chronological build notes and status snapshots.

## Session 1: Project Bootstrap

Highlights:

- Created `src` layout package and CLI skeleton.
- Added Neo4j connectivity commands (`ping`, `init-db`, `status`).
- Added initial schema constraints/indexes and basic tests.

Status:

- Complete.

---

## Session 2: MVP Ingestion and Query

Highlights:

- Added deterministic ID generation (`ids.py`).
- Added chunking, heuristic extraction, and batched upserts.
- Added `kg ingest`, `kg query`, and `kg reset`.

Status:

- Complete.

---

## Session 3: Pluggable Extraction and LLM Support

Highlights:

- Added extractor interfaces and registry.
- Added `simple` and `llm` extractor implementations.
- Added configuration knobs for provider/model/entity typing.

Status:

- Complete.

---

## Session 4: Correctness and API Hardening

Highlights:

- Preserved relationship metadata and improved extraction interfaces.
- Added handling improvements for optional SDK imports.
- Expanded regression tests for prior bug classes.

Status:

- Complete.

---

## Session 5: GraphRAG and Web Surface

Highlights:

- Added `kg ask` orchestration (question -> Cypher -> answer).
- Added FastAPI endpoints and D3 graph explorer.
- Added safety validation for read-only Cypher generation.

Status:

- Complete.

---

## Session 6: Security and Reliability Pass

Highlights:

- Hardened CORS behavior and query safety checks.
- Added transient Neo4j write retry/backoff in upsert path.
- Added additional security-focused tests.

Status:

- Complete.

---

## Session 7: Durable Ingest Jobs and Service Boundary

Highlights:

- Added staged ingest jobs with durable Neo4j-backed job state.
- Added `kg ingest-status` and `kg ingest-run`.
- Added service container boundary and integration tests.

Status:

- Complete.

---

## Session 8: V2 Planning and Synthetic Investigation Dataset

Highlights:

- Added v2 blueprint, roadmap, and issue backlog docs.
- Added issue creation automation script.
- Added synthetic claims/fraud/E&O dataset and investigator query pack.

Status:

- Planning assets complete.
- GitHub issue creation pending valid `gh` authentication.

---

## Current Program Status (as of 2026-03-04)

- v1 foundation is functional and test-backed.
- v2 planning artifacts are committed.
- Next execution focus is v2 phase 0 and phase 1 correctness work.

Related docs:

- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_ROADMAP.md`
- `docs/V2_GITHUB_ISSUES.md`
