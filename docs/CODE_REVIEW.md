# CODE REVIEW — neo4j-graphrag-kg

## 1) Executive summary

- The repository is a clean, modular Neo4j-first foundation with clear separation between ingestion, schema bootstrap, retrieval, and web/CLI surfaces; this is a strong base for insurance/legal knowledge workflows.
- Core invariants are mostly preserved (deterministic entity IDs, chunk IDs, batched `UNWIND ... MERGE` writes), but one correctness gap existed: `Document.created_at` was overwritten on re-ingest, weakening strict idempotency semantics (fixed in this review cycle).
- Neo4j write-path reliability needed hardening for real-world transient failures (cluster failover/network blips). Batched writes now include bounded retry with backoff for transient Neo4j exceptions (implemented).
- Schema and naming are mostly consistent (`Document`, `Chunk`, `Entity`, `MENTIONS`, `HAS_CHUNK`, `RELATED_TO`), but retrieval indexing and relationship-level constraints remain minimal for production-scale workloads.
- RAG is currently **Cypher-first LLM orchestration** (text2cypher + query + answer), not vector-first; this is acceptable for graph-first use cases but lacks evidence citation structure and poisoning defenses.
- Security posture is better than many early-stage repos (parameterization on public API graph endpoints, `.env` discipline, read-only Cypher validator in RAG pipeline), but ad-hoc CLI query execution remains unrestricted and can be destructive if misused.
- Test coverage is broad for unit logic and selected integrations, but CI does not provision Neo4j, so integration behavior is mostly asserted via skip mechanics rather than consistently executed in CI.
- DX is generally good (Typer CLI, src-layout, concise modules), but packaging currently depends on network at install time and can fail in restricted environments.
- For insurance/legal workloads with sensitive text, the project needs first-class data governance primitives next (PII redaction hooks, provenance fields, audit/event logging schema).
- Recommended path: keep architecture stable, add focused guardrails and observability primitives, and evolve public interfaces around stable ingestion/retrieval contracts.

## 2) Architecture map (components + data flow)

### Component boundaries

- **CLI surface (`cli.py`)**: operational entrypoints (`ping`, `init-db`, `status`, `ingest`, `query`, `ask`, `serve`, `reset`).
- **Config + connection (`config.py`, `neo4j_client.py`)**: env-based settings and singleton Neo4j driver.
- **Schema/bootstrap (`schema.py`)**: idempotent constraints/indexes.
- **Ingestion pipeline (`ingest.py`)**: orchestrates read → chunk → extraction → upsert.
- **Extraction layer (`extractors/`)**: simple heuristic + LLM extractors behind shared interface.
- **Persistence (`upsert.py`)**: batched transactional writes via `UNWIND`/`MERGE` helpers.
- **RAG layer (`rag/`)**: schema introspection, text-to-Cypher generation, read-only validation, query execution, answer synthesis.
- **Web/API (`web/app.py`)**: graph endpoints + ask endpoint + static visualization host.

### Data journey (actual flow today)

1. **Raw input**: text file path from CLI `kg ingest`.
2. **Chunking**: fixed character chunks with overlap (`chunker.py`).
3. **Extraction**: per-chunk entities + relationships (simple regex heuristics or LLM).
4. **ID normalization**:
   - entities: `slugify(name)`
   - chunks: `{doc_id}::chunk::{idx}`
   - relationships: deterministic ID helper from edge dimensions.
5. **Neo4j writes**: batched upserts for documents/chunks/entities/mentions/related edges via explicit transactions in `upsert.py`.
6. **Retrieval path (RAG)**:
   - question → graph schema introspection
   - LLM generates Cypher
   - read-only validator blocks write/admin/multi-statement queries
   - query executes in read-access transaction
   - LLM answers using only query rows.
7. **Output surfaces**: CLI printed answer/table and web JSON/visual graph.

## 3) P0 issues (must-fix for correctness/security)

