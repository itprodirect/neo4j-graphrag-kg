param(
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

function Ensure-GhAuth {
    $null = & gh auth status 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI auth is invalid. Run 'gh auth login -h github.com' first."
    }
}

function Ensure-Label {
    param(
        [string]$Name,
        [string]$Color,
        [string]$Description
    )

    & gh label create $Name --color $Color --description $Description 2>$null
    if ($LASTEXITCODE -ne 0) {
        # Label probably already exists. That is fine.
        $global:LASTEXITCODE = 0
    }
}

function New-Issue {
    param(
        [hashtable]$Issue
    )

    $tmp = New-TemporaryFile
    try {
        Set-Content -LiteralPath $tmp -Value $Issue.Body -Encoding utf8

        $args = @("issue", "create", "--title", $Issue.Title, "--body-file", $tmp)
        foreach ($label in $Issue.Labels) {
            $args += @("--label", $label)
        }

        & gh @args
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create issue: $($Issue.Title)"
        }
    }
    finally {
        Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

$issues = @(
    @{
        Title = "V2: Preserve relationship direction in extraction to graph writes"
        Labels = @("v2", "phase:1-correctness", "type:feature", "priority:p0")
        Body = @"
## Problem
Current extraction/write flow can lose relationship direction semantics.

## Scope
- Keep source/target direction unchanged end-to-end.
- Remove endpoint sorting that mutates directional meaning.
- Add regression tests for directional relationship types.

## Acceptance Criteria
- Directional relationships remain directional in persisted graph.
- Tests cover forward and inverse relationship assertions.
"@
    },
    @{
        Title = "V2: Add document versioning and source hash model"
        Labels = @("v2", "phase:1-correctness", "type:feature", "priority:p0")
        Body = @"
## Scope
- Introduce DocumentVersion model with content hash.
- Link chunks and assertions to version scope.
- Preserve backward compatibility where feasible.

## Acceptance Criteria
- Version records are persisted on ingest.
- Re-ingest behavior uses version identity intentionally.
"@
    },
    @{
        Title = "V2: Implement replace-document reconciliation for re-ingest"
        Labels = @("v2", "phase:1-correctness", "type:feature", "priority:p0")
        Body = @"
## Scope
- Add reconciliation mode that removes stale artifacts for a document.
- Cover chunks, mentions, and relationships.

## Acceptance Criteria
- Changed source re-ingest does not leave stale graph residue.
- Integration tests verify final graph correctness.
"@
    },
    @{
        Title = "V2: Add deterministic ingest report contract"
        Labels = @("v2", "phase:1-correctness", "type:feature", "priority:p1")
        Body = @"
## Scope
- Standard summary fields for add/update/remove and timing.
- Optional JSON output for automation.

## Acceptance Criteria
- `kg ingest` report is deterministic and documented.
"@
    },
    @{
        Title = "V2: Externalize large ingest stage artifacts from Neo4j job node"
        Labels = @("v2", "phase:2-platform", "type:refactor", "priority:p1")
        Body = @"
## Scope
- Store job metadata in Neo4j and large payloads in artifact storage.
- Resume pipeline from artifact references.

## Acceptance Criteria
- Bounded job property size in Neo4j.
- Resume path validated by tests.
"@
    },
    @{
        Title = "V2: Define stable domain protocols for stores and retrievers"
        Labels = @("v2", "phase:2-platform", "type:refactor", "priority:p1")
        Body = @"
## Scope
- Protocols for GraphStore, JobStore, Retriever, Answerer.
- CLI and API adapters call service layer only.

## Acceptance Criteria
- Type-checked interfaces documented and used.
"@
    },
    @{
        Title = "V2: Add `kg check` graph integrity diagnostics"
        Labels = @("v2", "phase:2-platform", "type:feature", "priority:p1")
        Body = @"
## Scope
- Add integrity checks for common data quality failures.
- Add machine-readable output and exit codes.

## Acceptance Criteria
- Command is CI-friendly and documented.
"@
    },
    @{
        Title = "V2: Add structured telemetry for ingest, query, and rag operations"
        Labels = @("v2", "phase:2-platform", "type:feature", "priority:p2")
        Body = @"
## Scope
- Structured logs and stable metric fields.
- Track latency, retries, row counts, and tx counts.

## Acceptance Criteria
- Logs are parseable and sensitive values are redacted.
"@
    },
    @{
        Title = "V2: Upgrade RAG response contract with citations and confidence"
        Labels = @("v2", "phase:3-rag", "type:feature", "priority:p0")
        Body = @"
## Scope
- Include citation IDs and insufficient-evidence signaling.
- Surface citations in CLI and API outputs.

## Acceptance Criteria
- Contract is stable and test-covered.
"@
    },
    @{
        Title = "V2: Expand Cypher safety policy and high-risk query blocks"
        Labels = @("v2", "phase:3-rag", "type:security", "priority:p0")
        Body = @"
## Scope
- Extend query validator to high-risk call patterns.
- Improve safe failure responses.

## Acceptance Criteria
- Bypass attempts are blocked by tests.
"@
    },
    @{
        Title = "V2: Build retrieval and answer evaluation harness"
        Labels = @("v2", "phase:3-rag", "type:feature", "priority:p1")
        Body = @"
## Scope
- Create gold questions with expected evidence.
- Add repeatable evaluation script and report output.

## Acceptance Criteria
- Baseline evaluation report committed to docs.
"@
    },
    @{
        Title = "V2: Add `kg doctor` onboarding diagnostics command"
        Labels = @("v2", "phase:4-ux", "type:feature", "priority:p1")
        Body = @"
## Scope
- Validate environment, connectivity, and optional dependencies.
- Return actionable fix hints.

## Acceptance Criteria
- New users can self-diagnose common setup failures.
"@
    },
    @{
        Title = "V2: Redesign web UI for investigator workflow"
        Labels = @("v2", "phase:4-ux", "type:feature", "priority:p1")
        Body = @"
## Scope
- Graph exploration + evidence panel + query history.
- Mobile-friendly layout and clearer visual hierarchy.

## Acceptance Criteria
- Users can navigate from answer to evidence in a single flow.
"@
    },
    @{
        Title = "V2: Ship synthetic fraud and E&O demo walkthrough"
        Labels = @("v2", "phase:4-ux", "type:docs", "priority:p2")
        Body = @"
## Scope
- End-to-end synthetic investigation dataset and query guide.
- Scripted ingest and demo flow.

## Acceptance Criteria
- Demo works without real-world sensitive data.
"@
    },
    @{
        Title = "V2: Enforce CI gates for lint, type-check, and Neo4j integration"
        Labels = @("v2", "phase:5-devsecops", "type:feature", "priority:p0")
        Body = @"
## Scope
- Add ruff and mypy checks to CI.
- Run integration tests with ephemeral Neo4j in CI.

## Acceptance Criteria
- Required checks protect main branch.
"@
    },
    @{
        Title = "V2: Define release and versioning policy for public interfaces"
        Labels = @("v2", "phase:5-devsecops", "type:docs", "priority:p1")
        Body = @"
## Scope
- Document semantic versioning and deprecation policy.
- Add release checklist and changelog process.

## Acceptance Criteria
- Policy is referenced by CONTRIBUTING or maintainer docs.
"@
    }
)

$labelDefinitions = @(
    @{ Name = "v2"; Color = "1d76db"; Description = "V2 rebuild initiative" },
    @{ Name = "phase:1-correctness"; Color = "b60205"; Description = "V2 phase 1 correctness work" },
    @{ Name = "phase:2-platform"; Color = "d93f0b"; Description = "V2 phase 2 platform and contracts" },
    @{ Name = "phase:3-rag"; Color = "fbca04"; Description = "V2 phase 3 RAG reliability" },
    @{ Name = "phase:4-ux"; Color = "0e8a16"; Description = "V2 phase 4 UX and product surface" },
    @{ Name = "phase:5-devsecops"; Color = "5319e7"; Description = "V2 phase 5 hardening and release" },
    @{ Name = "type:feature"; Color = "0052cc"; Description = "Feature work" },
    @{ Name = "type:refactor"; Color = "c2e0c6"; Description = "Refactor work" },
    @{ Name = "type:security"; Color = "e11d21"; Description = "Security-related work" },
    @{ Name = "type:docs"; Color = "f9d0c4"; Description = "Documentation work" },
    @{ Name = "priority:p0"; Color = "b60205"; Description = "Highest priority" },
    @{ Name = "priority:p1"; Color = "d93f0b"; Description = "High priority" },
    @{ Name = "priority:p2"; Color = "fbca04"; Description = "Medium priority" }
)

if (-not $Execute) {
    Write-Host "Dry run mode. No issues created."
    Write-Host "Planned issues: $($issues.Count)"
    foreach ($issue in $issues) {
        Write-Host " - $($issue.Title)"
    }
    Write-Host ""
    Write-Host "To create labels and issues, run:"
    Write-Host "  powershell -NoProfile -File scripts/create-v2-issues.ps1 -Execute"
    exit 0
}

Ensure-GhAuth

foreach ($label in $labelDefinitions) {
    Ensure-Label -Name $label.Name -Color $label.Color -Description $label.Description
}

foreach ($issue in $issues) {
    New-Issue -Issue $issue
}

Write-Host "Created $($issues.Count) issues."

