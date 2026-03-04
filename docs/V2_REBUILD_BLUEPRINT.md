# V2 Rebuild Blueprint

## Purpose
This document is a ground-up rebuild plan for `neo4j-graphrag-kg` based on lessons from v1 implementation and test history.

Goals:
- Keep what is strong in v1.
- Remove architecture debt that limits scale and correctness.
- Improve end-user clarity and trust.
- Build a product that can grow from power-user CLI to reliable platform.

---

## 1) Current-State Deep Dive

### What Works Well
- Clear module boundaries for core concerns:
  - config (`config.py`)
  - database lifecycle (`neo4j_client.py`)
  - ingest (`ingest.py`)
  - extractors (`extractors/`)
  - upserts (`upsert.py`)
  - retrieval/RAG (`rag/`)
  - web surface (`web/app.py`)
- Deterministic ID strategy exists and is test-covered:
  - `slugify(name)` for entities
  - `{doc_id}::chunk::{idx}` for chunks
- Batched Neo4j writes with `UNWIND ... MERGE` are in place.
- CLI is coherent and operationally useful (`kg ingest`, `kg query`, `kg ask`, `kg serve`, job commands).
- Test suite is broad and fast:
  - `186 passed, 11 skipped` locally on 2026-03-04
- Security posture is better than typical early-stage projects:
  - read-only query validation for RAG
  - CORS restrictions
  - secret discipline in docs and examples

### What Is OK (Good Start, Not Yet Production-Strong)
- Durable ingest jobs exist, but job state stores large JSON blobs in Neo4j node properties.
- RAG pipeline works, but answer contract is not yet structured for citations and trust scoring.
- Web UI is functional for demos, but still a developer console rather than an end-user experience.
- Service container pattern exists, but boundaries are still adapter-heavy and not fully domain-first.
- CI runs tests, but integration tests are usually skipped in CI because Neo4j service is not provisioned.

### What Is Bad / Risky
- Relationship direction semantics are lost in staged extraction due endpoint sorting.
  - This breaks meaning for directional relationship types (for example `WORKS_FOR`).
- Re-ingesting changed documents can leave stale graph artifacts.
  - Upserts do not currently perform cleanup for removed chunks/mentions/edges.
- Ingest retry model is coarse.
  - Retries re-run full stage sets, but there is no artifact checkpoint store outside job node payload.
- Type quality gates are configured (`mypy strict`), but not enforced in CI and currently failing.
- Lint quality gates are not enforced in CI and currently failing.
- FastAPI request handlers call synchronous LLM/database work directly.
  - Works now, but this blocks event loop scalability under concurrent load.

### Unknowns (Need Measurement)
- Throughput at scale:
  - ingest time per MB
  - write throughput under parallel document ingest
- Query latency under larger graphs:
  - graph exploration endpoints
  - RAG query generation + execution + answer time
- Cost profile:
  - LLM extraction and answer generation cost per document/question
- User behavior:
  - which commands are most used
  - where users abandon flow

---

## 2) Rebuild Principles (If Starting Fresh)

### Non-Negotiables
- Correctness over convenience:
  - no silent semantic corruption (directionality, stale data).
- Explicit contracts:
  - typed inputs/outputs for each stage.
- Deterministic behavior:
  - replay-safe ingest with version-aware cleanup rules.
- Security-by-default:
  - least privilege, read-only defaults, auditable changes.
- UX clarity:
  - users understand what happened, why, and what to do next.

### Architectural Direction
- Keep Neo4j-first core.
- Move to clean domain interfaces with swappable adapters:
  - `DocumentStore`
  - `GraphStore`
  - `Extractor`
  - `Retriever`
  - `Answerer`
  - `JobStore`
- Separate data plane and control plane:
  - data plane: ingest/extract/upsert/query
  - control plane: job orchestration, retries, metrics, audit, policy

---

## 3) V2 Domain Model and Data Contracts

### Proposed Core Entities
- `Document`
  - immutable identity (`doc_id`)
  - current pointer to latest version
- `DocumentVersion`
  - content hash, ingest timestamp, pipeline version, source metadata
- `Chunk`
  - version-scoped, deterministic ID including `doc_id`, `version_id`, `idx`
- `Entity`
  - canonical ID + alias set + type taxonomy
- `Mention`
  - explicit relationship with provenance (chunk_id, offsets optional)
- `RelationshipAssertion`
  - directional source/target
  - relationship type
  - provenance + confidence + extractor metadata

### Why This Matters
- Enables safe re-ingest updates without stale nodes/edges.
- Preserves audit and provenance for compliance-heavy use cases.
- Supports rollbacks and reproducibility.

---