1. **Re-ingest timestamp mutation broke strict idempotency semantics** ✅ fixed
   - `Document.created_at` was being overwritten on every ingest upsert.
   - Impact: replaying same dataset changed graph state even without content changes.
   - Fix applied: `created_at` now set only on node creation (`ON CREATE SET`).

2. **Write-path lacked resilience to transient Neo4j failures** ✅ fixed
   - No retry/backoff around batched writes.
   - Impact: intermittent network/cluster blips could abort ingest jobs.
   - Fix applied: bounded retry/backoff for `TransientError`, `ServiceUnavailable`, `SessionExpired`.

3. **Potential destructive usage path in CLI `kg query`** ⛳ pending
   - Query command executes user-provided Cypher without read-only guard.
   - While operationally useful, this is a footgun in multi-user operational environments.
   - Recommendation: add `--allow-write` opt-in and default read-only validation.

## 4) P1 improvements (high value, moderate effort)

- Add relationship-level uniqueness constraint/index strategy for `RELATED_TO.id` in Neo4j 5 to harden dedupe beyond MERGE pattern assumptions.
- Add ingestion integrity checks command (or post-ingest report): orphan chunks, orphan mentions, duplicate IDs, null critical properties.
- Introduce configurable ingest batch metrics (rows/sec, tx count, retries count) for production operability.
- Add optional per-document provenance metadata (`ingested_by`, `pipeline_version`, source hash) to support legal auditability.
- Expand CI to run at least one Neo4j-backed integration job with docker service.

## 5) P2 enhancements (nice-to-have / future)

- Add vector embeddings + vector index support for hybrid retrieval once embedding model/provider policy is decided.
- Add first-class retrieval abstraction (graph-only / hybrid / keyword) with swappable strategies.
- Introduce policy-aware redaction pipeline stage for PII before persistence.
- Add query caching and LLM response caching for cost/latency control.
- Add lightweight role model blueprint for future authn/authz integration (tenant/domain scopes).

## 6) Neo4j-specific recommendations (constraints/indexes/query patterns)

- Keep current unique constraints on node IDs; add relationship uniqueness where supported by your Neo4j edition/version policy.
- Consider indexes aligned to operational queries:
  - `Document(id)` already unique; consider additional lookup index for `Document.source` if frequently filtered.
  - `Chunk(document_id, idx)` composite index may help document reconstruction queries.
- Maintain parameterized Cypher in API endpoints; avoid string interpolation for dynamic filters/limits where possible.
- Preserve `UNWIND` batch writes + managed transactions; this is a strong pattern and should remain the write contract.
- If vector retrieval is added:
  - lock embedding dimensionality in config + schema docs,
  - define re-embed/update strategy on source mutation,
  - keep retrieval explainability metadata (distance/score/source chunk).

## 7) RAG/GraphRAG recommendations (retrieval/citations/grounding)

- Current implementation is **graph-query-first** via text2cypher; this is good but should output explicit evidence references (doc/chunk IDs) in answers by default.
- Add answer contract fields:
  - `evidence_rows` (or top-k rows used),
  - `citation_ids` (doc/chunk/entity IDs),
  - `insufficient_evidence: bool`.
- Harden prompt-injection resistance:
  - treat graph text as untrusted content,
  - keep system prompt strict (already good),
  - strip/normalize suspicious instruction-like text before few-shot context inclusion.
- Add query allowlist heuristics for high-risk patterns (`CALL`, full graph scans without selective predicates), with safe failure responses.

## 8) “Modular library” refactor suggestions (stable interfaces)

- Promote these to explicit stable interfaces:
  1. `IngestService.ingest_file(...) -> IngestSummary`
  2. `GraphStore` protocol (`init_schema`, `upsert_*`, `query_readonly`)
  3. `Retriever` protocol (`retrieve(question) -> RetrievalBundle`)
  4. `Answerer` protocol (`answer(question, bundle) -> AnswerResult`)
- Keep CLI/web as adapters over these interfaces; avoid business logic growth in transport layers.
- Preserve existing function-level APIs for backward compatibility; add wrappers rather than breaking signatures.

## 9) Concrete next steps (10-item checklist)

