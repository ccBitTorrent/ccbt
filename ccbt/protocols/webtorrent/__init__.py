"""WebTorrent protocol package.

This package contains WebTorrent protocol implementation including
WebRTC connection management and signaling.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

__all__ = [
    "WebRTCConnectionManager",
    "WebTorrentProtocol",
]

# Import WebTorrentProtocol directly from the .py file to avoid circular imports
# This handles the module/package name conflict (webtorrent.py vs webtorrent/)
try:
    # Get the parent directory and load webtorrent.py directly
    parent_dir = Path(__file__).parent.parent
    webtorrent_file = parent_dir / "webtorrent.py"

    if webtorrent_file.exists():
        spec = importlib.util.spec_from_file_location(
            "ccbt.protocols.webtorrent_module", webtorrent_file
        )
        if spec and spec.loader:
            webtorrent_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(webtorrent_module)
            WebTorrentProtocol = getattr(webtorrent_module, "WebTorrentProtocol", None)
        else:
            WebTorrentProtocol = None
    else:
        WebTorrentProtocol = None
except (
    ImportError,
    AttributeError,
    Exception,
):  # pragma: no cover - defensive import fallback
    WebTorrentProtocol = None  # type: ignore[assignment, misc]

# Import will be conditional to handle missing aiortc gracefully
try:
    from ccbt.protocols.webtorrent.webrtc_manager import WebRTCConnectionManager
except ImportError:  # pragma: no cover - defensive import fallback
    # aiortc not installed - create a placeholder
    WebRTCConnectionManager = None  # type: ignore[assignment, misc]
