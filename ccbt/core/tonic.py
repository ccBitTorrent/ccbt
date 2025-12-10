"""Tonic file format for XET folder synchronization.

This module handles parsing and generating .tonic files, which are the XET
equivalent of .torrent files. Tonic files use bencoded format and contain
folder metadata, XET chunk information, git versioning, sync modes, and
encrypted allowlist hashes.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from ccbt.core.bencode import decode, encode
from ccbt.models import XetTorrentMetadata
from ccbt.utils.exceptions import TorrentError


class TonicError(TorrentError):
    """Exception raised for tonic file errors."""


class TonicFile:
    """Parser and generator for .tonic files (XET folder sync format)."""

    TONIC_VERSION = 1  # Tonic file format version

    def __init__(self) -> None:
        """Initialize the tonic file handler."""

    def parse(self, tonic_path: str | Path) -> dict[str, Any]:
        """Parse a .tonic file from a local path.

        Args:
            tonic_path: Path to local .tonic file

        Returns:
            Dictionary containing parsed tonic data with keys:
            - info: Folder metadata (name, structure, total size)
            - xet_metadata: XET chunk hashes and file-to-chunk mapping
            - git_refs: Git commit hashes for version tracking
            - sync_mode: Synchronization mode
            - source_peers: Designated source peer IDs (if applicable)
            - allowlist_hash: Hash of encrypted allowlist
            - created_at: Timestamp
            - version: Tonic format version

        Raises:
            TonicError: If parsing fails

        """
        try:
            # Read tonic data
            tonic_data = self._read_from_file(tonic_path)

            # Decode bencoded data
            decoded_data = decode(tonic_data)

            # Validate tonic structure
            self._validate_tonic(decoded_data)

            # Extract and process data
            return self._extract_tonic_data(decoded_data)

        except TonicError:
            # Re-raise TonicError as-is
            raise
        except Exception as e:
            msg = f"Failed to parse tonic file: {e}"
            raise TonicError(msg) from e

    def parse_bytes(self, tonic_data: bytes) -> dict[str, Any]:
        """Parse .tonic file from bytes.

        Args:
            tonic_data: Bencoded .tonic file data

        Returns:
            Dictionary containing parsed tonic data

        Raises:
            TonicError: If parsing fails

        """
        try:
            # Decode bencoded data
            decoded_data = decode(tonic_data)

            # Validate tonic structure
            self._validate_tonic(decoded_data)

            # Extract and process data
            return self._extract_tonic_data(decoded_data)

        except TonicError:
            raise
        except Exception as e:
            msg = f"Failed to parse tonic data: {e}"
            raise TonicError(msg) from e

    def create(
        self,
        folder_name: str,
        xet_metadata: XetTorrentMetadata,
        git_refs: list[str] | None = None,
        sync_mode: str = "best_effort",
        source_peers: list[str] | None = None,
        allowlist_hash: bytes | None = None,
        announce: str | None = None,
        announce_list: list[list[str]] | None = None,
        comment: str | None = None,
    ) -> bytes:
        """Create a bencoded .tonic file.

        Args:
            folder_name: Name of the folder
            xet_metadata: XET metadata containing chunk hashes and file info
            git_refs: List of git commit hashes for version tracking
            sync_mode: Synchronization mode (designated/best_effort/broadcast/consensus)
            source_peers: List of designated source peer IDs (for designated mode)
            allowlist_hash: Hash of encrypted allowlist (32 bytes)
            announce: Primary tracker announce URL
            announce_list: List of tracker tiers
            comment: Optional comment

        Returns:
            Bencoded .tonic file data as bytes

        """
        # Build info dictionary
        info: dict[bytes, Any] = {
            b"name": folder_name.encode("utf-8"),
            b"tonic version": self.TONIC_VERSION,
        }

        # Add folder structure and total size from xet_metadata
        total_size = sum(fm.total_size for fm in xet_metadata.file_metadata)
        info[b"total length"] = total_size

        # Add file tree structure (parseable directory tree)
        # Format: {"folder1": {"folder2": {"file.txt": {"": {"length": 1234, "file hash": b"..."}}}, "file2.txt": {...}}}
        file_tree: dict[bytes, Any] = {}
        for file_meta in xet_metadata.file_metadata:
            # Convert file path to tree structure
            path_parts = [p for p in file_meta.file_path.split("/") if p]  # Remove empty parts
            if not path_parts:
                continue

            current = file_tree
            # Navigate/create directory structure
            for part in path_parts[:-1]:
                part_bytes = part.encode("utf-8")
                if part_bytes not in current:
                    current[part_bytes] = {}
                elif not isinstance(current[part_bytes], dict):
                    # Convert file to directory if needed
                    current[part_bytes] = {}
                current = current[part_bytes]

            # Add file entry (empty key indicates file, not directory)
            filename_bytes = path_parts[-1].encode("utf-8")
            if filename_bytes not in current:
                current[filename_bytes] = {}
            if b"" not in current[filename_bytes]:
                current[filename_bytes][b""] = {}
            current[filename_bytes][b""][b"length"] = file_meta.total_size
            current[filename_bytes][b""][b"file hash"] = file_meta.file_hash

        info[b"file tree"] = file_tree
        # Also add files list for easy access
        info[b"files"] = [
            {
                b"path": fm.file_path.encode("utf-8"),
                b"length": fm.total_size,
                b"file hash": fm.file_hash,
            }
            for fm in xet_metadata.file_metadata
        ]

        # Build xet_metadata dictionary
        xet_dict: dict[bytes, Any] = {
            b"chunk hashes": xet_metadata.chunk_hashes,
        }

        # Add file metadata
        file_meta_list: list[dict[bytes, Any]] = []
        for file_meta in xet_metadata.file_metadata:
            file_meta_list.append(
                {
                    b"file path": file_meta.file_path.encode("utf-8"),
                    b"file hash": file_meta.file_hash,
                    b"chunk hashes": file_meta.chunk_hashes,
                    b"total size": file_meta.total_size,
                }
            )
        xet_dict[b"file metadata"] = file_meta_list

        # Add piece metadata if available
        if xet_metadata.piece_metadata:
            piece_meta_list: list[dict[bytes, Any]] = []
            for piece_meta in xet_metadata.piece_metadata:
                piece_meta_list.append(
                    {
                        b"piece index": piece_meta.piece_index,
                        b"chunk hashes": piece_meta.chunk_hashes,
                        b"merkle hash": piece_meta.merkle_hash,
                    }
                )
            xet_dict[b"piece metadata"] = piece_meta_list

        # Add xorb hashes if available
        if xet_metadata.xorb_hashes:
            xet_dict[b"xorb hashes"] = xet_metadata.xorb_hashes

        # Build main tonic dictionary
        tonic_dict: dict[bytes, Any] = {
            b"info": info,
            b"xet metadata": xet_dict,
        }

        # Add optional fields
        if announce:
            tonic_dict[b"announce"] = announce.encode("utf-8")

        if announce_list:
            tonic_dict[b"announce-list"] = [
                [url.encode("utf-8") for url in tier] for tier in announce_list
            ]

        if comment:
            tonic_dict[b"comment"] = comment.encode("utf-8")

        # Add git refs
        if git_refs:
            tonic_dict[b"git refs"] = [ref.encode("utf-8") for ref in git_refs]

        # Add sync mode
        tonic_dict[b"sync mode"] = sync_mode.encode("utf-8")

        # Add source peers if applicable
        if source_peers:
            tonic_dict[b"source peers"] = [
                peer_id.encode("utf-8") for peer_id in source_peers
            ]

        # Add allowlist hash
        if allowlist_hash:
            if len(allowlist_hash) != 32:
                msg = "Allowlist hash must be 32 bytes"
                raise ValueError(msg)
            tonic_dict[b"allowlist hash"] = allowlist_hash

        # Add creation timestamp
        tonic_dict[b"created at"] = int(time.time())

        # Encode to bencoded format
        return encode(tonic_dict)

    def get_file_tree(self, tonic_data: dict[str, Any]) -> dict[str, Any]:
        """Extract parseable file tree from tonic data.

        Args:
            tonic_data: Parsed tonic data dictionary

        Returns:
            File tree structure as nested dictionaries

        """
        info = tonic_data.get("info", {})
        file_tree = info.get("file tree") or info.get(b"file tree")
        if file_tree:
            # Convert bytes keys to strings for easier use
            return self._convert_tree_keys(file_tree)
        # Fallback to files list if file tree not available
        files = info.get("files") or info.get(b"files", [])
        if files:
            return self._build_tree_from_files(files)
        return {}

    def _convert_tree_keys(self, tree: dict[bytes, Any] | dict[str, Any]) -> dict[str, Any]:
        """Convert tree keys from bytes to strings recursively.

        Args:
            tree: Tree dictionary with bytes or string keys

        Returns:
            Tree with string keys

        """
        result: dict[str, Any] = {}
        for key, value in tree.items():
            if isinstance(key, bytes):
                key_str = key.decode("utf-8")
            else:
                key_str = str(key)

            if isinstance(value, dict):
                result[key_str] = self._convert_tree_keys(value)
            elif isinstance(value, list):
                result[key_str] = [
                    self._convert_tree_keys(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key_str] = value
        return result

    def _build_tree_from_files(self, files: list[dict[bytes, Any] | dict[str, Any]]) -> dict[str, Any]:
        """Build file tree from files list.

        Args:
            files: List of file dictionaries

        Returns:
            File tree structure

        """
        tree: dict[str, Any] = {}
        for file_entry in files:
            path = file_entry.get("path") or file_entry.get(b"path")
            if isinstance(path, bytes):
                path_str = path.decode("utf-8")
            else:
                path_str = str(path)

            length = file_entry.get("length") or file_entry.get(b"length", 0)
            file_hash = file_entry.get("file hash") or file_entry.get(b"file hash")

            # Build tree path
            path_parts = [p for p in path_str.split("/") if p]
            if not path_parts:
                continue

            current = tree
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Add file
            filename = path_parts[-1]
            if filename not in current:
                current[filename] = {}
            current[filename][""] = {
                "length": length,
                "file hash": file_hash.hex() if isinstance(file_hash, bytes) else file_hash,
            }

        return tree

    def get_info_hash(self, tonic_data: dict[str, Any]) -> bytes:
        """Calculate info hash from parsed tonic data.

        The info hash is SHA-256 of the bencoded info dictionary.

        Args:
            tonic_data: Parsed tonic data dictionary

        Returns:
            32-byte SHA-256 hash

        """
        # Get info dictionary and encode it
        info_dict = tonic_data.get("info", {})
        # Convert back to bytes format for encoding
        info_bytes_dict: dict[bytes, Any] = {}
        for key, value in info_dict.items():
            if isinstance(key, str):
                key_bytes = key.encode("utf-8")
            else:
                key_bytes = key
            info_bytes_dict[key_bytes] = value

        info_bencoded = encode(info_bytes_dict)
        return hashlib.sha256(info_bencoded).digest()

    def _read_from_file(self, file_path: str | Path) -> bytes:
        """Read tonic data from a local file.

        Args:
            file_path: Path to .tonic file

        Returns:
            File contents as bytes

        Raises:
            TonicError: If file not found or read fails

        """
        path = Path(file_path)
        if not path.exists():
            msg = f"Tonic file not found: {path}"
            raise TonicError(msg)

        with open(path, "rb") as f:
            return f.read()

    def _validate_tonic(self, data: dict[bytes, Any]) -> None:
        """Validate that the data is a valid .tonic file.

        Args:
            data: Decoded bencoded data

        Raises:
            TonicError: If validation fails

        """
        # Must have info dictionary
        if b"info" not in data:
            msg = "Missing required 'info' key in tonic file"
            raise TonicError(msg)

        info = data[b"info"]
        if not isinstance(info, dict):
            msg = "Invalid info dictionary in tonic file"
            raise TonicError(msg)

        # Must have name in info
        if b"name" not in info:
            msg = "Missing 'name' in tonic info"
            raise TonicError(msg)

        # Must have xet metadata
        if b"xet metadata" not in data:
            msg = "Missing required 'xet metadata' key in tonic file"
            raise TonicError(msg)

        xet_meta = data[b"xet metadata"]
        if not isinstance(xet_meta, dict):
            msg = "Invalid xet metadata in tonic file"
            raise TonicError(msg)

        # Must have chunk hashes in xet metadata
        if b"chunk hashes" not in xet_meta:
            msg = "Missing 'chunk hashes' in xet metadata"
            raise TonicError(msg)

        # Validate sync mode if present
        if b"sync mode" in data:
            sync_mode = data[b"sync mode"]
            if isinstance(sync_mode, bytes):
                sync_mode_str = sync_mode.decode("utf-8")
            else:
                sync_mode_str = str(sync_mode)
            valid_modes = {"designated", "best_effort", "broadcast", "consensus"}
            if sync_mode_str not in valid_modes:
                msg = f"Invalid sync mode: {sync_mode_str}"
                raise TonicError(msg)

        # Validate allowlist hash if present (must be 32 bytes)
        if b"allowlist hash" in data:
            allowlist_hash = data[b"allowlist hash"]
            if isinstance(allowlist_hash, bytes) and len(allowlist_hash) != 32:
                msg = "Allowlist hash must be 32 bytes"
                raise TonicError(msg)

    def _extract_tonic_data(self, data: dict[bytes, Any]) -> dict[str, Any]:
        """Extract and process tonic data into Python-friendly format.

        Args:
            data: Decoded bencoded data

        Returns:
            Dictionary with string keys and processed values

        """
        result: dict[str, Any] = {}

        # Extract info
        info = data[b"info"]
        result["info"] = {
            "name": info[b"name"].decode("utf-8"),
            "tonic_version": info.get(b"tonic version", self.TONIC_VERSION),
            "total_length": info.get(b"total length", 0),
            "file_tree": self._decode_file_tree(info.get(b"file tree", {})),
        }

        # Extract xet metadata
        xet_meta = data[b"xet metadata"]
        result["xet_metadata"] = {
            "chunk_hashes": xet_meta.get(b"chunk hashes", []),
            "file_metadata": [
                {
                    "file_path": fm.get(b"file path", b"").decode("utf-8"),
                    "file_hash": fm.get(b"file hash", b""),
                    "chunk_hashes": fm.get(b"chunk hashes", []),
                    "total_size": fm.get(b"total size", 0),
                }
                for fm in xet_meta.get(b"file metadata", [])
            ],
            "piece_metadata": [
                {
                    "piece_index": pm.get(b"piece index", 0),
                    "chunk_hashes": pm.get(b"chunk hashes", []),
                    "merkle_hash": pm.get(b"merkle hash", b""),
                }
                for pm in xet_meta.get(b"piece metadata", [])
            ],
            "xorb_hashes": xet_meta.get(b"xorb hashes", []),
        }

        # Extract optional fields
        if b"announce" in data:
            result["announce"] = data[b"announce"].decode("utf-8")

        if b"announce-list" in data:
            result["announce_list"] = [
                [url.decode("utf-8") for url in tier]
                for tier in data[b"announce-list"]
            ]

        if b"comment" in data:
            result["comment"] = data[b"comment"].decode("utf-8")

        if b"git refs" in data:
            result["git_refs"] = [
                ref.decode("utf-8") if isinstance(ref, bytes) else str(ref)
                for ref in data[b"git refs"]
            ]

        if b"sync mode" in data:
            sync_mode = data[b"sync mode"]
            result["sync_mode"] = (
                sync_mode.decode("utf-8") if isinstance(sync_mode, bytes) else str(sync_mode)
            )
        else:
            result["sync_mode"] = "best_effort"  # Default

        if b"source peers" in data:
            result["source_peers"] = [
                peer.decode("utf-8") if isinstance(peer, bytes) else str(peer)
                for peer in data[b"source peers"]
            ]

        if b"allowlist hash" in data:
            result["allowlist_hash"] = data[b"allowlist hash"]

        if b"created at" in data:
            result["created_at"] = data[b"created at"]

        result["version"] = result["info"].get("tonic_version", self.TONIC_VERSION)

        return result

    def _decode_file_tree(self, file_tree: dict[bytes, Any]) -> dict[str, Any]:
        """Decode file tree structure from bencoded format.

        Args:
            file_tree: Bencoded file tree dictionary

        Returns:
            Decoded file tree with string keys

        """
        result: dict[str, Any] = {}
        for key, value in file_tree.items():
            key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            if isinstance(value, dict):
                if b"" in value:
                    # File entry
                    file_info = value[b""]
                    result[key_str] = {
                        "length": file_info.get(b"length", 0),
                        "file_hash": file_info.get(b"file hash", b"").hex()
                        if isinstance(file_info.get(b"file hash"), bytes)
                        else None,
                    }
                else:
                    # Directory entry
                    result[key_str] = self._decode_file_tree(value)
            else:
                result[key_str] = value
        return result


