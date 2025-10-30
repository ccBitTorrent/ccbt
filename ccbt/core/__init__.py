"""Core BitTorrent protocol implementation.

This module contains the fundamental BitTorrent protocol components:
- Bencoding (encoding/decoding)
- Torrent file parsing
- Magnet link handling
"""

from __future__ import annotations

from ccbt.core.bencode import (
    BencodeDecoder,
    BencodeEncoder,
    decode,
    encode,
)
from ccbt.core.magnet import (
    MagnetInfo,
    build_minimal_torrent_data,
    build_torrent_data_from_metadata,
    parse_magnet,
)
from ccbt.core.torrent import TorrentParser

__all__ = [
    # Bencoding
    "BencodeDecoder",
    "BencodeEncoder",
    # Magnet
    "MagnetInfo",
    # Torrent
    "TorrentParser",
    "build_minimal_torrent_data",
    "build_torrent_data_from_metadata",
    "decode",
    "encode",
    "parse_magnet",
]
