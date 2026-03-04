# V2 GitHub Issue Backlog

Issue-ready backlog for the v2 rebuild.

## Backlog Status (as of 2026-03-04)

| Item | Status |
|---|---|
| Backlog draft | Ready |
| Label + issue script | Ready (`scripts/create-v2-issues.ps1`) |
| GitHub issue creation | Pending valid `gh` authentication |

## Label Set

- `v2`
- `phase:1-correctness`
- `phase:2-platform`
- `phase:3-rag`
- `phase:4-ux`
- `phase:5-devsecops`
- `type:feature`
- `type:refactor`
- `type:security`
- `type:docs`
- `priority:p0`
- `priority:p1`
- `priority:p2`

---

## P0 Foundation Issues

1. Preserve relationship direction in extraction to graph write.
2. Add document versioning and source hash model.
3. Implement replace-document reconciliation for re-ingest.
4. Upgrade RAG response contract with citations and confidence.
5. Expand Cypher safety policy and high-risk query blocking.
6. Enforce CI gates for lint, typing, and Neo4j integration jobs.

## P1 Execution Issues

1. Add deterministic ingest report contract.
2. Externalize large ingest artifacts from job node payload.
3. Define stable domain protocols for stores and retrievers.
4. Add `kg check` integrity diagnostics.
5. Build retrieval and answer evaluation harness.
6. Add `kg doctor` onboarding diagnostics.
7. Redesign web UI for investigator workflow.
8. Define release and versioning policy.

## P2 Enhancements

1. Add structured telemetry for ingest/query/rag.
2. Ship synthetic investigation demo walkthrough polish.

---

## Issue Template Pattern

For each issue, include:

- Problem statement
- Scope boundaries
- Acceptance criteria
- Test plan
- Rollout or migration notes

## Create Issues Automatically

Dry run:

```powershell
powershell -NoProfile -File scripts/create-v2-issues.ps1
```

Execute:

```powershell
powershell -NoProfile -File scripts/create-v2-issues.ps1 -Execute
```

If auth fails:

```powershell
gh auth login -h github.com
```

---

## Source Links

- `docs/V2_REBUILD_BLUEPRINT.md`
- `docs/V2_ROADMAP.md`
- `scripts/create-v2-issues.ps1`

Simple plan, clean execution, useful software.