1. **[Backend | 0.5d]** Add read-only default guard to `kg query` with explicit override flag.
2. **[Backend | 1d]** Add integrity-check command (`kg check`) for orphan/duplicate sanity queries.
3. **[Backend | 1d]** Add relationship uniqueness/index strategy and migration note.
4. **[RAG | 1d]** Extend `RAGResponse` with structured citations/evidence fields.
5. **[RAG | 1d]** Add high-risk Cypher pattern gate + tests.
6. **[Security | 1.5d]** Add PII redaction hook interface in ingest pipeline.
7. **[Ops | 0.5d]** Emit ingest metrics logs (throughput, retries, tx count).
8. **[CI | 1d]** Add dockerized Neo4j integration job in GitHub Actions.
9. **[Docs | 0.5d]** Add production hardening section in README + DEV_NOTES.
10. **[Maintainer | 0.5d]** Define versioning policy for stable library interfaces.

---

## PR-sized change proposals

### Proposal 1 (implemented)

**Title:** Preserve immutable document creation timestamps across re-ingest

- **Rationale:** Ensures repeat ingest runs do not mutate `created_at`, preserving strict idempotency and predictable replay semantics.
- **Files touched:** `src/neo4j_graphrag_kg/upsert.py`, `tests/test_upsert.py`
- **Implementation notes:**
  - Changed document upsert Cypher to `ON CREATE SET d.created_at = row.created_at`.
  - Kept mutable fields (`title`, `source`) in `SET`.
- **Acceptance tests:**
  - Unit assertion that upsert statement contains `ON CREATE SET` for `created_at`.

### Proposal 2 (implemented)

**Title:** Add bounded retry/backoff for transient Neo4j write failures

- **Rationale:** Improves ingest reliability under intermittent Neo4j/network failures.
- **Files touched:** `src/neo4j_graphrag_kg/upsert.py`, `tests/test_upsert.py`
- **Implementation notes:**
  - Added `_execute_write_with_retry(...)` wrapper for `session.execute_write(...)`.
  - Retries `TransientError`, `ServiceUnavailable`, `SessionExpired` up to 3 attempts with exponential backoff.
- **Acceptance tests:**
  - Retry succeeds after first transient failure.
  - Exception is raised after retry budget exhausted.

### Proposal 3 (not yet implemented)

**Title:** Make `kg query` read-only by default with `--allow-write` escape hatch

- **Rationale:** Prevents accidental destructive operations while preserving operator flexibility.
- **Files likely touched:** `src/neo4j_graphrag_kg/cli.py`, `tests/test_security.py` or new CLI tests, README docs.
- **Implementation notes:**
  - Reuse `validate_cypher_readonly` before execution unless `--allow-write` is explicitly set.
  - Maintain existing command behavior for advanced users with explicit opt-in.
- **Acceptance tests:**
  - Write query blocked by default.
  - Same query succeeds when `--allow-write` provided.

---

## Local validation (end-to-end)

Run these commands from repo root:

```bash
# 1) Start Neo4j
cp .env.example .env  # first time only; set NEO4J_PASSWORD
docker compose up -d

# 2) Install package (normal connected environment)
pip install -e ".[dev,all]"

# 3) Initialize schema
kg init-db

# 4) Ingest sample
kg ingest --input examples/demo.txt --doc-id demo --title "Demo"

# 5) Confirm graph contents via Cypher
kg query --cypher "MATCH (d:Document {id:'demo'})-[:HAS_CHUNK]->(c:Chunk) RETURN d.id, count(c) AS chunks LIMIT 10"
kg query --cypher "MATCH (c:Chunk)-[:MENTIONS]->(e:Entity) RETURN e.name, count(*) AS mentions ORDER BY mentions DESC LIMIT 10"

# 6) RAG retrieval check (requires LLM_API_KEY)
kg ask "What entities are in the graph?"

# 7) Run tests
pytest -q
```

If working in a restricted/no-internet environment where extras cannot be installed, run:

```bash
PYTHONPATH=src pytest -q --ignore=tests/test_web.py --ignore=tests/test_security.py
```
