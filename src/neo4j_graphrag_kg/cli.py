"""CLI entry-point for the `kg` command."""

from __future__ import annotations

import typer

app = typer.Typer(help="Neo4j Knowledge-Graph CLI", no_args_is_help=True)

# Commands are registered below; stubs for initial skeleton.
# `kg ping`, `kg init-db`, and `kg status` will be added in subsequent commits.
