"""CLI entry-point for the `kg` command."""

from __future__ import annotations

import logging
from pathlib import Path
import typer

from neo4j_graphrag_kg.config import get_settings
from neo4j_graphrag_kg.neo4j_client import get_driver, close_driver
from neo4j_graphrag_kg.rag.text2cypher import validate_cypher_readonly
from neo4j_graphrag_kg.schema import ALL_STATEMENTS

app = typer.Typer(help="Neo4j Knowledge-Graph CLI", no_args_is_help=True)


def _setup_logging() -> None:
    """Configure root logger for CLI usage (INFO level)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-30s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )


@app.command()
def ping() -> None:
    """Verify connectivity to the Neo4j instance."""
    driver = get_driver()
    try:
        driver.verify_connectivity()
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
    try:
        with driver.session(database=settings.neo4j_database) as session:
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
    try:
        with driver.session(database=settings.neo4j_database) as session:
            # Version
            ver = session.run(
                "CALL dbms.components() YIELD name, versions RETURN name, versions"
            ).single()
            if ver:
                typer.echo(f"{ver['name']} {ver['versions'][0]}")

            # Node / relationship counts
            counts = session.run(
                "MATCH (n) "
                "OPTIONAL MATCH ()-[r]->() "
                "RETURN count(DISTINCT n) AS nodes, count(DISTINCT r) AS rels"
            ).single()
            if counts:
                typer.echo(f"Nodes: {counts['nodes']}  Relationships: {counts['rels']}")

            # Constraints
            constraints = list(session.run("SHOW CONSTRAINTS"))
            typer.echo(f"Constraints ({len(constraints)}):")
            for c in constraints:
                typer.echo(f"  {c['name']}")

            # Indexes
            indexes = list(session.run("SHOW INDEXES"))
            typer.echo(f"Indexes ({len(indexes)}):")
            for idx in indexes:
                typer.echo(f"  {idx['name']}")

    except Exception as exc:
        typer.echo(f"Status check failed: {exc}", err=True)
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
) -> None:
    """Ingest a text file: chunk, extract entities, upsert to Neo4j."""
    _setup_logging()

    if not input.is_file():
        typer.echo(f"File not found: {input}", err=True)
        raise typer.Exit(code=1)

    from neo4j_graphrag_kg.extractors import get_extractor
    from neo4j_graphrag_kg.ingest import ingest_file

    settings = get_settings()

    # Resolve extractor type: CLI flag > config > default
    ext_type = extractor_name or settings.extractor_type or "simple"

    # Build extractor instance — all extractors go through the same interface
    if ext_type == "llm":
        llm_provider = provider or settings.llm_provider
        llm_model = model or settings.llm_model
        api_key = settings.llm_api_key

        if not api_key:
            typer.echo(
                "LLM_API_KEY is required when using --extractor llm. "
                "Set it in .env or as an environment variable.",
                err=True,
            )
            raise typer.Exit(code=1)

        e_types = (
            [t.strip() for t in entity_types.split(",") if t.strip()]
            if entity_types
            else settings.entity_types
        )

        ext_instance = get_extractor(
            "llm",
            provider=llm_provider,
            model=llm_model or None,
            api_key=api_key,
            entity_types=e_types,
            relationship_types=settings.relationship_types,
        )
    elif ext_type == "simple":
        ext_instance = get_extractor("simple")
    else:
        typer.echo(f"Unknown extractor: {ext_type!r}. Use 'simple' or 'llm'.", err=True)
        raise typer.Exit(code=1)

    driver = get_driver(settings)
    try:
        summary = ingest_file(
            driver,
            settings.neo4j_database,
            input_path=input,
            doc_id=doc_id,
            title=title,
            source=source,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            extractor=ext_instance,
        )
        typer.echo(
            f"Ingested '{doc_id}': {summary['chunks']} chunks, "
            f"{summary['entities']} entities, {summary['edges']} edges "
            f"in {summary['elapsed_s']}s"
        )
    except Exception as exc:
        typer.echo(f"Ingestion failed: {exc}", err=True)
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

        # Build simple table
        keys = list(records[0].keys())
        # Compute column widths
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

        # Header
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
    try:
        response = rag_ask(
            question,
            driver=driver,
            database=settings.neo4j_database,
            provider=llm_provider,
            model=llm_model,
            api_key=api_key,
            cypher_only=cypher_only,
        )

        if cypher_only:
            typer.echo(response.cypher)
        else:
            typer.echo(f"\n{response.answer}\n")
            typer.echo(f"--- Cypher: {response.cypher}")
            typer.echo(f"--- Rows: {len(response.results)}  Time: {response.elapsed_s}s")
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
        import uvicorn
    except ImportError:
        typer.echo(
            "The 'web' extra is required for 'kg serve'. "
            "Install it with: pip install -e \".[web]\"",
            err=True,
        )
        raise typer.Exit(code=1)

    import webbrowser
    import threading

    url = f"http://{host}:{port}" if host != "0.0.0.0" else f"http://localhost:{port}"
    typer.echo(f"Starting graph visualization server at {url}")

    # Open browser after a short delay to let the server start
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
    try:
        with driver.session(database=settings.neo4j_database) as session:
            # Use batched delete to handle large graphs without OOM
            deleted = 0
            while True:
                result = session.run(
                    "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) AS c"
                )
                record = result.single()
                batch_count = record["c"] if record else 0
                if batch_count == 0:
                    break
                deleted += batch_count
        typer.echo(f"Reset complete. Deleted {deleted} nodes (and their relationships).")
    except Exception as exc:
        typer.echo(f"Reset failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        close_driver()
