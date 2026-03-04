# V2 Rebuild Blueprint

Ground-up v2 direction based on v1 lessons.

## Blueprint Status (as of 2026-03-04)

| Item | Status |
|---|---|
| Planning quality | Ready for execution |
| Core refactor execution | Not started |
| Phase source of truth | `docs/V2_ROADMAP.md` |
| Backlog source of truth | `docs/V2_GITHUB_ISSUES.md` |

## Purpose

Goals:

- Preserve what already works.
- Remove correctness and scalability debt.
- Improve trust, clarity, and operational reliability.
- Use AI where it materially helps and avoid it where deterministic systems win.

---

## 1) Current-State Deep Dive

### What Works Well

- Clear boundaries for config, ingest, extraction, persistence, RAG, and web.
- Deterministic IDs and batched graph write patterns.
- Practical CLI workflows.
- Strong baseline security defaults.
- Fast local test feedback loops.

### What Is OK

- Durable ingest jobs exist, but payload strategy can be improved.
- RAG works, but trust signals and citations need stronger contracts.
- Web UI is useful for demos, not yet for full investigation workflows.
- Service boundaries exist, but protocol-level contracts are still maturing.

### What Is Bad or Risky

- Relationship direction can be lost in staged extraction flow.
- Changed-source re-ingest can leave stale graph artifacts.
- CI does not yet enforce full quality gates.
- Synchronous web-path operations can bottleneck under concurrent load.

### What Is Unknown

- Throughput and latency at larger graph scale.
- LLM cost profile under realistic usage.
- User flow completion/failure points in onboarding and investigation paths.

---

## 2) Rebuild Principles

### Non-Negotiables

- Correctness over convenience.
- Explicit typed contracts across stage boundaries.
- Deterministic, replay-safe behavior.
- Security by default.
- UX that explains outcomes and next steps clearly.

### Architecture Direction

- Keep Neo4j central.
- Standardize service protocols:
  - `GraphStore`
  - `JobStore`
  - `Extractor`
  - `Retriever`
  - `Answerer`
- Keep data-plane and control-plane responsibilities separate.

---

## 3) V2 Data Contract Direction

Target entities:

- `Document`
- `DocumentVersion`
- `Chunk`
- `Entity`
- `Mention`
- `RelationshipAssertion`

Expected outcomes:

- Safe changed-source re-ingest behavior.
- Improved provenance and auditability.
- Better reproducibility and rollback options.

---

## 4) Ingestion and Extraction Rebuild

Target pipeline:

1. Source intake and fingerprinting.
2. Parse and normalize.
3. Version-aware chunking.
4. Extraction with typed contracts.
5. Record validation and normalization.
6. Bounded transactional upsert.
7. Reconciliation by mode.
8. Structured ingest reporting.

Key v2 changes:

- Preserve relationship direction end-to-end.
- Add reconciliation modes (`replace-document`, `append-version`).
- Externalize large stage artifacts from job node payload.
- Emit deterministic ingest delta summaries.

---

## 5) AI Integration Strategy

AI should be used for:

- Semantic extraction tasks.
- Text-to-Cypher translation with guardrails.
- Grounded answer synthesis.

AI should not be used for:

- Deterministic schema migration logic.
- Security policy enforcement.
- Integrity checks.

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

- CLI is strong for technical users.
- Web UI is a useful explorer but not yet a full investigation workspace.

V2 goals:

- first ingest + first useful answer in under 10 minutes.
- Evidence links by default in RAG answers.
- Better investigation workflow in the web app.

---

## 7) Security and DevSecOps Direction

Security baseline:

- Read-only defaults.
- Explicit destructive-command gates.
- Prompt-injection-resistant handling.
- Audit event schema.

Delivery baseline:

- CI gates for tests, lint, typing, integration.
- Repeatable release flow with changelog and versioning policy.

---

## 8) Engineering Quality Plan

Refactor priorities:

1. Correctness: directionality + reconciliation.
2. Interface quality: typed protocols and stable contracts.
3. Observability: structured logs and metrics.
4. UX clarity: actionable output and diagnostics.

---

## 9) Success Metrics

Product outcomes:

- First successful ingest in under 10 minutes.
- First citation-backed answer in under 15 minutes.

Engineering outcomes:

- CI reliability above 95% on main.
- Clean typing on `src` and stable lint gate.
- No known P0 correctness defects in ingest/retrieval path.

---

## 10) Commit Strategy

- One concern per commit.
- Include tests with behavior changes.
- Keep refactor-only commits separate from behavior-changing commits.

Examples:

- `feat(ingest): add replace-document reconciliation mode`
- `fix(extractor): preserve relationship direction across stages`
- `ci: enforce ruff and mypy gates`

---

## 11) Immediate Next Actions

1. Start phase 0 baseline and architecture decision records.
2. Begin phase 1 correctness work.
3. Create and triage issues from backlog doc.
4. Enforce CI gates before wide v2 refactor rollout.

If this looks too serious, good. If it works, even better.
