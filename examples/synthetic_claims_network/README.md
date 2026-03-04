# Synthetic Claims Network Dataset

Synthetic, investigation-friendly corpus for demonstrating graph-powered detection
of fraud, misrepresentation, and broker E&O risk.

## Dataset Status (as of 2026-03-04)

| Item | Status |
|---|---|
| Scenario docs | Complete |
| Ingest helper script | Complete |
| Investigator query pack | Complete |
| Intended use | Demo, workshops, retrieval testing |

## Scenario Summary

The corpus models a commercial property claim ecosystem:

- Carrier: `Northstar Mutual Insurance`
- Insured: `Eclipse Manufacturing Holdings`
- Broker: `Summit Risk Advisors`
- Vendors: `Apex Restoration Group`, `Pinnacle Emergency Services`
- People: adjusters, broker reps, AP staff, auditors, investigators

Embedded risk patterns:

- Policy application misrepresentation
- Duplicate invoice identifiers
- Shared remit account across vendors
- Vendor ownership overlap
- Cross-claim linkage signals
- Broker E&O exposure

## File Index

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

LLM extraction variant:

```powershell
powershell -NoProfile -File scripts/ingest-synthetic-claims.ps1 -Extractor llm -Provider openai -Model gpt-4o
```

## Why Graph Helps

Graph modeling makes these patterns easier to surface than row-first models:

- Multi-hop linkage paths (person -> vendor -> bank account -> claim)
- Cross-document contradiction checks
- Shared ownership and payment flow traces
- Ring-like high-degree entity discovery

## Notes

- Dataset is synthetic and demo-safe.
- No real customer data or production identifiers are included.

See `investigator_queries.md` for starter Cypher.
