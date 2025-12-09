"""Tonic link generation and parsing for XET folder synchronization.

This module handles generating and parsing tonic?: magnet-style links for
XET folder sync. Tonic links are similar to magnet links but use the
tonic?: scheme and include XET-specific parameters like git refs and sync modes.
"""

from __future__ import annotations

import base64
import urllib.parse
from dataclasses import dataclass
from typing import Any


@dataclass
class TonicLinkInfo:
    """Information extracted from a tonic?: link."""

    info_hash: bytes  # 32-byte SHA-256 hash
    display_name: str | None = None
    trackers: list[str] | None = None
    git_refs: list[str] | None = None
    sync_mode: str | None = None
    source_peers: list[str] | None = None
    allowlist_hash: bytes | None = None


def _hex_or_base32_to_bytes(value: str) -> bytes:
    """Convert hex or base32 encoded hash to bytes.

    Args:
        value: Hex or base32 encoded hash string

    Returns:
        Decoded bytes

    Raises:
        ValueError: If value cannot be decoded

    """
    # Try hex first (64 chars for 32 bytes)
    if len(value) == 64:
        try:
            return bytes.fromhex(value)
        except ValueError:
            pass

    # Try base32
    try:
        # Add padding if needed
        padding = (8 - len(value) % 8) % 8
        value_padded = value + "=" * padding
        return base64.b32decode(value_padded)
    except Exception:
        pass

    # Try hex with different lengths
    try:
        return bytes.fromhex(value)
    except ValueError as e:
        msg = f"Invalid hash format: {value}"
        raise ValueError(msg) from e


def parse_tonic_link(uri: str) -> TonicLinkInfo:
    """Parse a tonic?: link and return TonicLinkInfo.

    Format: tonic?:xt=urn:xet:<hash>&dn=<name>&tr=<tracker>&git=<commit>&mode=<sync_mode>

    Args:
        uri: Tonic link URI string

    Returns:
        TonicLinkInfo object containing parsed link data

    Raises:
        ValueError: If URI is not a valid tonic?: link

    """
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "tonic?":
        msg = "Not a tonic?: URI"
        raise ValueError(msg)

    qs = urllib.parse.parse_qs(parsed.query)

    # Extract info hash from xt parameter
    xts = qs.get("xt", [])
    xet_value = None
    for xt in xts:
        if xt.startswith("urn:xet:"):
            xet_value = xt.split("urn:xet:")[1]
            break
    if not xet_value:
        msg = "Tonic link missing xt=urn:xet"
        raise ValueError(msg)

    info_hash = _hex_or_base32_to_bytes(xet_value)
    if len(info_hash) != 32:
        msg = f"Info hash must be 32 bytes, got {len(info_hash)}"
        raise ValueError(msg)

    # Extract display name
    display_name = qs.get("dn", [None])[0]
    if display_name:
        display_name = urllib.parse.unquote(display_name)

    # Extract trackers (multiple tr parameters)
    trackers = qs.get("tr", [])
    if trackers:
        trackers = [urllib.parse.unquote(tr) for tr in trackers]

    # Extract git refs (multiple git parameters)
    git_refs = qs.get("git", [])
    if git_refs:
        git_refs = [urllib.parse.unquote(git) for git in git_refs]

    # Extract sync mode
    sync_mode = qs.get("mode", [None])[0]
    if sync_mode:
        sync_mode = urllib.parse.unquote(sync_mode)
        valid_modes = {"designated", "best_effort", "broadcast", "consensus"}
        if sync_mode not in valid_modes:
            msg = f"Invalid sync mode: {sync_mode}"
            raise ValueError(msg)

    # Extract source peers (comma-separated or multiple peer parameters)
    source_peers = None
    if "peer" in qs:
        source_peers = [urllib.parse.unquote(p) for p in qs["peer"]]
    elif "peers" in qs:
        # Comma-separated peers
        peers_str = qs.get("peers", [None])[0]
        if peers_str:
            source_peers = [
                urllib.parse.unquote(p.strip())
                for p in urllib.parse.unquote(peers_str).split(",")
                if p.strip()
            ]

    # Extract allowlist hash
    allowlist_hash = None
    if "allowlist" in qs:
        allowlist_str = qs.get("allowlist", [None])[0]
        if allowlist_str:
            try:
                allowlist_hash = _hex_or_base32_to_bytes(allowlist_str)
                if len(allowlist_hash) != 32:
                    msg = f"Allowlist hash must be 32 bytes, got {len(allowlist_hash)}"
                    raise ValueError(msg)
            except ValueError:
                # Invalid allowlist hash, ignore
                allowlist_hash = None

    return TonicLinkInfo(
        info_hash=info_hash,
        display_name=display_name,
        trackers=trackers if trackers else None,
        git_refs=git_refs if git_refs else None,
        sync_mode=sync_mode,
        source_peers=source_peers,
        allowlist_hash=allowlist_hash,
    )


