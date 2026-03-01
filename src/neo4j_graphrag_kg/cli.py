"""CLI entry-point for the `kg` command."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import typer

from neo4j_graphrag_kg.config import get_settings
from neo4j_graphrag_kg.neo4j_client import get_driver, close_driver
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
) -> None:
    """Ingest a text file: chunk → extract entities → upsert to Neo4j."""
    _setup_logging()

    if not input.is_file():
        typer.echo(f"File not found: {input}", err=True)
        raise typer.Exit(code=1)

    from neo4j_graphrag_kg.ingest import ingest_file

    settings = get_settings()
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
) -> None:
    """Run a read-only Cypher query and print results as a table."""
    settings = get_settings()
    driver = get_driver(settings)
    try:
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(cypher)
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
