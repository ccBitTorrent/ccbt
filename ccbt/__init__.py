"""ccBitTorrent - A BitTorrent client implementation."""

from __future__ import annotations

__version__ = "0.1.0"

# Ensure a default asyncio event loop exists on import for libraries/tests that
# construct futures outside of a running loop (e.g., asyncio.Future()).
# This avoids RuntimeError: There is no current event loop in thread 'MainThread'.
try:
    import asyncio

    class _SafeEventLoopPolicy(asyncio.AbstractEventLoopPolicy):
        """Wrapper policy that ensures a loop exists when requested."""

        def __init__(self, base: asyncio.AbstractEventLoopPolicy):
            self._base = base

        def get_event_loop(self):  # type: ignore[override]
            try:
                return asyncio.get_running_loop()
            except RuntimeError:
                # Create a new event loop if none exists
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop

        def set_event_loop(self, loop):  # type: ignore[override]
            return self._base.set_event_loop(loop)

        def new_event_loop(self):  # type: ignore[override]
            return self._base.new_event_loop()

        # Python 3.12+: get_running_loop is used in many places; delegate directly
        def get_running_loop(self):  # type: ignore[override]
            return self._base.get_running_loop()  # type: ignore[attr-defined]

        # Child watcher methods (posix); delegate if present
        def get_child_watcher(self):  # type: ignore[override]
            def _raise_not_implemented():
                raise NotImplementedError  # pragma: no cover

            if hasattr(self._base, "get_child_watcher"):
                return self._base.get_child_watcher()  # pragma: no cover
            return _raise_not_implemented()

        def set_child_watcher(self, watcher):  # type: ignore[override]
            def _raise_not_implemented():
                raise NotImplementedError  # pragma: no cover

            if hasattr(self._base, "set_child_watcher"):
                return self._base.set_child_watcher(watcher)  # pragma: no cover
            return _raise_not_implemented()

    # Install safe policy once
    try:
        base_policy = asyncio.get_event_loop_policy()
        if not isinstance(base_policy, _SafeEventLoopPolicy):
            asyncio.set_event_loop_policy(_SafeEventLoopPolicy(base_policy))
    except Exception:
        # As a fallback, ensure a loop is set at import time
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
except Exception:  # nosec B110 - If asyncio is unavailable or any error occurs, silently continue.
    # If asyncio is unavailable or any error occurs, silently continue.
    pass

# Backward compatibility: Re-export commonly used modules from new locations
# This allows old imports like "from ccbt.bencode import ..." to continue working
from ccbt.config import config
from ccbt.config.config import Config, ConfigManager, get_config, init_config
from ccbt.core import bencode, magnet, torrent

# Re-export commonly used classes/functions for backward compatibility
from ccbt.core.bencode import BencodeDecoder, BencodeEncoder, decode, encode
from ccbt.core.magnet import (
    MagnetInfo,
    build_minimal_torrent_data,
    build_torrent_data_from_metadata,
    parse_magnet,
)
from ccbt.core.torrent import TorrentParser
from ccbt.discovery import dht, pex, tracker
from ccbt.peer import async_peer_connection, peer, peer_connection
from ccbt.piece import (
    async_metadata_exchange,
    async_piece_manager,
    metadata_exchange,
    piece_manager,
)
from ccbt.session.session import AsyncSessionManager, SessionManager
from ccbt.storage import checkpoint, file_assembler
from ccbt.utils import (
    events,
    exceptions,
    logging_config,
    metrics,
    network_optimizer,
    resilience,
)

# Note: For complete backward compatibility, importing as modules
# (e.g., "from ccbt import bencode") will work via the imports above

__all__ = [
    "AsyncSessionManager",
    "BencodeDecoder",
    "BencodeEncoder",
    "Config",
    "ConfigManager",
    "MagnetInfo",
    "SessionManager",
    "TorrentParser",
    "__version__",
    # Piece
    "async_metadata_exchange",
    "async_peer_connection",
    "async_piece_manager",
    # Core
    "bencode",
    "build_minimal_torrent_data",
    "build_torrent_data_from_metadata",
    # Storage
    "checkpoint",
    # Config
    "config",
    "decode",
    # Discovery
    "dht",
    "encode",
    # Utils
    "events",
    "exceptions",
    "file_assembler",
    "get_config",
    "init_config",
    "logging_config",
    "magnet",
    "metadata_exchange",
    "metrics",
    "network_optimizer",
    "parse_magnet",
    # Peer
    "peer",
    "peer_connection",
    "pex",
    "piece_manager",
    "resilience",
    # Session
    "session",
    "torrent",
    "tracker",
]


# Lazy attribute access to prefer submodules over similarly named attributes
def __getattr__(name: str):  # pragma: no cover - import-time plumbing
    if name == "async_main":
        import importlib

        return importlib.import_module("ccbt.async_main")
    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)


# Ensure attribute binding prefers submodule even in long-lived interpreters
try:  # pragma: no cover - import-time plumbing
    import importlib as _importlib

    async_main = _importlib.import_module("ccbt.async_main")
except Exception:
    pass

# Backward compat: if async_main was imported as a function elsewhere, attach
# commonly patched attributes so patch('ccbt.async_main.X') works.
try:  # pragma: no cover - import-time plumbing
    import types as _types

    if isinstance(globals().get("async_main"), _types.FunctionType):
        import ccbt.session.async_main as _am
        from ccbt.config.config import get_config as _get_config
        from ccbt.core.magnet import (
            build_minimal_torrent_data as _build_min,
        )
        from ccbt.core.magnet import (
            parse_magnet as _parse_magnet,
        )
        from ccbt.peer.async_peer_connection import (
            AsyncPeerConnectionManager as _APCM,  # noqa: N814
        )
        from ccbt.piece.async_piece_manager import (
            AsyncPieceManager as _APM,  # noqa: N814
        )

        async_main.get_config = _get_config
        async_main.AsyncPeerConnectionManager = _APCM
        async_main.AsyncPieceManager = _APM
        async_main.parse_magnet = _parse_magnet
        async_main.build_minimal_torrent_data = _build_min
        async_main.AsyncDownloadManager = _am.AsyncDownloadManager
except Exception:
    pass
