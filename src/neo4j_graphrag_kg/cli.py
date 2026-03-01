"""CLI entry-point for the `kg` command."""

from __future__ import annotations

import typer

from neo4j_graphrag_kg.neo4j_client import get_driver, close_driver

app = typer.Typer(help="Neo4j Knowledge-Graph CLI", no_args_is_help=True)


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