## 4) Ingestion and Extraction Rebuild

### Target Ingest Pipeline
1. Source intake and fingerprinting.
2. Parse and normalize.
3. Chunk with deterministic strategy versioning.
4. Extract entities/relations with extractor contract.
5. Validate and normalize graph records.
6. Upsert in bounded transactions.
7. Reconcile stale artifacts for same document/version policy.
8. Emit ingest report and quality metrics.

### Changes from V1
- Store stage artifacts outside single Neo4j job node payload.
  - use object files or local artifact storage for large payloads
  - keep only pointers + small summaries in Neo4j job metadata
- Keep relationship direction exactly as extracted.
- Add reconciliation mode:
  - `replace-document` (authoritative refresh)
  - `append-version` (historical lineage)
- Add deterministic ingestion report:
  - entities added/updated/unchanged
  - relationships added/updated/removed
  - chunks added/removed

---

## 5) Retrieval and AI Integration Strategy

### Where AI Adds Real Value
- LLM extraction for richer typed entities and relations.
- Text-to-Cypher for natural language access.
- Answer synthesis with strict grounding to query results.

### Where AI Should Not Be Used
- Deterministic schema migrations.
- Integrity checks.
- Access policy enforcement.
- Core graph write safety logic.

### V2 RAG Contract
- `question`
- `cypher`
- `rows`
- `answer`
- `citations` (doc/chunk/entity IDs)
- `confidence` (pipeline-level heuristic)
- `insufficient_evidence` flag

---

## 6) UX/UI Rebuild Direction

### Current UX State
- CLI: usable for technical users.
- Web UI: demo-grade graph explorer and ask box.

### V2 UX Goals
- New users can complete first ingest + first query in under 10 minutes.
- Every command returns actionable next steps.
- RAG answers always show evidence links/citations.
- UI supports investigation flow:
  - ask question
  - inspect evidence
  - traverse related graph
  - export/share query context

### Proposed UI Surfaces
- `kg doctor`
  - environment validation and fix suggestions
- `kg check`
  - graph integrity and data quality checks
- `kg ingest --report`
  - structured output (JSON/table)
- Web app v2:
  - graph canvas
  - evidence panel
  - query history
  - document/version inspector
  - ingest job monitor

---

## 7) Security and DevSecOps Blueprint

### Security Baseline
- Enforce read-only default everywhere possible.
- Add role-based command gates for destructive operations.
- Add prompt-injection defenses for RAG context handling.
- Add audit event schema:
  - who ran what
  - when
  - result and scope

### Delivery Baseline
- CI gates:
  - unit tests
  - integration tests with Neo4j service
  - ruff
  - mypy
  - security checks
- CD:
  - tagged releases
  - changelog generation
  - signed artifacts optional

---

## 8) Engineering Quality Plan

### Refactor Priorities
1. Correctness first:
   - directional relationships
   - re-ingest reconciliation
2. Interface hardening:
   - typed protocols for services and adapters
3. Observability:
   - structured logs
   - ingest and query metrics
4. UX clarity:
   - better command outputs and docs flow

### Test Strategy
- Keep fast unit tests for deterministic logic.
- Add integration tests that always run in CI with ephemeral Neo4j.
- Add golden tests:
  - ingest summaries
  - RAG citation outputs
- Add regression fixtures for prior known failure classes.

---

## 9) Metrics for Success (V2 Definition of Done)

### Product Metrics
- Time to first successful ingest: <= 10 minutes.
- Time to first trustworthy answer with citation: <= 15 minutes.
- User-reported answer trust score: >= 4/5 in pilot.

### Engineering Metrics
- CI reliability: >= 95% passing on main.
- Type-check coverage: mypy clean on `src/`.
- No known P0 correctness defects in ingest/retrieval path.
- Ingest performance target:
  - baseline docs complete within agreed SLA (to be benchmarked in Phase 0).

---

## 10) Practical Commit Strategy

Keep commits small, reviewable, and narrative:
- One concern per commit.
- Imperative subject line.
- Include scope prefix where useful:
  - `feat(ingest): ...`
  - `fix(rag): ...`
  - `docs(v2): ...`
  - `ci: ...`

Recommended size:
- 1-4 files per commit when possible.
- keep refactor-only commits separate from behavior changes.
- include tests in same commit as behavior changes.

---

## 11) Immediate Next Actions

1. Align on v2 scope and phase cut lines.
2. Approve initial GitHub issue backlog.
3. Stand up CI quality gates (`ruff`, `mypy`, Neo4j integration job).
4. Start Phase 0 spikes for:
   - relationship direction fix
   - re-ingest reconciliation design
   - citation contract design

