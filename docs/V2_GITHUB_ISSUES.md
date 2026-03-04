# V2 GitHub Issue Backlog

These are issue-ready cards for a v2 rebuild program.

Label convention:
- `v2`
- `phase:*` (for example `phase:1-correctness`)
- `type:*` (`type:feature`, `type:refactor`, `type:security`, `type:docs`)
- `priority:*` (`priority:p0`, `priority:p1`, `priority:p2`)

---

## 1) V2: Preserve relationship direction in extraction -> graph write

Labels:
`v2`, `phase:1-correctness`, `type:feature`, `priority:p0`

Acceptance Criteria:
- LLM and simple extraction paths keep source/target direction unchanged.
- No alphabetical endpoint reordering in pipeline.
- Regression tests cover `WORKS_FOR` and inverse cases.

---

## 2) V2: Add document versioning and source hash model

Labels:
`v2`, `phase:1-correctness`, `type:feature`, `priority:p0`

Acceptance Criteria:
- `DocumentVersion` entity introduced with content hash.
- Ingest writes are version-scoped.
- Existing queries remain backward compatible where possible.

---

## 3) V2: Implement re-ingest reconciliation mode (`replace-document`)

Labels:
`v2`, `phase:1-correctness`, `type:feature`, `priority:p0`

Acceptance Criteria:
- Re-ingest of changed content removes stale chunks/mentions/relationships.
- Command flag/config for reconciliation mode documented.
- Integration tests validate non-stale final graph.

---

## 4) V2: Add ingest result contract with add/update/remove counters

Labels:
`v2`, `phase:1-correctness`, `type:feature`, `priority:p1`

Acceptance Criteria:
- `kg ingest` outputs deterministic summary counters.
- JSON output mode available for automation.
- Summary includes pipeline version and timings.

---

## 5) V2: Externalize large stage artifacts from Neo4j job nodes

Labels:
`v2`, `phase:2-platform`, `type:refactor`, `priority:p1`

Acceptance Criteria:
- `IngestJob` stores metadata and pointers only.
- Artifact payload size in Neo4j remains bounded.
- Resume logic works from stored artifact references.

---

## 6) V2: Define stable domain protocols (GraphStore, JobStore, Retriever)

Labels:
`v2`, `phase:2-platform`, `type:refactor`, `priority:p1`

Acceptance Criteria:
- Protocols/interfaces defined with typed contracts.
- CLI and web use service layer, not direct infra calls.
- Public API surface documented.

---

## 7) V2: Add `kg check` integrity diagnostics command

Labels:
`v2`, `phase:2-platform`, `type:feature`, `priority:p1`

Acceptance Criteria:
- Checks for orphan chunks/mentions, duplicate risk signals, null key fields.
- Exit code and JSON output suitable for CI automation.
- Docs include remediation guide.

---

## 8) V2: Structured telemetry for ingest/query/rag

Labels:
`v2`, `phase:2-platform`, `type:feature`, `priority:p2`

Acceptance Criteria:
- Structured log events with stable schema.
- Metrics include tx counts, retries, latency, row counts.
- Sensitive fields redacted by default.

---

## 9) V2: RAG response contract with citations and confidence

Labels:
`v2`, `phase:3-rag`, `type:feature`, `priority:p0`

Acceptance Criteria:
- Response includes `citations`, `insufficient_evidence`, and confidence signal.
- CLI and API surfaces display citation references.
- Tests verify contract stability.

---

## 10) V2: Expand Cypher safety policy and high-risk query blocking

Labels:
`v2`, `phase:3-rag`, `type:security`, `priority:p0`

Acceptance Criteria:
- Guardrails cover high-risk procedure patterns and heavy unbounded scans.
- Safe failure responses are user-readable and non-leaky.
- Security tests include bypass attempts.

---

## 11) V2: Build evaluation harness for retrieval and answer quality

Labels:
`v2`, `phase:3-rag`, `type:feature`, `priority:p1`

Acceptance Criteria:
- Gold question set and expected evidence references stored in repo.
- Evaluation script outputs precision/recall style metrics.
- Baseline report checked into docs.

---

## 12) V2: Add `kg doctor` onboarding and environment diagnostics

Labels:
`v2`, `phase:4-ux`, `type:feature`, `priority:p1`

Acceptance Criteria:
- Validates env vars, Neo4j reachability, optional SDK presence.
- Provides actionable fixes for each failure.
- Referenced in README quickstart.

---

## 13) V2: Redesign web UI for investigator workflow

Labels:
`v2`, `phase:4-ux`, `type:feature`, `priority:p1`

Acceptance Criteria:
- Graph canvas + evidence panel + query history implemented.
- Responsive layout works on desktop and mobile.
- Node and relationship drill-down shows provenance clearly.

---

## 14) V2: Add synthetic investigation demo pack and walkthrough

Labels:
`v2`, `phase:4-ux`, `type:docs`, `priority:p2`

Acceptance Criteria:
- Synthetic corpus and query walkthrough integrated in docs.
- Demo script ingests and validates expected signals.
- No real PII or sensitive real-world data included.

---

## 15) V2: CI quality gates for ruff, mypy, and Neo4j integration job

Labels:
`v2`, `phase:5-devsecops`, `type:feature`, `priority:p0`

Acceptance Criteria:
- CI fails on lint/type errors.
- Integration tests run against ephemeral Neo4j service in CI.
- Required checks enabled for protected branch.

---

## 16) V2: Release and versioning policy for stable public interfaces

Labels:
`v2`, `phase:5-devsecops`, `type:docs`, `priority:p1`

Acceptance Criteria:
- Semantic versioning policy documented.
- Breaking-change guidance and deprecation windows defined.
- Changelog and release checklist added.

