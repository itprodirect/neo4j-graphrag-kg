# V2 Roadmap

Phased execution plan for rebuilding the project on top of v1 lessons.

## Roadmap Status (as of 2026-03-04)

| Phase | Focus | Status |
|---|---|---|
| Phase 0 | Baseline and architecture decisions | Planned |
| Phase 1 | Correctness core | Planned |
| Phase 2 | Contracts and observability | Planned |
| Phase 3 | Trustworthy GraphRAG | Planned |
| Phase 4 | UX and product surface | Planned |
| Phase 5 | DevSecOps hardening and release | Planned |

## Phase 0: Baseline and Decisions (1-2 weeks)

Outcomes:

- Lock domain contracts and adapter boundaries.
- Record baseline ingest/query metrics.
- Finalize re-ingest policy decisions.

Exit criteria:

- Architecture decisions documented.
- Baseline benchmark notes committed.
- Backlog triaged and sequenced.

## Phase 1: Correctness Core (2-3 weeks)

Outcomes:

- Preserve relationship direction from extraction to persistence.
- Implement document versioning and reconciliation mode.
- Emit deterministic ingest delta reports.

Exit criteria:

- Directionality regression tests pass.
- Changed-source re-ingest leaves no stale graph artifacts in replace mode.
- Summary contracts documented and tested.

## Phase 2: Platform Contracts and Observability (2 weeks)

Outcomes:

- Introduce typed service protocols.
- Add `kg check` integrity diagnostics.
- Add structured ingest/query telemetry.

Exit criteria:

- Protocol interfaces are documented and type-checked.
- Integrity diagnostics command is usable in CI automation.
- Metrics fields are stable and documented.

## Phase 3: Trustworthy GraphRAG (2-3 weeks)

Outcomes:

- Add citation-rich RAG response contract.
- Expand Cypher safety and prompt-injection guardrails.
- Build evaluation harness for retrieval and answer quality.

Exit criteria:

- API and CLI return citation-aware responses.
- Guardrail tests cover high-risk query patterns.
- Baseline evaluation report committed.

## Phase 4: UX and Product Surface (2-3 weeks)

Outcomes:

- Improve onboarding and diagnostics (`kg doctor`).
- Redesign web UI for investigation workflows.
- Integrate synthetic walkthroughs into user docs.

Exit criteria:

- New users complete first useful flow in under 10 minutes.
- UI supports answer-to-evidence drill-down.

## Phase 5: DevSecOps Hardening and Release (1-2 weeks)

Outcomes:

- Enforce CI gates for tests, lint, and typing.
- Run Neo4j integration tests in CI services.
- Publish release and versioning policy.

Exit criteria:

- Required checks protect main branch.
- v2 release candidate passes full pipeline.
- Runbook and release checklist are complete.

---

## Delivery Rhythm

- Weekly architecture and risk review.
- Bi-weekly milestone demo.
- Daily small, descriptive commits.

## Suggested Milestones

- `v2-phase-0`
- `v2-phase-1`
- `v2-phase-2`
- `v2-phase-3`
- `v2-phase-4`
- `v2-phase-5`

## Backlog Reference

Use `docs/V2_GITHUB_ISSUES.md` as the issue source file.
