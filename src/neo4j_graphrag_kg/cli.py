"""CLI entry-point for the `kg` command."""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any

import typer

from neo4j_graphrag_kg.config import Settings, get_settings
from neo4j_graphrag_kg.extractors.base import BaseExtractor
from neo4j_graphrag_kg.neo4j_client import close_driver, get_driver
from neo4j_graphrag_kg.rag.text2cypher import validate_cypher_readonly
from neo4j_graphrag_kg.schema import ALL_STATEMENTS
from neo4j_graphrag_kg.services import build_service_container

app = typer.Typer(help="Neo4j Knowledge-Graph CLI", no_args_is_help=True)


def _setup_logging() -> None:
    """Configure root logger for CLI usage (INFO level)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-30s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_extractor(
    settings: Settings,
    *,
    extractor_name: str,
    provider: str,
    model: str,
    entity_types: str,
) -> tuple[str, BaseExtractor]:
    from neo4j_graphrag_kg.extractors import get_extractor

    ext_type = extractor_name or settings.extractor_type or "simple"
    if ext_type == "llm":
        llm_provider = provider or settings.llm_provider
        llm_model = model or settings.llm_model
        api_key = settings.llm_api_key
        if not api_key:
            raise ValueError(
                "LLM_API_KEY is required when using --extractor llm. "
                "Set it in .env or as an environment variable."
            )

        e_types = (
            [t.strip() for t in entity_types.split(",") if t.strip()]
            if entity_types
            else settings.entity_types
        )

        extractor = get_extractor(
            "llm",
            provider=llm_provider,
            model=llm_model or None,
            api_key=api_key,
            entity_types=e_types,
            relationship_types=settings.relationship_types,
            timeout=settings.llm_timeout,
        )
        return ext_type, extractor

    if ext_type == "simple":
        return ext_type, get_extractor("simple")

    raise ValueError(f"Unknown extractor: {ext_type!r}. Use 'simple' or 'llm'.")


def _find_local_dotenv() -> Path | None:
    """Walk up from cwd to locate a local .env file."""
    cur = Path.cwd()
    for parent in [cur, *cur.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None


def _module_available(module_name: str) -> bool:
    """Return True when an optional dependency can be imported."""
    return importlib.util.find_spec(module_name) is not None


def _doctor_check(status: str, detail: str) -> dict[str, str]:
    """Create a simple doctor status record."""
    return {"status": status, "detail": detail}


@app.command()
def ping() -> None:
    """Verify connectivity to the Neo4j instance."""
    settings = get_settings()
    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)
    try:
        services.graph.verify_connectivity()
        typer.echo("Neo4j is reachable.")
    except Exception as exc:
        typer.echo(f"Cannot reach Neo4j: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command("init-db")
def init_db() -> None:
    """Create constraints and indexes (idempotent, Neo4j 5+ syntax)."""
    settings = get_settings()
    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)
    try:
        with services.graph.session() as session:
            for stmt in ALL_STATEMENTS:
                session.run(stmt)
                typer.echo(f"  OK  {stmt.split('IF NOT EXISTS')[0].strip()}")
        typer.echo("Schema initialised.")
    except Exception as exc:
        typer.echo(f"Schema init failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command()
def status() -> None:
    """Show Neo4j version, node/rel counts, and constraints."""
    settings = get_settings()
    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)
    try:
        with services.graph.session() as session:
            ver = session.run(
                "CALL dbms.components() YIELD name, versions RETURN name, versions"
            ).single()
            if ver:
                typer.echo(f"{ver['name']} {ver['versions'][0]}")

            counts = session.run(
                "MATCH (n) "
                "OPTIONAL MATCH ()-[r]->() "
                "RETURN count(DISTINCT n) AS nodes, count(DISTINCT r) AS rels"
            ).single()
            if counts:
                typer.echo(f"Nodes: {counts['nodes']}  Relationships: {counts['rels']}")

            constraints = list(session.run("SHOW CONSTRAINTS"))
            typer.echo(f"Constraints ({len(constraints)}):")
            for c in constraints:
                typer.echo(f"  {c['name']}")

            indexes = list(session.run("SHOW INDEXES"))
            typer.echo(f"Indexes ({len(indexes)}):")
            for idx in indexes:
                typer.echo(f"  {idx['name']}")

    except Exception as exc:
        typer.echo(f"Status check failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command("doctor")
def doctor(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print setup diagnostics as JSON.",
    ),
) -> None:
    """Run local setup diagnostics for config, dependencies, and connectivity."""
    settings = get_settings()
    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)

    dotenv_path = _find_local_dotenv()
    config_summary = {
        "neo4j_uri": settings.neo4j_uri,
        "neo4j_database": settings.neo4j_database,
        "extractor_type": settings.extractor_type,
        "llm_provider": settings.llm_provider,
    }

    core_checks: dict[str, dict[str, str]] = {
        "env_file": _doctor_check(
            "ok" if dotenv_path is not None else "info",
            (
                f"Using .env at {dotenv_path}"
                if dotenv_path is not None
                else (
                    "No .env file found in the current workspace; "
                    "using process environment and defaults."
                )
            ),
        )
    }
    feature_checks: dict[str, dict[str, str]] = {}
    core_attention = False

    if settings.neo4j_password:
        core_checks["neo4j_password"] = _doctor_check(
            "ok",
            "NEO4J_PASSWORD is configured.",
        )
        try:
            services.graph.verify_connectivity()
            core_checks["neo4j_connectivity"] = _doctor_check(
                "ok",
                f"Connected to {settings.neo4j_uri} / database {settings.neo4j_database}.",
            )
        except Exception as exc:
            core_checks["neo4j_connectivity"] = _doctor_check(
                "attention",
                f"Cannot reach Neo4j: {exc}",
            )
            core_attention = True
    else:
        core_checks["neo4j_password"] = _doctor_check(
            "attention",
            "NEO4J_PASSWORD is empty.",
        )
        core_checks["neo4j_connectivity"] = _doctor_check(
            "attention",
            "Connectivity check skipped because NEO4J_PASSWORD is empty.",
        )
        core_attention = True

    extractor_type = settings.extractor_type.strip().lower()
    provider = settings.llm_provider.strip().lower()
    provider_module = provider if provider in {"anthropic", "openai"} else ""

    if extractor_type == "simple":
        core_checks["active_extractor"] = _doctor_check(
            "ok",
            "Simple extractor is active and requires no optional LLM dependencies.",
        )
    elif extractor_type == "llm":
        if provider_module == "":
            core_checks["active_extractor"] = _doctor_check(
                "attention",
                (
                    f"Unsupported LLM_PROVIDER {settings.llm_provider!r}. "
                    "Use 'anthropic' or 'openai'."
                ),
            )
            core_attention = True
        elif not settings.llm_api_key:
            core_checks["active_extractor"] = _doctor_check(
                "attention",
                "LLM extractor is configured but LLM_API_KEY is empty.",
            )
            core_attention = True
        elif not _module_available(provider_module):
            core_checks["active_extractor"] = _doctor_check(
                "attention",
                (
                    f"LLM extractor requires the '{provider_module}' package "
                    f"for provider {provider_module!r}."
                ),
            )
            core_attention = True
        else:
            core_checks["active_extractor"] = _doctor_check(
                "ok",
                f"LLM extractor is ready for provider {provider_module!r}.",
            )
    else:
        core_checks["active_extractor"] = _doctor_check(
            "attention",
            f"Unsupported EXTRACTOR_TYPE {settings.extractor_type!r}. Use 'simple' or 'llm'.",
        )
        core_attention = True

    if provider_module == "":
        feature_checks["ask"] = _doctor_check(
            "info",
            "kg ask requires a supported LLM_PROVIDER ('anthropic' or 'openai').",
        )
    elif not settings.llm_api_key:
        feature_checks["ask"] = _doctor_check(
            "info",
            "kg ask is disabled until LLM_API_KEY is configured.",
        )
    elif not _module_available(provider_module):
        feature_checks["ask"] = _doctor_check(
            "info",
            (
                f"Install -e '.[{provider_module}]' to enable kg ask "
                f"for provider {provider_module!r}."
            ),
        )
    else:
        feature_checks["ask"] = _doctor_check(
            "ok",
            f"kg ask is ready for provider {provider_module!r}.",
        )

    if _module_available("fastapi") and _module_available("uvicorn"):
        feature_checks["serve"] = _doctor_check(
            "ok",
            "kg serve dependencies are installed.",
        )
    else:
        feature_checks["serve"] = _doctor_check(
            "info",
            "Install -e '.[web]' to enable kg serve.",
        )

    report: dict[str, Any] = {
        "status": "ok" if not core_attention else "attention",
        "config": config_summary,
        "core_checks": core_checks,
        "feature_checks": feature_checks,
    }

    try:
        if json_output:
            typer.echo(json.dumps(report, indent=2))
        else:
            typer.echo(f"Doctor: {report['status']}")
            typer.echo(
                "Config: "
                f"uri={settings.neo4j_uri}  db={settings.neo4j_database}  "
                f"extractor={settings.extractor_type}  provider={settings.llm_provider}"
            )
            typer.echo("Core:")
            for key, value in core_checks.items():
                typer.echo(
                    f"  [{value['status']}] {key}: {value['detail']}"
                )
            typer.echo("Features:")
            for key, value in feature_checks.items():
                typer.echo(
                    f"  [{value['status']}] {key}: {value['detail']}"
                )

        if core_attention:
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Doctor failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command("check")
def check_graph(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print integrity diagnostics as JSON.",
    ),
) -> None:
    """Run graph integrity diagnostics and fail if stale artifacts are found."""
    settings = get_settings()
    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)
    try:
        diagnostics = services.graph.diagnostics()
        if json_output:
            typer.echo(json.dumps(diagnostics, indent=2))
        else:
            typer.echo(f"Graph integrity: {diagnostics['status']}")
            typer.echo(f"Stale artifacts: {diagnostics['stale_total']}")
            checks = diagnostics["checks"]
            typer.echo(
                "Checks: "
                f"docs_without_chunks={checks['documents_without_chunks']}  "
                f"orphan_chunks={checks['orphan_chunks']}  "
                f"related_without_doc={checks['related_edges_without_document']}  "
                f"orphan_entities={checks['orphan_entities']}"
            )

        if diagnostics["status"] != "ok":
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Integrity check failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command()
def ingest(
    input: Path = typer.Option(..., "--input", help="Path to a UTF-8 text file"),
    doc_id: str = typer.Option(..., "--doc-id", help="Unique document identifier"),
    title: str = typer.Option(..., "--title", help="Document title"),
    source: str = typer.Option("", "--source", help="Source URL or reference"),
    chunk_size: int = typer.Option(1000, "--chunk-size", help="Chars per chunk"),
    chunk_overlap: int = typer.Option(150, "--chunk-overlap", help="Overlap between chunks"),
    extractor_name: str = typer.Option(
        "", "--extractor", help="Extractor: 'simple' or 'llm' (default: from config)",
    ),
    provider: str = typer.Option(
        "", "--provider", help="LLM provider: 'anthropic' or 'openai' (default: from config)",
    ),
    model: str = typer.Option(
        "", "--model", help="LLM model name (default: from config)",
    ),
    entity_types: str = typer.Option(
        "", "--entity-types", help="Comma-separated entity types for LLM extraction",
    ),
    replace_mode: str = typer.Option(
        "atomic",
        "--replace-mode",
        help="Re-ingest strategy for same doc_id: 'atomic' (default) or 'non_atomic'",
    ),
    max_retries: int = typer.Option(
        2, "--max-retries", min=0, help="Maximum retries per ingest stage on failure",
    ),
    queue_only: bool = typer.Option(
        False,
        "--queue-only",
        help="Create a durable ingest job and exit without processing it now.",
    ),
) -> None:
    """Ingest a text file through staged jobs with durable Neo4j job state."""
    _setup_logging()

    if not input.is_file():
        typer.echo(f"File not found: {input}", err=True)
        raise typer.Exit(code=1)

    from neo4j_graphrag_kg.ingest import IngestJobSpec

    settings = get_settings()
    try:
        ext_type, ext_instance = _build_extractor(
            settings,
            extractor_name=extractor_name,
            provider=provider,
            model=model,
            entity_types=entity_types,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)

    replace_mode_norm = replace_mode.strip().lower().replace("-", "_")
    if replace_mode_norm not in {"atomic", "non_atomic"}:
        typer.echo(
            "Invalid --replace-mode. Use 'atomic' or 'non_atomic'.",
            err=True,
        )
        raise typer.Exit(code=1)

    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)
    try:
        spec = IngestJobSpec(
            input_path=input,
            doc_id=doc_id,
            title=title,
            source=source,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            replace_mode=replace_mode_norm,
        )
        job_id = services.ingest.enqueue_job(
            spec,
            max_retries=max_retries,
            extractor_name=ext_type,
        )

        if queue_only:
            typer.echo(f"Queued ingest job: {job_id}")
            typer.echo("Run 'kg ingest-run --job-id <id>' to process it.")
            return

        summary = services.ingest.run_job(job_id, extractor=ext_instance)
        typer.echo(
            f"Ingested '{doc_id}' via job {job_id}: {summary['chunks']} chunks, "
            f"{summary['entities']} entities, {summary['edges']} edges "
            f"in {summary['elapsed_s']}s"
        )
    except Exception as exc:
        typer.echo(f"Ingestion failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command("ingest-status")
def ingest_status(
    job_id: str = typer.Option(..., "--job-id", help="Ingest job ID to inspect"),
) -> None:
    """Show durable ingest job state (status, stage, retries, summary)."""
    settings = get_settings()
    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)
    try:
        job = services.ingest.jobs.get_job(job_id)
        if job is None:
            typer.echo(f"Job not found: {job_id}", err=True)
            raise typer.Exit(code=1)

        payload = {
            "id": job.get("id"),
            "status": job.get("status"),
            "stage": job.get("stage"),
            "attempt": job.get("attempt"),
            "max_retries": job.get("max_retries"),
            "error": job.get("error"),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "completed_at": job.get("completed_at"),
            "summary": job.get("summary", {}),
        }
        typer.echo(json.dumps(payload, indent=2))
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Could not read ingest job: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command("ingest-run")
def ingest_run(
    job_id: str = typer.Option(..., "--job-id", help="Queued ingest job ID to run"),
    extractor_name: str = typer.Option(
        "", "--extractor", help="Override extractor: 'simple' or 'llm'",
    ),
    provider: str = typer.Option(
        "", "--provider", help="LLM provider override: 'anthropic' or 'openai'",
    ),
    model: str = typer.Option(
        "", "--model", help="LLM model override",
    ),
    entity_types: str = typer.Option(
        "", "--entity-types", help="Comma-separated entity types override for LLM extraction",
    ),
) -> None:
    """Run a queued durable ingest job by ID."""
    _setup_logging()
    settings = get_settings()
    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)
    try:
        job = services.ingest.jobs.get_job(job_id)
        if job is None:
            typer.echo(f"Job not found: {job_id}", err=True)
            raise typer.Exit(code=1)

        requested = extractor_name or str(job.get("extractor_name", "simple"))
        try:
            _, ext_instance = _build_extractor(
                settings,
                extractor_name=requested,
                provider=provider,
                model=model,
                entity_types=entity_types,
            )
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1)

        summary = services.ingest.run_job(job_id, extractor=ext_instance)
        typer.echo(
            f"Completed job {job_id}: {summary['chunks']} chunks, "
            f"{summary['entities']} entities, {summary['edges']} edges "
            f"in {summary['elapsed_s']}s"
        )
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Could not run ingest job: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command()
def query(
    cypher: str = typer.Option(..., "--cypher", help="Cypher query to execute"),
    allow_write: bool = typer.Option(
        False,
        "--allow-write",
        help="Allow write/admin Cypher (bypasses read-only validation).",
    ),
) -> None:
    """Run a Cypher query and print results as a table (read-only by default)."""
    settings = get_settings()
    driver = get_driver(settings)
    try:
        query_text = cypher
        if not allow_write:
            try:
                query_text = validate_cypher_readonly(cypher)
            except Exception as exc:
                typer.echo(f"Query blocked by read-only validation: {exc}", err=True)
                raise typer.Exit(code=1)

        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(query_text)
            records = [dict(r) for r in result]

        if not records:
            typer.echo("(no results)")
            return

        keys = list(records[0].keys())
        col_widths = {k: len(k) for k in keys}
        str_rows: list[dict[str, str]] = []
        for rec in records:
            sr: dict[str, str] = {}
            for k in keys:
                val = rec[k]
                s = str(val) if val is not None else ""
                sr[k] = s
                col_widths[k] = max(col_widths[k], len(s))
            str_rows.append(sr)

        header = " | ".join(k.ljust(col_widths[k]) for k in keys)
        sep = "-+-".join("-" * col_widths[k] for k in keys)
        typer.echo(header)
        typer.echo(sep)
        for sr in str_rows:
            line = " | ".join(sr[k].ljust(col_widths[k]) for k in keys)
            typer.echo(line)
        typer.echo(f"\n({len(str_rows)} row{'s' if len(str_rows) != 1 else ''})")

    except Exception as exc:
        typer.echo(f"Query failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command()
def ask(
    question: str = typer.Argument(..., help="Natural language question about the graph"),
    cypher_only: bool = typer.Option(
        False, "--cypher-only", help="Print generated Cypher without executing",
    ),
    provider: str = typer.Option(
        "", "--provider", help="LLM provider: 'anthropic' or 'openai'",
    ),
    model: str = typer.Option(
        "", "--model", help="LLM model name",
    ),
) -> None:
    """Ask a natural language question about the knowledge graph (requires LLM API key)."""
    _setup_logging()

    from neo4j_graphrag_kg.rag.pipeline import ask as rag_ask

    settings = get_settings()

    api_key = settings.llm_api_key
    if not api_key:
        typer.echo(
            "LLM_API_KEY is required for 'kg ask'. "
            "Set it in .env or as an environment variable.",
            err=True,
        )
        raise typer.Exit(code=1)

    llm_provider = provider or settings.llm_provider
    llm_model = model or settings.llm_model

    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)
    try:
        response = rag_ask(
            question,
            driver=services.driver,
            database=services.graph.database,
            provider=llm_provider,
            model=llm_model,
            api_key=api_key,
            timeout=settings.llm_timeout,
            cypher_only=cypher_only,
        )

        if cypher_only:
            typer.echo(response.cypher)
        else:
            typer.echo(f"\n{response.answer}\n")
            typer.echo(f"--- Cypher: {response.cypher}")
            typer.echo(
                "--- Rows: "
                f"{len(response.results)}  Time: {response.elapsed_s}s  "
                f"Confidence: {response.confidence:.2f}"
            )
            evidence_status = (
                "insufficient evidence"
                if response.insufficient_evidence
                else "grounded in query results"
            )
            typer.echo(f"--- Evidence: {evidence_status}")
            if response.citations:
                typer.echo("--- Citations:")
                for citation in response.citations:
                    typer.echo(f"  [{citation['row']}] {citation['preview']}")
    except Exception as exc:
        typer.echo(f"RAG query failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", help="Port to run the web server on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
) -> None:
    """Start the graph visualization web server."""
    _setup_logging()

    try:
        uvicorn = importlib.import_module("uvicorn")
    except ImportError:
        typer.echo(
            "The 'web' extra is required for 'kg serve'. "
            "Install it with: pip install -e \".[web]\"",
            err=True,
        )
        raise typer.Exit(code=1)

    import threading
    import webbrowser

    url = f"http://{host}:{port}" if host != "0.0.0.0" else f"http://localhost:{port}"
    typer.echo(f"Starting graph visualization server at {url}")

    def _open_browser() -> None:
        import time

        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(
        "neo4j_graphrag_kg.web.app:app",
        host=host,
        port=port,
        log_level="info",
    )


@app.command()
def reset(
    confirm: bool = typer.Option(False, "--confirm", help="Required flag to confirm reset"),
) -> None:
    """Drop ALL nodes and relationships (DETACH DELETE). Requires --confirm."""
    if not confirm:
        typer.echo("Pass --confirm to actually delete all data.", err=True)
        raise typer.Exit(code=1)

    settings = get_settings()
    driver = get_driver(settings)
    services = build_service_container(settings, driver=driver)
    try:
        deleted = services.graph.reset(batch_size=10000)
        typer.echo(f"Reset complete. Deleted {deleted} nodes (and their relationships).")
    except Exception as exc:
        typer.echo(f"Reset failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()