def generate_tonic_link(
    info_hash: bytes,
    display_name: str | None = None,
    trackers: list[str] | None = None,
    git_refs: list[str] | None = None,
    sync_mode: str | None = None,
    source_peers: list[str] | None = None,
    allowlist_hash: bytes | None = None,
    use_base32: bool = False,
) -> str:
    """Generate a tonic?: link from provided parameters.

    Args:
        info_hash: 32-byte SHA-256 info hash
        display_name: Optional display name (dn parameter)
        trackers: Optional list of tracker URLs (tr parameters)
        git_refs: Optional list of git commit hashes/refs (git parameters)
        sync_mode: Optional sync mode (mode parameter)
        source_peers: Optional list of source peer IDs (peer parameters)
        allowlist_hash: Optional 32-byte allowlist hash
        use_base32: Whether to encode info hash as base32 (default: hex)

    Returns:
        Complete tonic?: link string

    Raises:
        ValueError: If info_hash is not 32 bytes or sync_mode is invalid

    """
    if len(info_hash) != 32:
        msg = f"Info hash must be 32 bytes, got {len(info_hash)}"
        raise ValueError(msg)

    # Build base tonic link
    parts = ["tonic?:xt=urn:xet:"]

    # Encode info hash
    if use_base32:
        hash_str = base64.b32encode(info_hash).decode().rstrip("=")
    else:
        hash_str = info_hash.hex()
    parts[0] += hash_str

    # Add display name
    if display_name:
        encoded_name = urllib.parse.quote(display_name)
        parts.append(f"dn={encoded_name}")

    # Add trackers
    if trackers:
        for tracker in trackers:
            encoded_tracker = urllib.parse.quote(tracker, safe=":/?#[]@!$&'()*+,;=")
            parts.append(f"tr={encoded_tracker}")

    # Add git refs
    if git_refs:
        for git_ref in git_refs:
            encoded_git = urllib.parse.quote(git_ref)
            parts.append(f"git={encoded_git}")

    # Add sync mode
    if sync_mode:
        valid_modes = {"designated", "best_effort", "broadcast", "consensus"}
        if sync_mode not in valid_modes:
            msg = f"Invalid sync mode: {sync_mode}"
            raise ValueError(msg)
        parts.append(f"mode={urllib.parse.quote(sync_mode)}")

    # Add source peers
    if source_peers:
        # Use comma-separated format in peers parameter
        peers_str = ",".join(urllib.parse.quote(peer) for peer in source_peers)
        parts.append(f"peers={peers_str}")

    # Add allowlist hash
    if allowlist_hash:
        if len(allowlist_hash) != 32:
            msg = f"Allowlist hash must be 32 bytes, got {len(allowlist_hash)}"
            raise ValueError(msg)
        allowlist_str = allowlist_hash.hex()
        parts.append(f"allowlist={allowlist_str}")

    return "&".join(parts)


def build_minimal_tonic_data(
    info_hash: bytes,
    name: str | None,
    trackers: list[str],
    sync_mode: str = "best_effort",
) -> dict[str, Any]:
    """Create a minimal tonic_data placeholder using known info.

    This structure is suitable for tracker/DHT peer discovery and metadata
    fetching, but lacks full folder details until tonic file is fetched.

    Args:
        info_hash: 32-byte SHA-256 info hash
        name: Optional folder name
        trackers: List of tracker URLs
        sync_mode: Synchronization mode

    Returns:
        Dictionary with minimal tonic data structure

    """
    return {
        "announce": trackers[0] if trackers else "",
        "announce_list": trackers,
        "info_hash": info_hash,
        "info": None,
        "xet_metadata": None,
        "name": name or "",
        "sync_mode": sync_mode,
        "is_tonic": True,  # Mark as tonic link for DHT setup
    }






