"""Magnet URI parsing (BEP 9) utilities.

from __future__ import annotations

This module parses magnet links and provides helpers to construct
`torrent_data`-compatible structures once metadata is obtained.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Any


@dataclass
class MagnetInfo:
    """Information extracted from a magnet link."""

    info_hash: bytes
    display_name: str | None
    trackers: list[str]
    web_seeds: list[str]


def _hex_or_base32_to_bytes(btih: str) -> bytes:
    """Decode btih which can be hex (40 chars) or base32 (32 chars)."""
    btih = btih.strip()
    if len(btih) == 40:
        # Hex
        return bytes.fromhex(btih)
    # Base32
    import base64

    return base64.b32decode(btih.upper())


def parse_magnet(uri: str) -> MagnetInfo:
    """Parse a magnet URI and return `MagnetInfo`.

    Supports: xt=urn:btih:<hash>, dn, tr (multiple), ws (multiple).
    """
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "magnet":
        msg = "Not a magnet URI"
        raise ValueError(msg)

    qs = urllib.parse.parse_qs(parsed.query)
    xts = qs.get("xt", [])
    btih_value = None
    for xt in xts:
        if xt.startswith("urn:btih:"):
            btih_value = xt.split("urn:btih:")[1]
            break
    if not btih_value:
        msg = "Magnet URI missing xt=urn:btih"
        raise ValueError(msg)

    info_hash = _hex_or_base32_to_bytes(btih_value)
    display_name = qs.get("dn", [None])[0]
    trackers = qs.get("tr", [])
    web_seeds = qs.get("ws", [])

    return MagnetInfo(
        info_hash=info_hash,
        display_name=display_name,
        trackers=trackers,
        web_seeds=web_seeds,
    )


def build_minimal_torrent_data(
    info_hash: bytes,
    name: str | None,
    trackers: list[str],
) -> dict[str, Any]:
    """Create a minimal `torrent_data` placeholder using known info.

    This structure is suitable for tracker/DHT peer discovery and metadata
    fetching, but lacks `info` details and piece layout until metadata is fetched.
    """
    return {
        "announce": trackers[0] if trackers else "",
        "announce_list": trackers,
        "info_hash": info_hash,
        "info": None,
        "file_info": None,
        "pieces_info": None,
        "name": name or "",
    }


def build_torrent_data_from_metadata(
    info_hash: bytes,
    info_dict: dict[bytes, Any],
) -> dict[str, Any]:
    """Convert decoded info dictionary to the client `torrent_data` shape."""
    # Extract piece hashes
    piece_length = int(info_dict.get(b"piece length", 0))
    pieces_blob = info_dict.get(b"pieces", b"")
    piece_hashes = [pieces_blob[i : i + 20] for i in range(0, len(pieces_blob), 20)]

    if b"files" in info_dict:
        # multi-file
        files_info = []
        total_length = 0
        for f in info_dict[b"files"]:
            length = int(f[b"length"])
            path = [p.decode("utf-8", errors="ignore") for p in f[b"path"]]
            files_info.append(
                {
                    "length": length,
                    "path": path,
                    "full_path": "/".join(path),
                },
            )
            total_length += length
        file_info = {
            "type": "multi",
            "files": files_info,
            "name": info_dict.get(b"name", b"").decode("utf-8", errors="ignore"),
            "total_length": total_length,
        }
    else:
        # single-file
        length = int(info_dict.get(b"length", 0))
        file_info = {
            "type": "single",
            "length": length,
            "name": info_dict.get(b"name", b"").decode("utf-8", errors="ignore"),
            "total_length": length,
        }

    # Help type checker for 'files' iteration below
    if not isinstance(file_info, dict):
        msg = f"Expected dict for file_info, got {type(file_info)}"
        raise TypeError(msg)
    pieces_info = {
        "piece_length": piece_length,
        "num_pieces": len(piece_hashes),
        "piece_hashes": piece_hashes,
        "total_length": file_info["total_length"]
        if file_info["type"] == "single"
        else sum(
            f.get("length", 0)
            for f in file_info.get("files", [])  # type: ignore[not-iterable]
            if isinstance(f, dict)
        ),
    }

    return {
        "announce": "",
        "announce_list": [],
        "info_hash": info_hash,
        "info": info_dict,
        "file_info": file_info,
        "pieces_info": pieces_info,
        "name": file_info["name"],
    }
