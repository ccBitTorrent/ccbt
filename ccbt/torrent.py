"""Torrent file parsing and management for BitTorrent client.

This module handles parsing torrent files, extracting metadata,
and calculating info hashes as required by the BitTorrent protocol.
"""

import hashlib
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Union

from .bencode import decode, encode
from .exceptions import TorrentError
from .models import FileInfo, TorrentInfo


class TorrentParser:
    """Parser for BitTorrent torrent files."""

    def __init__(self) -> None:
        """Initialize the torrent parser."""

    def parse(self, torrent_path: Union[str, Path]) -> TorrentInfo:
        """Parse a torrent file from a local path or URL.

        Args:
            torrent_path: Path to local torrent file or URL

        Returns:
            TorrentInfo object containing parsed torrent data

        Raises:
            TorrentError: If parsing fails
        """
        try:
            # Read torrent data
            if self._is_url(torrent_path):
                torrent_data = self._read_from_url(torrent_path)
            else:
                torrent_data = self._read_from_file(torrent_path)

            # Decode bencoded data
            decoded_data = decode(torrent_data)

            # Validate torrent structure
            self._validate_torrent(decoded_data)

            # Extract and process data
            result = self._extract_torrent_data(decoded_data, torrent_data)

            return result

        except TorrentError:
            # Re-raise TorrentError as-is (validation errors)
            raise
        except Exception as e:
            raise TorrentError(f"Failed to parse torrent: {e}")

    def _is_url(self, path: Union[str, Path]) -> bool:
        """Check if path is a URL."""
        path_str = str(path)
        return path_str.startswith(("http://", "https://", "ftp://"))

    def _read_from_file(self, file_path: Union[str, Path]) -> bytes:
        """Read torrent data from a local file."""
        path = Path(file_path)
        if not path.exists():
            raise TorrentError(f"Torrent file not found: {path}")

        with open(path, "rb") as f:
            return f.read()

    def _read_from_url(self, url: str) -> bytes:
        """Read torrent data from a URL."""
        try:
            with urllib.request.urlopen(url) as response:
                return response.read()
        except Exception as e:
            raise TorrentError(f"Failed to download torrent from URL: {e}")

    def _validate_torrent(self, data: Dict[bytes, Any]) -> None:
        """Validate that the data is a valid torrent file."""
        required_keys = [b"announce", b"info"]
        for key in required_keys:
            if key not in data:
                raise TorrentError(f"Missing required key in torrent: {key.decode('utf-8', errors='ignore')}")

        # Validate info dictionary has required keys
        info = data[b"info"]
        if not isinstance(info, dict):
            raise TorrentError("Invalid info dictionary in torrent")

        # Must have either length (single file) or files (multi-file)
        if b"length" not in info and b"files" not in info:
            raise TorrentError("Torrent must specify either length (single file) or files (multi-file)")

        # Must have piece length and pieces
        if b"piece length" not in info:
            raise TorrentError("Missing piece length in torrent info")
        if b"pieces" not in info:
            raise TorrentError("Missing pieces in torrent info")

    def _extract_torrent_data(self, data: Dict[bytes, Any], raw_data: bytes) -> TorrentInfo:
        """Extract and process torrent data."""
        # Extract announce URL
        announce = data[b"announce"].decode("utf-8")

        # Extract info dictionary
        info = data[b"info"]

        # Calculate info hash (SHA-1 of bencoded info)
        info_bencoded = encode(info)
        info_hash = hashlib.sha1(info_bencoded).digest()

        # Extract file information
        files = self._extract_file_info(info)

        # Extract pieces information
        pieces_info = self._extract_pieces_info(info)

        # Extract optional fields
        announce_list = None
        if b"announce-list" in data:
            announce_list = [[url.decode("utf-8") for url in tier] for tier in data[b"announce-list"]]

        comment = data.get(b"comment", b"").decode("utf-8") if b"comment" in data else None
        created_by = data.get(b"created by", b"").decode("utf-8") if b"created by" in data else None
        creation_date = data.get(b"creation date")
        encoding = data.get(b"encoding", b"").decode("utf-8") if b"encoding" in data else None

        return TorrentInfo(
            name=info[b"name"].decode("utf-8"),
            info_hash=info_hash,
            announce=announce,
            announce_list=announce_list,
            comment=comment,
            created_by=created_by,
            creation_date=creation_date,
            encoding=encoding,
            files=files,
            total_length=sum(f.length for f in files),
            piece_length=pieces_info["piece_length"],
            pieces=pieces_info["piece_hashes"],
            num_pieces=pieces_info["num_pieces"],
        )

    def _extract_file_info(self, info: Dict[bytes, Any]) -> List[FileInfo]:
        """Extract file information from info dictionary."""
        if b"length" in info:
            # Single file torrent
            return [FileInfo(
                name=info[b"name"].decode("utf-8"),
                length=info[b"length"],
                path=None,
                full_path=info[b"name"].decode("utf-8"),
            )]
        # Multi-file torrent
        files = []
        for file_info in info[b"files"]:
            length = file_info[b"length"]
            path_parts = [part.decode("utf-8") for part in file_info[b"path"]]
            full_path = os.path.join(*path_parts)

            files.append(FileInfo(
                name=path_parts[-1],  # filename
                length=length,
                path=path_parts,
                full_path=full_path,
            ))

        return files

    def _extract_pieces_info(self, info: Dict[bytes, Any]) -> Dict[str, Any]:
        """Extract pieces information from info dictionary."""
        piece_length = info[b"piece length"]
        pieces_data = info[b"pieces"]

        # Pieces data should be multiple of 20 bytes (SHA-1 hashes)
        if len(pieces_data) % 20 != 0:
            raise TorrentError(f"Invalid pieces data length: {len(pieces_data)} bytes (should be multiple of 20)")

        num_pieces = len(pieces_data) // 20
        piece_hashes = []

        for i in range(num_pieces):
            start = i * 20
            end = start + 20
            piece_hashes.append(pieces_data[start:end])

        return {
            "piece_length": piece_length,
            "num_pieces": num_pieces,
            "piece_hashes": piece_hashes,
            "total_length": piece_length * num_pieces,  # Approximate, last piece may be smaller
        }

    def get_info_hash(self, torrent_data: TorrentInfo) -> bytes:
        """Get the info hash for a parsed torrent."""
        return torrent_data.info_hash

    def get_announce_url(self, torrent_data: TorrentInfo) -> str:
        """Get the announce URL for a parsed torrent."""
        return torrent_data.announce

    def get_total_length(self, torrent_data: TorrentInfo) -> int:
        """Get the total download length for a parsed torrent."""
        return torrent_data.total_length

    def get_piece_length(self, torrent_data: TorrentInfo) -> int:
        """Get the piece length for a parsed torrent."""
        return torrent_data.piece_length

    def get_num_pieces(self, torrent_data: TorrentInfo) -> int:
        """Get the number of pieces for a parsed torrent."""
        return torrent_data.num_pieces

    def get_piece_hash(self, torrent_data: TorrentInfo, piece_index: int) -> bytes:
        """Get the SHA-1 hash for a specific piece."""
        if piece_index < 0 or piece_index >= torrent_data.num_pieces:
            raise TorrentError(f"Invalid piece index: {piece_index}")

        return torrent_data.pieces[piece_index]
