# V2 GitHub Issue Backlog

Issue-ready backlog for the V2 rebuild.

## Backlog Status (as of 2026-03-05)

| Item | Status |
|---|---|
| Backlog definition | Ready |
| Label + milestone + issue automation | Ready (`scripts/create-v2-issues.ps1`) |
| GitHub issue creation | Ready (requires `gh auth status` to pass) |

## Milestone and Ownership Model

- Default milestone: `V2 Rebuild`
- Sequence model: issues are prefixed `[V2-01]` .. `[V2-16]`
- Owner model: default assignee is `@me` (customizable per issue in script)
- Idempotency: script skips already-existing issue titles

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

## Create or Sync Issues

Dry run (recommended first):

```powershell
powershell -NoProfile -File scripts/create-v2-issues.ps1
```

Create labels + milestone + issues:

```powershell
powershell -NoProfile -File scripts/create-v2-issues.ps1 -Execute
```

Custom milestone name:

```powershell
powershell -NoProfile -File scripts/create-v2-issues.ps1 -Execute -Milestone "V2 Rebuild"
```

Verify V2 issues:

```powershell
gh issue list --limit 200 --label v2
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

Ship cleanly, iterate fast, keep receipts.
