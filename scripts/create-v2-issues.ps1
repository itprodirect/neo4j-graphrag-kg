param(
    [switch]$Execute,
    [string]$Milestone = "V2 Rebuild"
)

$ErrorActionPreference = "Stop"

function Ensure-GhAuth {
    try {
        $null = & gh auth status *> $null
    }
    catch {
        # gh can emit status text on stderr even when authenticated
    }

    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI auth is invalid. Run 'gh auth login -h github.com' first."
    }
}

function Get-RepoSlug {
    $slug = (& gh repo view --json nameWithOwner --jq .nameWithOwner).Trim()
    if (-not $slug) {
        throw "Unable to resolve repo slug from gh repo view."
    }
    return $slug
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

function Ensure-Milestone {
    param(
        [string]$Name
    )

    $repo = Get-RepoSlug
    $existingRaw = & gh api "repos/$repo/milestones?state=all&per_page=100"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list milestones for $repo"
    }

    $existing = @($existingRaw | ConvertFrom-Json)
    $match = $existing | Where-Object { $_.title -eq $Name }
    if ($null -ne $match) {
        return
    }

    & gh api "repos/$repo/milestones" --method POST -f title=$Name | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create milestone '$Name'"
    }
}

function Test-IssueExists {
    param(
        [string]$Title
    )

    $found = (& gh issue list --state all --search ('"' + $Title + '" in:title') --limit 1 --json title --jq '.[0].title').Trim()
    return ($LASTEXITCODE -eq 0 -and $found -eq $Title)
}

function New-Issue {
    param(
        [hashtable]$Issue,
        [string]$MilestoneName
    )

    $title = "[V2-{0:d2}] {1}" -f [int]$Issue.Sequence, $Issue.Title

    if (Test-IssueExists -Title $title) {
        Write-Host "Skip existing issue: $title"
        return
    }

    $owners = @($Issue.Owners)
    if ($owners.Count -eq 0) {
        $owners = @("@me")
    }

    $body = @"
## Sequence
$($Issue.Sequence) / 16

## Owner(s)
$($owners -join ", ")

$($Issue.Body)
"@

    $tmp = New-TemporaryFile
    try {
        Set-Content -LiteralPath $tmp -Value $body -Encoding utf8

        $args = @(
            "issue", "create",
            "--title", $title,
            "--body-file", $tmp,
            "--milestone", $MilestoneName
        )

        foreach ($label in $Issue.Labels) {
            $args += @("--label", $label)
        }
        foreach ($owner in $owners) {
            $args += @("--assignee", $owner)
        }

        & gh @args
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create issue: $title"
        }
    }
    finally {
        Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

$issues = @(
    @{
        Sequence = 1
        Title = "Preserve relationship direction in extraction to graph writes"
        Owners = @("@me")
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
        Sequence = 2
        Title = "Add document versioning and source hash model"
        Owners = @("@me")
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
        Sequence = 3
        Title = "Implement replace-document reconciliation for re-ingest"
        Owners = @("@me")
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
        Sequence = 4
        Title = "Upgrade RAG response contract with citations and confidence"
        Owners = @("@me")
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
        Sequence = 5
        Title = "Expand Cypher safety policy and high-risk query blocks"
        Owners = @("@me")
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
        Sequence = 6
        Title = "Enforce CI gates for lint, type-check, and Neo4j integration"
        Owners = @("@me")
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
        Sequence = 7
        Title = "Add deterministic ingest report contract"
        Owners = @("@me")
        Labels = @("v2", "phase:1-correctness", "type:feature", "priority:p1")
        Body = @"
## Scope
- Standard summary fields for add/update/remove and timing.
- Optional JSON output for automation.

## Acceptance Criteria
- kg ingest report is deterministic and documented.
"@
    },
    @{
        Sequence = 8
        Title = "Externalize large ingest stage artifacts from Neo4j job node"
        Owners = @("@me")
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
        Sequence = 9
        Title = "Define stable domain protocols for stores and retrievers"
        Owners = @("@me")
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
        Sequence = 10
        Title = "Add kg check graph integrity diagnostics"
        Owners = @("@me")
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
        Sequence = 11
        Title = "Build retrieval and answer evaluation harness"
        Owners = @("@me")
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
        Sequence = 12
        Title = "Add kg doctor onboarding diagnostics command"
        Owners = @("@me")
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
        Sequence = 13
        Title = "Redesign web UI for investigator workflow"
        Owners = @("@me")
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
        Sequence = 14
        Title = "Define release and versioning policy for public interfaces"
        Owners = @("@me")
        Labels = @("v2", "phase:5-devsecops", "type:docs", "priority:p1")
        Body = @"
## Scope
- Document semantic versioning and deprecation policy.
- Add release checklist and changelog process.

## Acceptance Criteria
- Policy is referenced by CONTRIBUTING or maintainer docs.
"@
    },
    @{
        Sequence = 15
        Title = "Add structured telemetry for ingest, query, and rag operations"
        Owners = @("@me")
        Labels = @("v2", "phase:2-platform", "type:feature", "priority:p2")
        Body = @"
## Scope
- Structured logs and stable metric fields.
- Track latency, retries, row counts, and transaction counts.

## Acceptance Criteria
- Logs are parseable and sensitive values are redacted.
"@
    },
    @{
        Sequence = 16
        Title = "Ship synthetic fraud and E&O demo walkthrough"
        Owners = @("@me")
        Labels = @("v2", "phase:4-ux", "type:docs", "priority:p2")
        Body = @"
## Scope
- End-to-end synthetic investigation dataset and query guide.
- Scripted ingest and demo flow.

## Acceptance Criteria
- Demo works without real-world sensitive data.
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

$ordered = $issues | Sort-Object { [int]$_.Sequence }

if (-not $Execute) {
    Write-Host "Dry run mode. No issues created."
    Write-Host "Milestone: $Milestone"
    Write-Host "Planned issues: $($ordered.Count)"
    foreach ($issue in $ordered) {
        $owners = @($issue.Owners)
        if ($owners.Count -eq 0) {
            $owners = @("@me")
        }
        Write-Host (" - [V2-{0:d2}] {1} (owners: {2})" -f [int]$issue.Sequence, $issue.Title, ($owners -join ", "))
    }
    Write-Host ""
    Write-Host "To create labels, milestone, and issues, run:"
    Write-Host "  powershell -NoProfile -File scripts/create-v2-issues.ps1 -Execute"
    exit 0
}

Ensure-GhAuth

foreach ($label in $labelDefinitions) {
    Ensure-Label -Name $label.Name -Color $label.Color -Description $label.Description
}

Ensure-Milestone -Name $Milestone

foreach ($issue in $ordered) {
    New-Issue -Issue $issue -MilestoneName $Milestone
}

Write-Host "V2 backlog sync complete for milestone '$Milestone'."
