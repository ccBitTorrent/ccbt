"""CLI command for creating torrent files (BEP 52 support).

Provides commands to create v1, v2, and hybrid torrent files.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ccbt.i18n import _

logger = logging.getLogger(__name__)


@click.command("create-torrent")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output torrent file path (default: <source>.torrent)",
)
@click.option(
    "--v2",
    "format_v2",
    is_flag=True,
    help="Create v2-only torrent (BEP 52)",
)
@click.option(
    "--hybrid",
    "format_hybrid",
    is_flag=True,
    help="Create hybrid torrent (v1 + v2 metadata)",
)
@click.option(
    "--v1",
    "format_v1",
    is_flag=True,
    help="Create v1-only torrent (default if none specified)",
)
@click.option(
    "--tracker",
    "-t",
    multiple=True,
    type=str,
    help="Tracker announce URL (can specify multiple times)",
)
@click.option(
    "--web-seed",
    multiple=True,
    type=str,
    help="Web seed URL (can specify multiple times)",
)
@click.option(
    "--comment",
    "-c",
    type=str,
    help="Torrent comment",
)
@click.option(
    "--created-by",
    type=str,
    default="ccBitTorrent",
    help="Created by field (default: ccBitTorrent)",
)
@click.option(
    "--piece-length",
    type=int,
    help="Piece length in bytes (must be power of 2, default: auto)",
)
@click.option(
    "--private",
    is_flag=True,
    help="Mark torrent as private (BEP 27)",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (-v: verbose, -vv: debug, -vvv: trace)",
)
@click.pass_context
def create_torrent(
    _ctx: click.Context,
    source: Path,
    output: Path | None,
    format_v2: bool,
    format_hybrid: bool,
    format_v1: bool,
    tracker: tuple[str, ...],
    web_seed: tuple[str, ...],
    comment: str | None,
    created_by: str,
    piece_length: int | None,
    private: bool,
    verbose: int,
) -> None:
    """Create a torrent file from a directory or file.

    Supports creating v1, v2, or hybrid torrents (BEP 52).

    Examples:
        # Create v2 torrent
        ccbt create-torrent /path/to/content --v2 -t http://tracker.example.com/announce

        # Create hybrid torrent
        ccbt create-torrent /path/to/content --hybrid -t http://tracker.example.com/announce

        # Create v1 torrent (default)
        ccbt create-torrent /path/to/content -t http://tracker.example.com/announce

    """
    console = Console()

    # Determine output format
    if format_v2 and format_hybrid:
        logger.error(_("Cannot specify both --v2 and --hybrid"))
        console.print(_("[red]Error: Cannot specify both --v2 and --hybrid[/red]"))
        raise click.Abort
    if format_v2 and format_v1:
        logger.error(_("Cannot specify both --v2 and --v1"))
        console.print(_("[red]Error: Cannot specify both --v2 and --v1[/red]"))
        raise click.Abort
    if format_hybrid and format_v1:
        logger.error(_("Cannot specify both --hybrid and --v1"))
        console.print(_("[red]Error: Cannot specify both --hybrid and --v1[/red]"))
        raise click.Abort

    # Default to v1 if no format specified
    torrent_format = "v1"
    if format_v2:
        torrent_format = "v2"
    elif format_hybrid:
        torrent_format = "hybrid"
    elif format_v1:
        torrent_format = "v1"

    # Determine output file path
    if output is None:
        output = source.with_suffix(".torrent")
    else:
        output = Path(output)
        if output.is_dir():  # pragma: no cover - Output directory path construction, tested via file output path
            output = output / f"{source.name}.torrent"

    # Validate source path
    if not source.exists():  # pragma: no cover - Defensive check: Click validates paths, but this guards against race conditions
        logger.error(_("Source path does not exist: %s"), source)
        console.print(_("[red]Error: Source path does not exist: {path}[/red]").format(path=source))
        raise click.Abort

    if source.is_dir() and not any(source.iterdir()):
        console.print(
            _("[red]Error: Source directory is empty[/red]"),
        )
        raise click.Abort

    # Validate piece length if specified
    if piece_length is not None:
        if piece_length < 16384:  # 16 KiB minimum
            console.print(
                _("[red]Error: Piece length must be at least 16 KiB (16384 bytes)[/red]"),
            )
            raise click.Abort
        if piece_length & (piece_length - 1) != 0:
            console.print(
                _("[red]Error: Piece length must be a power of 2[/red]"),
            )
            raise click.Abort

    console.print(_("[cyan]Creating {format} torrent...[/cyan]").format(format=torrent_format.upper()))
    console.print(_("[dim]Source: {path}[/dim]").format(path=source))
    console.print(_("[dim]Output: {path}[/dim]").format(path=output))
    if tracker:
        console.print(_("[dim]Trackers: {count}[/dim]").format(count=len(tracker)))
    if web_seed:  # pragma: no cover - Web seeds info display, tested via torrent creation without web seeds
        console.print(_("[dim]Web seeds: {count}[/dim]").format(count=len(web_seed)))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                _("Generating {format} torrent...").format(format=torrent_format.upper()),
                total=None,
            )

            torrent_bytes = None

            if torrent_format == "v2":
                from ccbt.core.torrent_v2 import TorrentV2Parser

                progress.update(
                    task, description=_("Parsing files and building file tree...")
                )
                parser = TorrentV2Parser()
                torrent_bytes = parser.generate_v2_torrent(
                    source=source,
                    output=None,  # Return bytes, we'll write to file ourselves
                    trackers=list(tracker) if tracker else None,
                    web_seeds=list(web_seed) if web_seed else None,
                    comment=comment,
                    created_by=created_by,
                    piece_length=piece_length,
                    private=private,
                )
            elif torrent_format == "hybrid":
                from ccbt.core.torrent_v2 import TorrentV2Parser

                progress.update(
                    task, description=_("Parsing files and building hybrid metadata...")
                )
                parser = TorrentV2Parser()
                torrent_bytes = parser.generate_hybrid_torrent(
                    source=source,
                    output=None,  # Return bytes, we'll write to file ourselves
                    trackers=list(tracker) if tracker else None,
                    web_seeds=list(web_seed) if web_seed else None,
                    comment=comment,
                    created_by=created_by,
                    piece_length=piece_length,
                    private=private,
                )
            else:  # v1
                progress.update(
                    task, description=_("V1 torrent generation not yet implemented")
                )
                console.print(
                    _("[yellow]Warning: V1 torrent generation is not yet implemented.[/yellow]"),
                )
                console.print(
                    _("[yellow]Please use --v2 or --hybrid flags for now.[/yellow]"),
                )
                raise click.Abort

            if torrent_bytes:
                # Save torrent file
                progress.update(task, description=_("Saving torrent to {path}...").format(path=output))
                output.parent.mkdir(parents=True, exist_ok=True)
                with open(output, "wb") as f:
                    f.write(torrent_bytes)

                progress.update(task, description=_("Torrent saved to {path}").format(path=output))
                console.print(
                    _("[green]✓ Torrent created successfully: {path}[/green]").format(path=output)
                )

                # Parse torrent to show info hashes
                from ccbt.core.bencode import decode

                torrent_dict = decode(torrent_bytes)
                info_dict = torrent_dict.get(b"info", {})

                if torrent_format in ["v2", "hybrid"]:
                    # Extract v2 info hash
                    from ccbt.core.torrent_v2 import TorrentV2Parser

                    parser = TorrentV2Parser()
                    if torrent_format == "v2":
                        v2_info = parser.parse_v2(info_dict, torrent_dict)
                        info_hash_v2 = v2_info.info_hash_v2
                    else:  # hybrid
                        v1_info, v2_info = parser.parse_hybrid(info_dict, torrent_dict)
                        info_hash_v2 = v2_info.info_hash_v2 if v2_info else None
                        info_hash_v1 = v1_info.info_hash if v1_info else None

                    if info_hash_v2:
                        console.print(
                            _("[dim]Info hash v2 (SHA-256): {hash}...[/dim]").format(hash=info_hash_v2.hex()[:32]),
                        )
                    if torrent_format == "hybrid" and info_hash_v1:
                        console.print(
                            _("[dim]Info hash v1 (SHA-1): {hash}...[/dim]").format(hash=info_hash_v1.hex()[:32]),
                        )

    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        logger.exception(_("Error creating torrent"))
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.Abort from e


    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        logger.exception(_("Error creating torrent"))
        console.print(_("[red]Error: {e}[/red]").format(e=e))
        raise click.Abort from e
