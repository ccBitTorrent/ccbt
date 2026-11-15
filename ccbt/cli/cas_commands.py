"""CAS / Hub server CLI commands (`ccbt cas serve`, `ccbt hub serve`)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
from aiohttp import web
from rich.console import Console

from ccbt.cas_server.app import parse_token_config, run_server
from ccbt.hub.api import create_hub_app

console = Console()


@click.group()
def cas() -> None:
    """Run a Xet CAS service."""


@cas.command("serve")
@click.option(
    "--root",
    "-r",
    type=click.Path(),
    default=".ccbt-cas",
    help="Storage root directory",
)
@click.option("--host", "-H", default="127.0.0.1")
@click.option("--port", "-p", type=int, default=8470)
@click.option(
    "--tokens",
    "-t",
    default=None,
    help='Static tokens, e.g. "alice:read,write;bob:read" (default: open local mode)',
)
def cas_serve(root: str, host: str, port: int, tokens: Optional[str]) -> None:
    """Serve the CAS API (HF/OpenXet contract) in the foreground."""
    console.print(f"Serving CAS at http://{host}:{port} (root: {root})")
    if not tokens:
        console.print("[yellow]No tokens configured: open local mode[/yellow]")
    run_server(Path(root), host, port, tokens=parse_token_config(tokens))


@click.group()
def hub() -> None:
    """Run a Hub (HF-compatible) + LFS + CAS service."""


@hub.command("serve")
@click.option(
    "--root",
    "-r",
    type=click.Path(),
    default=".ccbt-hub",
    help="Storage root directory",
)
@click.option("--host", "-H", default="127.0.0.1")
@click.option("--port", "-p", type=int, default=8471)
@click.option(
    "--tokens",
    "-t",
    default=None,
    help='Static tokens, e.g. "alice:read,write;bob:read" (default: open local mode)',
)
def hub_serve(root: str, host: str, port: int, tokens: Optional[str]) -> None:
    """Serve Hub API + Git LFS + CAS in the foreground."""
    console.print(f"Serving Hub+LFS+CAS at http://{host}:{port} (root: {root})")
    if not tokens:
        console.print("[yellow]No tokens configured: open local mode[/yellow]")
    web.run_app(
        create_hub_app(Path(root), tokens=parse_token_config(tokens)),
        host=host,
        port=port,
    )
