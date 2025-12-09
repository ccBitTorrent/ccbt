"""CLI commands for tracker scraping (BEP 48).

Provides commands to manually scrape trackers and view cached scrape results.
"""

from __future__ import annotations

import asyncio
import logging

import click
from rich.console import Console
from rich.table import Table

from ccbt.cli.main import _get_executor
from ccbt.i18n import _

logger = logging.getLogger(__name__)


@click.group("scrape", help="Tracker scrape commands (BEP 48)")
@click.pass_context
def scrape(ctx):
    """Manage tracker scraping."""


@scrape.command("torrent")
@click.argument("info_hash", type=str)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force scrape even if recently scraped",
)
@click.pass_context
def scrape_torrent(_ctx, info_hash: str, force: bool):
    """Scrape tracker for torrent statistics.

    Args:
        _ctx: Click context (unused but required by decorator)
        info_hash: Torrent info hash (hex format, 40 characters)
        force: Force scrape even if cached result exists

    """
    console = Console()

    # Validate info_hash format
    invalid_hash_msg = _("Invalid info hash format")
    if len(info_hash) != 40:
        console.print(_("[red]Error: Info hash must be 40 hex characters[/red]"))
        raise click.ClickException(invalid_hash_msg)

    async def _scrape_torrent() -> None:
        """Async helper for scrape torrent."""
        # Get executor (scrape commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                _(
                    "Daemon is not running. Scrape commands require the daemon to be running.\n"
                    "Start the daemon with: 'btbt daemon start'"
                )
            )

        try:
            # Execute command via executor
            result = await executor.execute(
                "scrape.torrent",
                info_hash=info_hash,
                force=force,
            )

            if not result.success:
                error_msg = result.error or _("Failed to scrape torrent")
                raise click.ClickException(error_msg)

            scrape_result = result.data["result"]

            table = Table(title=_("Scrape Results"))
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Info Hash", scrape_result.info_hash)
            table.add_row("Seeders", str(scrape_result.seeders))
            table.add_row("Leechers", str(scrape_result.leechers))
            table.add_row("Completed", str(scrape_result.completed))
            table.add_row("Last Scrape", f"{scrape_result.last_scrape_time:.0f}")
            table.add_row("Scrape Count", str(scrape_result.scrape_count))

            console.print(table)
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_scrape_torrent())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e


@scrape.command("list")
@click.pass_context
def scrape_list(_ctx):
    """List all cached scrape results.

    Args:
        _ctx: Click context (unused but required by decorator)

    """
    console = Console()

    async def _list_scrape_results() -> None:
        """Async helper for scrape list."""
        # Get executor (scrape commands require daemon)
        executor, is_daemon = await _get_executor()

        if not executor or not is_daemon:
            raise click.ClickException(
                _(
                    "Daemon is not running. Scrape commands require the daemon to be running.\n"
                    "Start the daemon with: 'btbt daemon start'"
                )
            )

        try:
            # Execute command via executor
            result = await executor.execute("scrape.list")

            if not result.success:
                error_msg = result.error or _("Failed to list scrape results")
                raise click.ClickException(error_msg)

            scrape_list_response = result.data["results"]

            if not scrape_list_response.results:
                console.print(_("[yellow]No cached scrape results[/yellow]"))
                return

            table = Table(title=_("Cached Scrape Results"))
            table.add_column("Info Hash", style="cyan")
            table.add_column("Seeders", style="green")
            table.add_column("Leechers", style="yellow")
            table.add_column("Completed", style="blue")
            table.add_column("Last Scrape", style="magenta")

            for scrape_result in sorted(
                scrape_list_response.results,
                key=lambda r: r.last_scrape_time,
                reverse=True,
            ):
                table.add_row(
                    scrape_result.info_hash,
                    str(scrape_result.seeders),
                    str(scrape_result.leechers),
                    str(scrape_result.completed),
                    f"{scrape_result.last_scrape_time:.0f}",
                )

            console.print(table)
        finally:
            # Close IPC client if using daemon adapter
            if hasattr(executor.adapter, "ipc_client"):
                await executor.adapter.ipc_client.close()

    try:
        asyncio.run(_list_scrape_results())
    except click.ClickException:
        raise
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.ClickException(str(e)) from e
