"""Session orchestration and lifecycle management.

This module handles multi-torrent session management and async operations.
"""

from __future__ import annotations

from ccbt.session.async_main import AsyncDownloadManager as AsyncDownloadManagerSession
from ccbt.session.async_main import main as async_main
from ccbt.session.session import (
    AsyncSessionManager,
    AsyncTorrentSession,
    SessionManager,
)


# Lazy import to avoid circular dependencies
def __getattr__(name):
    if name == "AsyncDHTClient":
        from ccbt.discovery.dht import AsyncDHTClient

        return AsyncDHTClient
    if name == "TorrentParser":
        from ccbt.core.torrent import TorrentParser

        return TorrentParser
    if name == "parse_magnet":
        from ccbt.core.magnet import parse_magnet

        return parse_magnet
    if name == "build_minimal_torrent_data":
        from ccbt.core.magnet import build_minimal_torrent_data

        return build_minimal_torrent_data
    if name == "Path":
        from pathlib import Path

        return Path
    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)


__all__ = [
    "AsyncDownloadManagerSession",
    "AsyncSessionManager",
    "AsyncTorrentSession",
    "SessionManager",
    "async_main",
]
