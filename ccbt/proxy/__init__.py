"""HTTP proxy support for ccBitTorrent.

This module provides proxy support with authentication for tracker requests,
peer connections, and WebSeed downloads.
"""

from __future__ import annotations

from ccbt.proxy.auth import ProxyAuth
from ccbt.proxy.client import ProxyClient
from ccbt.proxy.exceptions import (
    ProxyAuthError,
    ProxyConnectionError,
    ProxyError,
)

__all__ = [
    "ProxyAuth",
    "ProxyAuthError",
    "ProxyClient",
    "ProxyConnectionError",
    "ProxyError",
]
