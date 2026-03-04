# V2 Rebuild Blueprint

## Blueprint Status (as of 2026-03-04)

- Planning quality: complete enough to execute.
- Execution status: not started for core refactors.
- Source of truth for phases: `docs/V2_ROADMAP.md`.
- Source of truth for backlog: `docs/V2_GITHUB_ISSUES.md`.

## Purpose

This document defines the ground-up v2 direction using lessons from v1.

Goals:

- Preserve what already works.
- Remove correctness and scalability debt.
- Improve user trust, clarity, and operational reliability.
- Keep AI where it adds value and avoid it where deterministic systems are better.

---

## 1) Current-State Deep Dive

### What Works Well

- Clear module boundaries for config, ingest, extraction, persistence, RAG, and web.
- Deterministic IDs and batched graph write patterns.
- Practical command-line workflows.
- Security defaults that are better than average at this stage.
- Fast and broad local test suite coverage.

### What Is OK (Good Start, Not Yet Production-Strong)

- Durable ingest jobs exist, but state payload strategy should be refined.
- RAG works, but trust signals and citations need stronger contracts.
- Web UI is useful for demos, not yet ideal for investigations at scale.
- Service boundaries exist, but interfaces are not fully protocolized.

### What Is Bad / Risky

- Relationship direction can be lost in staged extraction flow.
- Changed-source re-ingest can leave stale graph artifacts.
- CI does not yet enforce full quality gates.
- Synchronous web-path operations can become a bottleneck under load.

### What Is Unknown (Needs Measurement)

- Throughput and latency under realistic production data volume.
- LLM cost profile for extraction and answer generation.
- User flow drop-off points and task completion times.

---

## 2) Rebuild Principles

### Non-Negotiables

- Correctness over convenience.
- Explicit typed contracts at stage boundaries.
- Deterministic and replay-safe behavior.
- Security by default.
- UX that explains what happened and what to do next.

### Architectural Direction

- Keep Neo4j at the center.
- Standardize service protocols:
  - `GraphStore`
  - `JobStore`
  - `Extractor`
  - `Retriever`
  - `Answerer`
- Separate data plane and control plane concerns.

---

## 3) V2 Data Contract Direction

Target entities:

- `Document`
- `DocumentVersion`
- `Chunk`
- `Entity`
- `Mention`
- `RelationshipAssertion`

Contract outcomes:

- Safer re-ingest behavior.
- Better provenance and auditability.
- Easier rollback and reproducibility.

---

## 4) Ingestion and Extraction Rebuild

Target pipeline:

1. Source intake and fingerprinting.
2. Parse and normalize.
3. Version-aware chunking.
4. Extraction with typed contracts.
5. Record validation and normalization.
6. Bounded transactional upsert.
7. Reconciliation strategy by mode.
8. Structured ingest report emission.

Key changes from v1:

- Keep relationship direction intact.
- Add reconciliation modes (`replace-document`, `append-version`).
- Externalize large stage artifacts from job node payload.
- Emit deterministic delta summaries.

---

## 5) AI Integration Strategy

AI should be used for:

- Entity and relationship extraction where semantic interpretation matters.
- Text-to-Cypher translation with guardrails.
- Grounded answer synthesis.

AI should not be used for:

- Deterministic schema migration logic.
- Security policy enforcement.
- Integrity checks and hard validation.

Target RAG response contract:

- `question`
- `cypher`
- `rows`
- `answer`
- `citations`
- `confidence`
- `insufficient_evidence`

---

## 6) UX and Product Direction

Current state:

- CLI: strong for technical users.
- Web UI: functional explorer, not yet full investigation workspace.

V2 UX goals:

- First ingest + first useful answer in under 10 minutes.
- Evidence links by default for RAG answers.
- Better investigation workflow in web UI (history, evidence panel, graph traversal).

---

## 7) Security and DevSecOps Direction

Security baseline:

- Read-only defaults.
- Explicit destructive command gates.
- Prompt-injection-resistant handling.
- Audit event schema.

Delivery baseline:

- CI gates for tests, lint, typing, and integration.
- Repeatable release process with changelog and versioning policy.

---

## 8) Engineering Quality Plan

Refactor priorities:

1. Correctness: directionality and re-ingest reconciliation.
2. Interface quality: typed protocols and stable contracts.
3. Observability: structured logs and metrics.
4. UX clarity: actionable output and diagnostics.

---

## 9) Success Metrics

Product outcomes:

- First successful ingest within 10 minutes.
- First citation-backed answer within 15 minutes.

Engineering outcomes:

- CI reliability above 95% on main.
- Clean typing on `src` and stable lint gate.
- No known P0 correctness defects in ingest/retrieval path.

---

## 10) Commit Strategy

Use simple, descriptive commits:

- One concern per commit.
- Include tests with behavior changes.
- Keep refactor-only commits separate from feature changes.

Examples:

- `feat(ingest): add replace-document reconciliation mode`
- `fix(extractor): preserve relationship direction across stages`
- `ci: enforce ruff and mypy gates`

---

## 11) Immediate Next Actions

1. Start phase 0 baseline and architecture decision records.
2. Begin phase 1 correctness work items.
3. Create and triage GitHub issues from backlog doc.
4. Set CI gates before broad v2 refactor work lands.
