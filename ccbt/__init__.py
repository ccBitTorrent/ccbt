"""ccBitTorrent - A BitTorrent client implementation."""

from __future__ import annotations

import importlib

__version__ = "0.0.1"

# Ensure a default asyncio event loop exists on import for libraries/tests that
# construct futures outside of a running loop (e.g., asyncio.Future()).
# This avoids RuntimeError: There is no current event loop in thread 'MainThread'.
try:
    import asyncio
    import warnings

    class _SafeEventLoopPolicy(asyncio.AbstractEventLoopPolicy):
        """Wrapper policy that ensures a loop exists when requested."""

        def __init__(self, base: asyncio.AbstractEventLoopPolicy):
            self._base = base

        def get_event_loop(self):  # type: ignore[override]
            try:
                return asyncio.get_running_loop()
            except RuntimeError:
                # No running loop - try to get thread-default loop from base policy first.
                # Python 3.12+ deprecates asyncio.get_event_loop() when no loop is set;
                # suppress only for this delegation so we still return a pytest-managed loop.
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    try:
                        return self._base.get_event_loop()
                    except RuntimeError:
                        # Base policy also can't provide a loop - create new one
                        # This is the fallback for user code that needs a loop
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        return loop

        def set_event_loop(self, loop):  # type: ignore[override]
            return self._base.set_event_loop(loop)

        def new_event_loop(self):  # type: ignore[override]
            return self._base.new_event_loop()

        # Python 3.12+: get_running_loop is used in many places; delegate directly
        def get_running_loop(self):  # type: ignore[override]
            return self._base.get_running_loop()  # type: ignore[attr-defined]  # pragma: no cover - Base policy method may not exist on all platforms (Windows ProactorEventLoopPolicy), platform-specific delegation

        # Child watcher methods (posix); delegate if present
        def get_child_watcher(self):  # type: ignore[override]
            def _raise_not_implemented():  # pragma: no cover - Nested function definition, only executed if base lacks method (platform-specific):
                raise NotImplementedError  # pragma: no cover - NotImplementedError path, tested via test_get_child_watcher_no_base

            if hasattr(
                self._base, "get_child_watcher"
            ):  # pragma: no cover - Base policy with child watcher, platform-specific
                return self._base.get_child_watcher()  # pragma: no cover - Same context
            return _raise_not_implemented()  # pragma: no cover - Same context

        def set_child_watcher(self, watcher):  # type: ignore[override]
            def _raise_not_implemented():  # pragma: no cover - Nested function definition, only executed if base lacks method (platform-specific):
                raise NotImplementedError  # pragma: no cover - NotImplementedError path, tested via test_set_child_watcher_no_base

            if hasattr(
                self._base, "set_child_watcher"
            ):  # pragma: no cover - Base policy with child watcher, platform-specific
                return self._base.set_child_watcher(
                    watcher
                )  # pragma: no cover - Same context
            return _raise_not_implemented()  # pragma: no cover - Same context

    # Note: On Windows, use SelectorEventLoop instead of ProactorEventLoop
    # ProactorEventLoop has known bugs with UDP sockets (WinError 10022)
    # This must be set BEFORE wrapping with _SafeEventLoopPolicy
    import sys

    if sys.platform == "win32":
        current_policy = asyncio.get_event_loop_policy()
        # Check if we're using ProactorEventLoopPolicy (the default on Windows)
        # Handle both direct policy and wrapped policy
        base_policy = current_policy
        if hasattr(current_policy, "_base"):
            base_policy = current_policy._base  # noqa: SLF001 - Windows event loop policy workaround

        # Replace ProactorEventLoopPolicy with WindowsSelectorEventLoopPolicy
        if isinstance(base_policy, asyncio.WindowsProactorEventLoopPolicy):
            selector_policy = asyncio.WindowsSelectorEventLoopPolicy()
            asyncio.set_event_loop_policy(selector_policy)

    # Install safe policy once
    try:
        base_policy = asyncio.get_event_loop_policy()
        if not isinstance(
            base_policy, _SafeEventLoopPolicy
        ):  # pragma: no cover - Policy setup already done on first import, difficult to test second import
            asyncio.set_event_loop_policy(
                _SafeEventLoopPolicy(base_policy)
            )  # pragma: no cover - Same context
    except (
        Exception
    ):  # pragma: no cover - Exception handling during policy setup, defensive fallback
        # As a fallback, ensure a loop is set at import time
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.get_event_loop()  # pragma: no cover - Same context
        except RuntimeError:  # pragma: no cover - Same context
            loop = asyncio.new_event_loop()  # pragma: no cover - Same context
            asyncio.set_event_loop(loop)  # pragma: no cover - Same context
except Exception:  # nosec B110 - If asyncio is unavailable or any error occurs, silently continue.  # pragma: no cover - Exception handling if asyncio unavailable, defensive
    # If asyncio is unavailable or any error occurs, silently continue.
    pass  # pragma: no cover - Same context

# Backward compatibility: Re-export commonly used modules from new locations
# This allows old imports like "from ccbt.bencode import ..." to continue working
from ccbt import discovery
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
from ccbt.peer import async_peer_connection, peer_connection
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
    "dht",
    # Discovery
    "discovery",
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


# Lazy attribute access for undefined attributes
def __getattr__(name: str):  # pragma: no cover - import-time plumbing
    if name in {
        "config",
        "core",
        "discovery",
        "peer",
        "piece",
        "session",
        "storage",
        "utils",
    }:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)
