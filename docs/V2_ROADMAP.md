# V2 Roadmap

This roadmap translates the v2 blueprint into execution phases with clear exit criteria.

## Phase 0: Baseline and Decisions (1-2 weeks)

Outcomes:
- Lock v2 architecture boundaries and domain contracts.
- Benchmark v1 ingest and query baseline.
- Decide re-ingest policy (`replace-document` vs `append-version`).

Exit Criteria:
- Architecture decision record set approved.
- Baseline metrics captured in repo docs.
- Backlog triaged with priorities and owners.

## Phase 1: Correctness Core (2-3 weeks)

Outcomes:
- Preserve relationship direction end-to-end.
- Add document versioning + reconciliation for stale artifacts.
- Add deterministic ingest report with add/update/remove counts.

Exit Criteria:
- No known semantic directionality bugs.
- Re-ingest of changed source does not leave stale graph state in `replace-document` mode.
- New regression tests added and passing.

## Phase 2: Platform Contracts and Observability (2 weeks)

Outcomes:
- Introduce stable protocols for stores/extractors/retrievers.
- Emit structured ingest and query telemetry.
- Add `kg check` integrity command and machine-readable output.

Exit Criteria:
- Public service interfaces documented and type-checked.
- Integrity command available in CLI.
- Metrics visible in logs with stable field names.

## Phase 3: Trustworthy GraphRAG (2-3 weeks)

Outcomes:
- RAG response contract upgraded with citations and confidence fields.
- Prompt-injection and query-risk guardrails expanded.
- Evaluation harness for Q/A and retrieval quality.

Exit Criteria:
- `kg ask` and `/api/ask` return citation-aware response objects.
- Query safety tests cover high-risk patterns.
- Baseline evaluation report published.

## Phase 4: UX and Product Surface (2-3 weeks)

Outcomes:
- CLI onboarding improvements (`kg doctor`, actionable hints).
- Web app redesign for investigation workflow.
- Synthetic investigation demos integrated into docs.

Exit Criteria:
- New users can complete first ingest and first evidence-backed answer in <= 10 minutes.
- Web UI supports evidence drill-down and query history.

## Phase 5: DevSecOps Hardening and Release (1-2 weeks)

Outcomes:
- CI enforces lint, type-check, and Neo4j integration tests.
- Release pipeline with versioning policy and changelog generation.
- Security checklist and incident playbooks documented.

Exit Criteria:
- Main branch protected by quality gates.
- v2.0.0 release candidate passes full test matrix.
- Operational runbook completed.

---

## Delivery Rhythm

- Weekly architecture + risk review.
- Bi-weekly milestone demo.
- Daily small commits with descriptive messages and test evidence.

## Suggested Milestone Tags

- `v2-phase-0`
- `v2-phase-1`
- `v2-phase-2`
- `v2-phase-3`
- `v2-phase-4`
- `v2-phase-5`

