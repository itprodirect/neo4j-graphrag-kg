# Synthetic Claims Network Dataset

This synthetic dataset is designed to show why graph modeling can surface
fraud, misrepresentation, and errors-and-omissions patterns faster than
traditional row-and-table workflows.

## Scenario Summary

The corpus models a commercial property claim ecosystem:
- Carrier: `Northstar Mutual Insurance`
- Insured: `Eclipse Manufacturing Holdings`
- Broker: `Summit Risk Advisors`
- Vendors: `Apex Restoration Group`, `Pinnacle Emergency Services`
- Individuals: adjusters, broker reps, AP staff, and investigators

Intentional risk signals are embedded:
- Policy misrepresentation (prior losses and solvent storage omitted)
- Duplicate/suspicious invoicing patterns
- Shared bank account across vendors
- Cross-claim vendor reuse
- Potential adjuster/vendor collusion
- Broker E&O exposure

## Files

- `01_policy_application.txt`
- `02_underwriting_inspection.txt`
- `03_first_notice_of_loss.txt`
- `04_adjuster_field_notes.txt`
- `05_vendor_invoices.txt`
- `06_payment_journal.txt`
- `07_internal_audit_email_thread.txt`
- `08_broker_eo_review.txt`
- `09_legal_interview_extract.txt`
- `10_cross_claim_linkage.txt`
- `investigator_queries.md`

## Suggested Ingest

From repo root:

```powershell
powershell -NoProfile -File scripts/ingest-synthetic-claims.ps1 -Extractor simple
```

For richer typed relationships:

```powershell
powershell -NoProfile -File scripts/ingest-synthetic-claims.ps1 -Extractor llm -Provider openai -Model gpt-4o
```

## Why Graph Helps Here

A graph can naturally model:
- One-to-many and many-to-many entity relationships
- Cross-document identity overlap
- Multi-hop investigative paths (person -> company -> bank account -> claim)
- Contradiction links (application statement vs inspection finding)

See `investigator_queries.md` for starter Cypher queries.

