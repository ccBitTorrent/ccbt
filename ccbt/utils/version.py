"""Version management utilities for ccBitTorrent.

This module provides functions to:
- Retrieve the installed package version using importlib
- Generate peer_id prefixes based on version
- Get client names for network protocol and UI
- Format user-agent strings
"""

from __future__ import annotations

import importlib.metadata
import re
from typing import Final

# Client names
NETWORK_CLIENT_NAME: Final[str] = "btonic"
UI_CLIENT_NAME: Final[str] = "ccBitTorrent"


def get_version() -> str:
    """Get the installed package version.

    Uses importlib.metadata to get version from installed package.
    Falls back to ccbt.__version__ if metadata is unavailable.

    Returns:
        Version string (e.g., "0.0.1", "0.1.0", "1.2.3")
    """
    try:
        # Try to get version from installed package metadata
        return importlib.metadata.version("ccbt")
    except importlib.metadata.PackageNotFoundError:
        # Fallback to __version__ attribute
        try:
            import ccbt

            return getattr(ccbt, "__version__", "0.0.1")
        except ImportError:
            return "0.0.1"


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse version string into major, minor, patch components.

    Args:
        version: Version string (e.g., "0.0.1", "1.2.3")

    Returns:
        Tuple of (major, minor, patch) integers

    Raises:
        ValueError: If version format is invalid
    """
    # Remove any pre-release or build metadata (e.g., "0.1.0-alpha.1" -> "0.1.0")
    version_clean = re.split(r"[-+]", version)[0]

    parts = version_clean.split(".")
    if len(parts) < 2:
        msg = f"Invalid version format: {version} (expected MAJOR.MINOR.PATCH)"
        raise ValueError(msg)

    major = int(parts[0])
    minor = int(parts[1])
    patch = int(parts[2]) if len(parts) > 2 else 0

    return (major, minor, patch)


def get_peer_id_prefix(version: str | None = None) -> bytes:
    """Generate peer_id prefix from version.

    Pattern: -BT{major:02d}{minor:02d}-
    Patch version is ignored.

    Special case: Until first 0.1.0 release, all 0.0.x versions use -BT0001-

    Examples:
        Version 0.0.1 → -BT0001-
        Version 0.0.5 → -BT0001-
        Version 0.1.0 → -BT0100-
        Version 0.1.2 → -BT0100- (patch ignored)
        Version 1.2.3 → -BT0102- (patch ignored)

    Args:
        version: Version string. If None, uses get_version().

    Returns:
        Peer ID prefix as bytes (e.g., b"-BT0001-", b"-BT0100-")
    """
    if version is None:
        version = get_version()

    major, minor, patch = parse_version(version)

    # Special case: Until first 0.1.0 release, all 0.0.x versions use -BT0001-
    if major == 0 and minor == 0:
        return b"-BT0001-"

    # Format as -BT{major:02d}{minor:02d}-
    prefix = f"-BT{major:02d}{minor:02d}-"
    return prefix.encode("utf-8")


def get_network_client_name() -> str:
    """Get client name for network protocol (peer_id, user-agent).

    Returns:
        Network client name: "btonic"
    """
    return NETWORK_CLIENT_NAME


def get_ui_client_name() -> str:
    """Get client name for UI/CLI display.

    Returns:
        UI client name: "ccBitTorrent"
    """
    return UI_CLIENT_NAME


def get_user_agent(version: str | None = None) -> str:
    """Format user-agent string for HTTP requests.

    Format: "btonic/{version}"

    Args:
        version: Version string. If None, uses get_version().

    Returns:
        User-agent string (e.g., "btonic/0.0.1")
    """
    if version is None:
        version = get_version()

    return f"{NETWORK_CLIENT_NAME}/{version}"


def get_full_peer_id(version: str | None = None) -> bytes:
    """Generate a complete 20-byte peer_id.

    Format: {prefix}{random_bytes}
    - Prefix: 8 bytes (-BT{major:02d}{minor:02d}-)
    - Random: 12 bytes

    Args:
        version: Version string. If None, uses get_version().

    Returns:
        20-byte peer_id
    """
    import os

    prefix = get_peer_id_prefix(version)
    # Generate 12 random bytes to complete the 20-byte peer_id
    random_bytes = os.urandom(12)
    return prefix + random_bytes











