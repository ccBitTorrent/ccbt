"""Top-level async_main shim for tests and CLI compatibility.

Re-export everything from ccbt.session.async_main so tests can patch
ccbt.async_main.* symbols and have them affect the actual module.
"""

from __future__ import annotations

# Explicit re-exports for commonly patched symbols to ensure they're accessible
from ccbt.config.config import get_config
from ccbt.core.magnet import build_minimal_torrent_data, parse_magnet
from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager
from ccbt.piece.async_piece_manager import AsyncPieceManager

# Import everything from the actual module
from ccbt.session.async_main import *  # noqa: F403
from ccbt.session.async_main import (
    AsyncDownloadManager,
    download_magnet,
    download_torrent,
    main,
    run_daemon,
)

# Ensure these are in the module namespace for patching
__all__ = [
    "AsyncDownloadManager",
    "AsyncPeerConnectionManager",
    "AsyncPieceManager",
    "build_minimal_torrent_data",
    "download_magnet",
    "download_torrent",
    "get_config",
    "main",
    "parse_magnet",
    "run_daemon",
]
