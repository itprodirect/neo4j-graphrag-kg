param(
    [ValidateSet("simple", "llm")]
    [string]$Extractor = "simple",
    [string]$Provider = "",
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$datasetDir = Join-Path $repoRoot "examples\synthetic_claims_network"

if (-not (Test-Path -LiteralPath $datasetDir)) {
    throw "Dataset directory not found: $datasetDir"
}

$docs = @(
    @{ Id = "syn-policy-app"; Title = "Synthetic Policy Application"; File = "01_policy_application.txt" },
    @{ Id = "syn-inspection"; Title = "Synthetic Underwriting Inspection"; File = "02_underwriting_inspection.txt" },
    @{ Id = "syn-fnol"; Title = "Synthetic First Notice of Loss"; File = "03_first_notice_of_loss.txt" },
    @{ Id = "syn-adjuster-notes"; Title = "Synthetic Adjuster Field Notes"; File = "04_adjuster_field_notes.txt" },
    @{ Id = "syn-vendor-invoices"; Title = "Synthetic Vendor Invoice Packet"; File = "05_vendor_invoices.txt" },
    @{ Id = "syn-payment-journal"; Title = "Synthetic Payment Journal"; File = "06_payment_journal.txt" },
    @{ Id = "syn-audit-thread"; Title = "Synthetic Internal Audit Thread"; File = "07_internal_audit_email_thread.txt" },
    @{ Id = "syn-broker-eo"; Title = "Synthetic Broker EO Review"; File = "08_broker_eo_review.txt" },
    @{ Id = "syn-legal-interview"; Title = "Synthetic Legal Interview Extract"; File = "09_legal_interview_extract.txt" },
    @{ Id = "syn-cross-claim"; Title = "Synthetic Cross Claim Linkage"; File = "10_cross_claim_linkage.txt" }
)

Write-Host "Ingesting synthetic claims network documents using extractor '$Extractor'..."

foreach ($doc in $docs) {
    $inputPath = Join-Path $datasetDir $doc.File
    if (-not (Test-Path -LiteralPath $inputPath)) {
        throw "Missing dataset file: $inputPath"
    }

    $args = @(
        "ingest",
        "--input", $inputPath,
        "--doc-id", $doc.Id,
        "--title", $doc.Title,
        "--source", "synthetic_claims_network"
    )

    if ($Extractor -eq "llm") {
        $args += @("--extractor", "llm")
        if ($Provider) {
            $args += @("--provider", $Provider)
        }
        if ($Model) {
            $args += @("--model", $Model)
        }
    }

    Write-Host "  -> $($doc.Id) ($($doc.File))"
    & kg @args
    if ($LASTEXITCODE -ne 0) {
        throw "Ingest failed for doc_id '$($doc.Id)' with exit code $LASTEXITCODE"
    }
}

Write-Host ""
Write-Host "Synthetic dataset ingest complete."
Write-Host "Try:"
Write-Host "  kg query --cypher `"MATCH (e:Entity) RETURN e.name ORDER BY e.name LIMIT 25`""
Write-Host "  See examples/synthetic_claims_network/investigator_queries.md for more queries."

