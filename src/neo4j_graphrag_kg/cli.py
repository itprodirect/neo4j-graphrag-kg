"""CLI entry-point for the `kg` command."""

from __future__ import annotations

import typer

from neo4j_graphrag_kg.config import get_settings
from neo4j_graphrag_kg.neo4j_client import get_driver, close_driver
from neo4j_graphrag_kg.schema import ALL_STATEMENTS

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
