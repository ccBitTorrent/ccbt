"""Tonic file generator CLI command.

This module provides CLI functionality for generating .tonic files from folders
with options for sync mode, source peers, allowlist, and git refs.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ccbt.core.tonic import TonicFile
from ccbt.core.tonic_link import generate_tonic_link
from ccbt.i18n import _
from ccbt.models import XetFileMetadata, XetTorrentMetadata
from ccbt.security.xet_allowlist import XetAllowlist
from ccbt.storage.git_versioning import GitVersioning
from ccbt.storage.xet_chunking import GearhashChunker
from ccbt.storage.xet_hashing import XetHasher

logger = logging.getLogger(__name__)


async def generate_tonic_from_folder(
    folder_path: str | Path,
    output_path: str | Path | None = None,
    sync_mode: str = "best_effort",
    source_peers: list[str] | None = None,
    allowlist_path: str | Path | None = None,
    git_ref: str | None = None,
    announce: str | None = None,
    announce_list: list[list[str]] | None = None,
    comment: str | None = None,
    generate_link: bool = False,
) -> tuple[bytes, str | None]:
    """Generate .tonic file from folder.

    Args:
        folder_path: Path to folder
        output_path: Output .tonic file path (None = auto-generate)
        sync_mode: Synchronization mode
        source_peers: Designated source peer IDs
        allowlist_path: Path to allowlist file
        git_ref: Git commit hash/ref to track
        announce: Primary tracker URL
        announce_list: List of tracker tiers
        comment: Optional comment
        generate_link: Whether to also generate tonic?: link

    Returns:
        Tuple of (tonic_file_bytes, tonic_link_string_or_none)

    """
    folder = Path(folder_path).resolve()
    if not folder.exists() or not folder.is_dir():
        msg = _("Folder not found: {folder}").format(folder=folder)
        raise ValueError(msg)

    # Initialize components
    chunker = GearhashChunker()
    hasher = XetHasher()

    # Get folder name
    folder_name = folder.name

    # Collect files and calculate chunks
    file_metadata_list: list[XetFileMetadata] = []
    all_chunk_hashes: set[bytes] = set()

    console = Console()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(_("Scanning folder and calculating chunks..."), total=None)

        # Scan folder
        for file_path in folder.rglob("*"):
            if file_path.is_file():
                try:
                    relative_path = str(file_path.relative_to(folder))

                    # Read file and chunk it
                    with open(file_path, "rb") as f:
                        file_data = f.read()

                    # Chunk file
                    chunk_hashes: list[bytes] = []
                    for chunk_data in chunker.chunk(file_data):
                        chunk_hash = hasher.compute_chunk_hash(chunk_data)
                        chunk_hashes.append(chunk_hash)
                        all_chunk_hashes.add(chunk_hash)

                    # Calculate file hash (Merkle root)
                    file_hash = hasher.build_merkle_tree_from_hashes(chunk_hashes)

                    file_metadata = XetFileMetadata(
                        file_path=relative_path,
                        file_hash=file_hash,
                        chunk_hashes=chunk_hashes,
                        total_size=len(file_data),
                    )

                    file_metadata_list.append(file_metadata)

                except Exception as e:
                    logger.warning(_("Error processing file %s: %s"), file_path, e)
                    continue

        progress.update(task, completed=True)

    # Get git refs if git versioning enabled
    git_refs: list[str] | None = None
    git_versioning = GitVersioning(folder_path=folder)
    if git_versioning.is_git_repo():
        if git_ref:
            git_refs = [git_ref]
        else:
            current_ref = await git_versioning.get_current_commit()
            if current_ref:
                git_refs = [current_ref]
                # Also get recent refs
                recent_refs = await git_versioning.get_commit_refs(max_refs=10)
                if recent_refs:
                    git_refs = recent_refs

    # Get allowlist hash if allowlist provided
    allowlist_hash: bytes | None = None
    if allowlist_path:
        allowlist = XetAllowlist(allowlist_path=allowlist_path)
        await allowlist.load()
        allowlist_hash = allowlist.get_allowlist_hash()

    # Build XET metadata
    xet_metadata = XetTorrentMetadata(
        chunk_hashes=list(all_chunk_hashes),
        file_metadata=file_metadata_list,
        piece_metadata=[],  # Will be populated if piece metadata available
        xorb_hashes=[],  # Will be populated if xorb hashes available
    )

    # Create tonic file
    tonic_file = TonicFile()
    tonic_data = tonic_file.create(
        folder_name=folder_name,
        xet_metadata=xet_metadata,
        git_refs=git_refs,
        sync_mode=sync_mode,
        source_peers=source_peers,
        allowlist_hash=allowlist_hash,
        announce=announce,
        announce_list=announce_list,
        comment=comment,
    )

    # Calculate info hash (parse the data we just created)
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(delete=False, suffix=".tonic") as tmp_file:
        tmp_file.write(tonic_data)
        tmp_path = tmp_file.name

    try:
        parsed_data = tonic_file.parse(tmp_path)
        info_hash = tonic_file.get_info_hash(parsed_data)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Save to file if output path specified
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(tonic_data)
        console.print(_("[green]✓[/green] Generated .tonic file: {file}").format(file=output_file))

    # Generate link if requested
    tonic_link: str | None = None
    if generate_link:
        tonic_link = generate_tonic_link(
            info_hash=info_hash,
            display_name=folder_name,
            trackers=[announce] if announce else None,
            git_refs=git_refs,
            sync_mode=sync_mode,
            source_peers=source_peers,
            allowlist_hash=allowlist_hash,
        )
        console.print(_("[green]✓[/green] Generated tonic?: link:"))
        console.print(f"  {tonic_link}")

    return tonic_data, tonic_link


@click.command("generate")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(),
    help="Output .tonic file path (default: <folder_name>.tonic)",
)
@click.option(
    "--sync-mode",
    type=click.Choice(["designated", "best_effort", "broadcast", "consensus"]),
    default="best_effort",
    help="Synchronization mode",
)
@click.option(
    "--source-peers",
    help="Comma-separated list of designated source peer IDs",
)
@click.option(
    "--allowlist",
    "allowlist_path",
    type=click.Path(),
    help="Path to allowlist file",
)
@click.option(
    "--git-ref",
    help="Git commit hash/ref to track (default: current HEAD)",
)
@click.option(
    "--announce",
    help="Primary tracker announce URL",
)
@click.option(
    "--generate-link",
    is_flag=True,
    help="Also generate tonic?: link",
)
@click.pass_context
def tonic_generate(
    ctx,
    folder_path: str,
    output_path: str | None,
    sync_mode: str,
    source_peers: str | None,
    allowlist_path: str | None,
    git_ref: str | None,
    announce: str | None,
    generate_link: bool,
) -> None:
    """Generate .tonic file from folder."""
    console = Console()

    # Parse source peers
    source_peers_list: list[str] | None = None
    if source_peers:
        source_peers_list = [p.strip() for p in source_peers.split(",") if p.strip()]

    # Determine output path
    if not output_path:
        folder_name = Path(folder_path).name
        output_path = f"{folder_name}.tonic"

    try:
        # Generate tonic file
        asyncio.run(
            generate_tonic_from_folder(
                folder_path=folder_path,
                output_path=output_path,
                sync_mode=sync_mode,
                source_peers=source_peers_list,
                allowlist_path=allowlist_path,
                git_ref=git_ref,
                announce=announce,
                generate_link=generate_link,
            )
        )

    except Exception as e:
        console.print(_("[red]Error generating .tonic file: {e}[/red]").format(e=e))
        logger.exception(_("Failed to generate .tonic file"))
        raise click.Abort() from e


