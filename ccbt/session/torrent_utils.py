"""Torrent data utility functions for session management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ccbt.core.magnet import build_minimal_torrent_data, parse_magnet
from ccbt.core.torrent import TorrentParser
from ccbt.models import TorrentInfo as TorrentInfoModel


def get_torrent_info(
    torrent_data: dict[str, Any] | TorrentInfoModel,
    logger: Any | None = None,
) -> TorrentInfoModel | None:
    """Convert torrent_data to TorrentInfo if possible.

    Args:
        torrent_data: Torrent data in dict or TorrentInfo format
        logger: Optional logger instance for warnings

    Returns:
        TorrentInfo if conversion successful, None otherwise

    """
    if isinstance(torrent_data, TorrentInfoModel):
        return torrent_data

    if isinstance(torrent_data, dict):
        # Try to extract file information from dict
        try:
            # Check if files are in the dict directly
            files = torrent_data.get("files", [])
            if not files:
                # Check if in file_info
                # CRITICAL FIX: Handle None values (common for magnet links)
                file_info_dict = torrent_data.get("file_info") or {}
                if isinstance(file_info_dict, dict) and "files" in file_info_dict:
                    files = file_info_dict["files"]

            # Convert files to FileInfo objects if needed
            file_info_list = []
            if files:
                from ccbt.models import FileInfo

                for f in files:
                    if isinstance(f, dict):
                        file_info_list.append(
                            FileInfo(
                                name=f.get("name", f.get("full_path", "")),
                                length=f.get("length", 0),
                                path=f.get("path"),
                                full_path=f.get("full_path"),
                            ),
                        )
                    elif hasattr(f, "name"):  # Already a FileInfo
                        file_info_list.append(f)

            # Validate and normalize info_hash to exactly 20 bytes
            info_hash_raw = torrent_data.get("info_hash", b"\x00" * 20)
            if len(info_hash_raw) > 20:
                if logger:
                    logger.warning(
                        "info_hash too long (%d bytes), truncating to 20",
                        len(info_hash_raw),
                    )
                info_hash = info_hash_raw[:20]
            elif len(info_hash_raw) < 20:
                if logger:
                    logger.warning(
                        "info_hash too short (%d bytes), padding to 20",
                        len(info_hash_raw),
                    )
                info_hash = info_hash_raw + b"\x00" * (20 - len(info_hash_raw))
            else:
                info_hash = info_hash_raw

            # Build TorrentInfo
            return TorrentInfoModel(
                name=torrent_data.get("name", "Unknown"),
                info_hash=info_hash,
                announce=torrent_data.get("announce", ""),
                announce_list=torrent_data.get("announce_list"),
                is_private=torrent_data.get("is_private", False),
                files=file_info_list,
                total_length=torrent_data.get("total_length", 0),
                piece_length=torrent_data.get("pieces_info", {}).get(
                    "piece_length",
                    torrent_data.get("piece_length", 16384),
                ),
                pieces=torrent_data.get("pieces_info", {}).get(
                    "piece_hashes",
                    torrent_data.get("pieces", []),
                ),
                num_pieces=torrent_data.get("pieces_info", {}).get(
                    "num_pieces",
                    torrent_data.get("num_pieces", 0),
                ),
            )
        except Exception:
            if logger:
                logger.debug("Could not convert torrent_data to TorrentInfo")
            return None

    return None


def extract_is_private(
    torrent_data: dict[str, Any] | TorrentInfoModel,
) -> bool:
    """Extract is_private flag from torrent data (BEP 27).

    Args:
        torrent_data: Torrent data in dict or TorrentInfo format

    Returns:
        True if torrent is marked as private, False otherwise

    """
    if isinstance(torrent_data, TorrentInfoModel):
        return getattr(torrent_data, "is_private", False)

    if isinstance(torrent_data, dict):
        # Check direct is_private field
        if "is_private" in torrent_data:
            return bool(torrent_data["is_private"])

        # Check in info dictionary if present
        info_dict = torrent_data.get("info")
        if isinstance(info_dict, dict):
            private_value = info_dict.get(b"private") or info_dict.get("private")
            if private_value is not None:
                return bool(private_value)

    return False


def normalize_torrent_data(
    td: dict[str, Any] | TorrentInfoModel,
    logger: Any | None = None,
) -> dict[str, Any]:
    """Convert TorrentInfoModel or legacy dict into a normalized dict expected by piece manager.

    Returns a dict with keys: 'file_info', 'pieces_info', and minimal metadata.

    For magnet links (pieces_info is None), creates a minimal placeholder structure
    that allows AsyncPieceManager to initialize. The piece manager will need to
    update this once metadata is fetched via metadata exchange.

    Args:
        td: Torrent data in dict or TorrentInfoModel format
        logger: Optional logger instance for warnings

    Returns:
        Normalized dict with file_info and pieces_info

    Raises:
        TypeError: If torrent_data is a list or invalid type

    """
    # CRITICAL FIX: Validate torrent_data is not a list
    if isinstance(td, list):
        error_msg = (
            f"torrent_data cannot be a list, got {type(td)}. "
            "Expected dict or TorrentInfoModel."
        )
        if logger:
            logger.error(error_msg)
        raise TypeError(error_msg)

    if isinstance(td, dict):
        # Assume already using legacy dict shape or at least includes needed fields
        # Best-effort fill pieces_info / file_info if missing
        pieces_info = td.get("pieces_info")
        file_info = td.get("file_info")
        result: dict[str, Any] = dict(td)

        # Handle magnet links: if pieces_info is None, create minimal placeholder
        # This allows AsyncPieceManager to initialize, but metadata must be fetched
        if pieces_info is None:
            # Check if this is a magnet link (has info_hash but no pieces_info)
            if "info_hash" in td and "pieces" not in td:
                # Magnet link - create minimal placeholder structure
                # These values will be updated once metadata is fetched
                result["pieces_info"] = {
                    "piece_hashes": [],  # Empty until metadata fetched
                    "piece_length": 16384,  # Default piece length
                    "num_pieces": 0,  # Will be updated when metadata available
                    "total_length": 0,  # Will be updated when metadata available
                }
                result["file_info"] = {
                    "total_length": 0,  # Will be updated when metadata available
                    "files": [],  # Empty until metadata fetched
                }
                # Mark as incomplete metadata (magnet link)
                result["_metadata_incomplete"] = True
            elif "pieces" in td and "piece_length" in td and "num_pieces" in td:
                # Has pieces data but not in pieces_info format
                result["pieces_info"] = {
                    "piece_hashes": td.get("pieces", []),
                    "piece_length": td.get("piece_length", 0),
                    "num_pieces": td.get("num_pieces", 0),
                    "total_length": td.get("total_length", 0),
                }
            else:
                # No pieces data available - create minimal placeholder
                result["pieces_info"] = {
                    "piece_hashes": [],
                    "piece_length": 16384,
                    "num_pieces": 0,
                    "total_length": 0,
                }
                result["_metadata_incomplete"] = True
        elif pieces_info is not None:
            # Ensure pieces_info has all required fields
            if (
                not isinstance(pieces_info, dict)
                or not all(
                    key in pieces_info
                    for key in ["piece_hashes", "piece_length", "num_pieces"]
                )
            ) and ("pieces" in td and "piece_length" in td and "num_pieces" in td):
                # Rebuild from available data
                result["pieces_info"] = {
                    "piece_hashes": td.get(
                        "pieces", pieces_info.get("piece_hashes", [])
                    ),
                    "piece_length": td.get(
                        "piece_length", pieces_info.get("piece_length", 0)
                    ),
                    "num_pieces": td.get(
                        "num_pieces", pieces_info.get("num_pieces", 0)
                    ),
                    "total_length": td.get(
                        "total_length", pieces_info.get("total_length", 0)
                    ),
                }
            else:
                # Use what we have from pieces_info
                result["pieces_info"] = pieces_info
        if not file_info:
            # Use total_length from pieces_info if available, otherwise from td
            total_length = 0
            if pieces_info and isinstance(pieces_info, dict):
                total_length = pieces_info.get("total_length", 0)
            if total_length == 0:
                total_length = td.get("total_length", 0)
            result.setdefault(
                "file_info",
                {"total_length": total_length},
            )
        return result
    # TorrentInfoModel
    result = {
        "name": td.name,
        "info_hash": td.info_hash,
        "pieces_info": {
            "piece_hashes": list(td.pieces),
            "piece_length": td.piece_length,
            "num_pieces": td.num_pieces,
            "total_length": td.total_length,
        },
        "file_info": {
            "total_length": td.total_length,
        },
    }
    # Add v2 fields (BEP 52) if present
    if td.meta_version and td.meta_version >= 2:
        result["meta_version"] = td.meta_version
    if td.piece_layers:
        result["piece_layers"] = td.piece_layers
    if td.file_tree:
        result["file_tree"] = td.file_tree
    return result


def load_torrent(
    torrent_path: str | Path, logger: Any | None = None
) -> dict[str, Any] | None:
    """Load torrent file and return parsed data.

    Args:
        torrent_path: Path to torrent file
        logger: Optional logger instance for error logging

    Returns:
        Dictionary with torrent data or None if loading fails

    """
    try:
        parser = TorrentParser()
        tdm = parser.parse(
            str(torrent_path)
        )  # pragma: no cover - Parse torrent file, tested via integration tests
        return {
            "name": tdm.name,  # pragma: no cover - Build torrent data dict, tested via integration tests
            "info_hash": tdm.info_hash,  # pragma: no cover - Build torrent data dict, tested via integration tests
            "pieces_info": {
                "piece_hashes": list(tdm.pieces),
                "piece_length": tdm.piece_length,
                "num_pieces": tdm.num_pieces,
                "total_length": tdm.total_length,
            },
            "file_info": {
                "total_length": tdm.total_length,
            },
            "announce": getattr(tdm, "announce", ""),
        }
    except Exception:
        if logger:
            logger.exception("Failed to load torrent %s", torrent_path)
        return None


def parse_magnet_link(
    magnet_uri: str, logger: Any | None = None
) -> dict[str, Any] | None:
    """Parse magnet link and return torrent data.

    Args:
        magnet_uri: Magnet URI string
        logger: Optional logger instance for error logging

    Returns:
        Dictionary with minimal torrent data or None if parsing fails

    """
    try:
        magnet_info = parse_magnet(
            magnet_uri
        )  # pragma: no cover - Parse magnet URI, tested via integration tests
        return build_minimal_torrent_data(
            magnet_info.info_hash,  # pragma: no cover - Build minimal torrent data from magnet, tested via integration tests
            magnet_info.display_name,  # pragma: no cover - Build minimal torrent data from magnet, tested via integration tests
            magnet_info.trackers,
        )
    except Exception:  # pragma: no cover - defensive: parse_magnet error handling, returns None on failure
        if logger:
            logger.exception("Failed to parse magnet link")  # pragma: no cover
        return None  # pragma: no cover
