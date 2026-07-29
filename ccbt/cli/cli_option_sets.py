"""Reusable Click option decorator sets (short/long parity for heavy commands)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import click

from ccbt.i18n import _

F = TypeVar("F", bound=Callable[..., object])


def compose_click_options(*decorators: Callable[[F], F]) -> Callable[[F], F]:
    """Apply Click option decorators in source order (top option = outermost)."""

    def _compose(f: F) -> F:
        for dec in reversed(decorators):
            f = dec(f)
        return f

    return _compose


# Shared by ``download`` and ``magnet`` after each command's specific options.
# Short letters avoid ``-o/-i/-m/-r`` (command-specific) and ``-F`` (magnet
# ``--select-files``). Expert knobs listed in ``CLI_SHORT_FLAG_EXCEPTIONS`` stay
# long-only so every other flag keeps a single-letter alias.
DOWNLOAD_MAGNET_SHARED_OPTIONS: tuple[Callable[[F], F], ...] = (
    click.option(
        "--no-checkpoint",
        "-N",
        is_flag=True,
        help=_("Disable checkpointing"),
    ),
    click.option(
        "--checkpoint-dir",
        "-C",
        type=click.Path(),
        help=_("Checkpoint directory"),
    ),
    click.option("--listen-port", "-L", type=int, help=_("Listen port")),
    click.option("--max-peers", "-p", type=int, help=_("Maximum global peers")),
    click.option(
        "--max-peers-per-torrent",
        "-P",
        type=int,
        help=_("Maximum peers per torrent"),
    ),
    click.option(
        "--pipeline-depth",
        "-f",
        type=int,
        help=_("Request pipeline depth"),
    ),
    click.option("--block-size-kib", "-B", type=int, help=_("Block size (KiB)")),
    click.option(
        "--connection-timeout",
        "-T",
        type=float,
        help=_("Connection timeout (s)"),
    ),
    click.option(
        "--download-limit",
        "-D",
        type=int,
        help=_("Global download limit (KiB/s)"),
    ),
    click.option(
        "--upload-limit",
        "-U",
        type=int,
        help=_("Global upload limit (KiB/s)"),
    ),
    click.option("--dht-port", "-j", type=int, help=_("DHT port")),
    click.option("--enable-dht", "-y", is_flag=True, help=_("Enable DHT")),
    click.option("--disable-dht", "-Y", is_flag=True, help=_("Disable DHT")),
    click.option(
        "--piece-selection",
        "-S",
        type=click.Choice(["round_robin", "rarest_first", "sequential"]),
    ),
    click.option(
        "--endgame-threshold",
        "-e",
        type=float,
        help=_("Endgame threshold (0..1)"),
    ),
    click.option(
        "--hash-workers",
        "-w",
        type=int,
        help=_("Hash verification workers"),
    ),
    click.option("--disk-workers", "-x", type=int, help=_("Disk I/O workers")),
    click.option("--use-mmap", "-a", is_flag=True, help=_("Use memory mapping")),
    click.option(
        "--no-mmap",
        "-A",
        is_flag=True,
        help=_("Disable memory mapping"),
    ),
    click.option(
        "--mmap-cache-mb",
        "-b",
        type=int,
        help=_("MMap cache size (MB)"),
    ),
    click.option(
        "--write-batch-kib",
        "-g",
        type=int,
        help=_("Write batch size (KiB)"),
    ),
    click.option(
        "--write-buffer-kib",
        "-z",
        type=int,
        help=_("Write buffer size (KiB)"),
    ),
    click.option(
        "--preallocate",
        "-k",
        type=click.Choice(["none", "sparse", "full"]),
    ),
    click.option(
        "--sparse-files",
        "-s",
        is_flag=True,
        help=_("Enable sparse files"),
    ),
    click.option(
        "--no-sparse-files",
        "-K",
        is_flag=True,
        help=_("Disable sparse files"),
    ),
    click.option(
        "--enable-io-uring",
        "-n",
        is_flag=True,
        help=_("Enable io_uring on Linux if available"),
    ),
    click.option(
        "--disable-io-uring",
        "-V",
        is_flag=True,
        help=_("Disable io_uring usage"),
    ),
    click.option(
        "--direct-io",
        "-d",
        is_flag=True,
        help=_("Enable direct I/O for writes when supported"),
    ),
    click.option(
        "--sync-writes",
        "-u",
        is_flag=True,
        help=_("Enable fsync after batched writes"),
    ),
    click.option(
        "--log-level",
        "-l",
        type=click.Choice(["DEBUG", "TRACE", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    ),
    click.option(
        "--enable-metrics",
        "-H",
        is_flag=True,
        help=_("Enable metrics"),
    ),
    click.option(
        "--disable-metrics",
        "-M",
        is_flag=True,
        help=_("Disable metrics"),
    ),
    click.option("--metrics-port", "-O", type=int, help=_("Metrics port")),
    click.option("--enable-ipv6", "-E", is_flag=True, help=_("Enable IPv6")),
    click.option("--disable-ipv6", "-X", is_flag=True, help=_("Disable IPv6")),
    click.option("--enable-tcp", "-t", is_flag=True, help=_("Enable TCP transport")),
    click.option(
        "--disable-tcp",
        "-G",
        is_flag=True,
        help=_("Disable TCP transport"),
    ),
    click.option("--enable-utp", "-q", is_flag=True, help=_("Enable uTP transport")),
    click.option(
        "--disable-utp",
        "-Q",
        is_flag=True,
        help=_("Disable uTP transport"),
    ),
    click.option(
        "--enable-encryption",
        "-c",
        is_flag=True,
        help=_("Enable protocol encryption"),
    ),
    click.option(
        "--disable-encryption",
        "-Z",
        is_flag=True,
        help=_("Disable protocol encryption"),
    ),
    click.option(
        "--tcp-nodelay",
        "-J",
        is_flag=True,
        help=_("Enable TCP_NODELAY"),
    ),
    click.option(
        "--no-tcp-nodelay",
        "-I",
        is_flag=True,
        help=_("Disable TCP_NODELAY"),
    ),
    click.option(
        "--socket-rcvbuf-kib",
        type=int,
        help=_("Socket receive buffer (KiB)"),
    ),
    click.option(
        "--socket-sndbuf-kib",
        type=int,
        help=_("Socket send buffer (KiB)"),
    ),
    click.option(
        "--listen-interface",
        type=str,
        help=_("Listen interface"),
    ),
    click.option("--peer-timeout", type=float, help=_("Peer timeout (s)")),
    click.option("--dht-timeout", type=float, help=_("DHT timeout (s)")),
    click.option(
        "--min-block-size-kib",
        type=int,
        help=_("Minimum block size (KiB)"),
    ),
    click.option(
        "--max-block-size-kib",
        type=int,
        help=_("Maximum block size (KiB)"),
    ),
    click.option(
        "--enable-http-trackers",
        is_flag=True,
        help=_("Enable HTTP trackers"),
    ),
    click.option(
        "--disable-http-trackers",
        is_flag=True,
        help=_("Disable HTTP trackers"),
    ),
    click.option(
        "--enable-udp-trackers",
        is_flag=True,
        help=_("Enable UDP trackers"),
    ),
    click.option(
        "--disable-udp-trackers",
        is_flag=True,
        help=_("Disable UDP trackers"),
    ),
    click.option(
        "--tracker-announce-interval",
        type=float,
        help=_("Tracker announce interval (s)"),
    ),
    click.option(
        "--tracker-scrape-interval",
        type=float,
        help=_("Tracker scrape interval (s)"),
    ),
    click.option("--pex-interval", type=float, help=_("PEX interval (s)")),
    click.option(
        "--endgame-duplicates",
        type=int,
        help=_("Endgame duplicate requests"),
    ),
    click.option(
        "--streaming-mode",
        is_flag=True,
        help=_("Enable streaming mode"),
    ),
    click.option(
        "--first-piece-priority",
        is_flag=True,
        help=_("Prioritize first piece"),
    ),
    click.option(
        "--last-piece-priority",
        is_flag=True,
        help=_("Prioritize last piece"),
    ),
    click.option(
        "--optimistic-unchoke-interval",
        type=float,
        help=_("Optimistic unchoke interval (s)"),
    ),
    click.option(
        "--unchoke-interval",
        type=float,
        help=_("Unchoke interval (s)"),
    ),
    click.option(
        "--peer-choked-hard-timeout-seconds",
        type=float,
        help=_("Hard recovery base timeout if remote still chokes (s)"),
    ),
    click.option(
        "--peer-choked-anchor-timeout-seconds",
        type=float,
        help=_("UNCHOKE wait for seed-anchor peers (s)"),
    ),
    click.option(
        "--peer-choked-solo-grace-seconds",
        type=float,
        help=_("Min grace when solo or no requestable peers (s)"),
    ),
    click.option(
        "--peer-choked-solo-grace-zero-bytes-cap-seconds",
        type=float,
        help=_("Cap solo grace when zero bytes/outstanding (0=off)"),
    ),
    click.option(
        "--metrics-interval",
        type=float,
        help=_("Metrics interval (s)"),
    ),
    click.option(
        "--enable-v2",
        "-R",
        "enable_v2",
        is_flag=True,
        help=_("Enable Protocol v2 (BEP 52)"),
    ),
    click.option(
        "--disable-v2",
        "-W",
        "disable_v2",
        is_flag=True,
        help=_("Disable Protocol v2 (BEP 52)"),
    ),
    click.option(
        "--prefer-v2",
        "prefer_v2",
        is_flag=True,
        help=_("Prefer Protocol v2 when available"),
    ),
    click.option(
        "--v2-only",
        "v2_only",
        is_flag=True,
        help=_("Use Protocol v2 only (disable v1)"),
    ),
)
