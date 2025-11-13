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
    """Information extracted from a magnet link (BEP 9 + BEP 53)."""

    info_hash: bytes
    display_name: str | None
    trackers: list[str]
    web_seeds: list[str]
    selected_indices: list[int] | None = None  # BEP 53: so parameter
    prioritized_indices: dict[int, int] | None = None  # BEP 53: x.pe parameter


def _hex_or_base32_to_bytes(btih: str) -> bytes:
    """Decode btih which can be hex (40 chars) or base32 (32 chars)."""
    btih = btih.strip()
    if len(btih) == 40:
        # Hex
        return bytes.fromhex(btih)
    # Base32
    import base64  # pragma: no cover - import statement

    return base64.b32decode(btih.upper())


def _parse_index_list(index_str: str) -> list[int]:
    """Parse comma-separated file indices with optional ranges (BEP 53).

    Examples:
        "0,2,4" -> [0, 2, 4]
        "0-5" -> [0, 1, 2, 3, 4, 5]
        "0,3-5,8" -> [0, 3, 4, 5, 8]
        "1, 3 , 5-7" -> [1, 3, 5, 6, 7] (handles whitespace)

    Args:
        index_str: Comma-separated indices and ranges

    Returns:
        Sorted list of unique indices

    Raises:
        ValueError: If format is invalid

    """
    if not index_str.strip():
        return []

    indices: set[int] = set()

    for raw_token in index_str.split(","):
        token = raw_token.strip()
        if not token:
            continue

        if "-" in token:
            # Range format: "start-end"
            try:
                parts = token.split("-", 1)
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                if start < 0 or end < 0:
                    msg = f"Negative indices not allowed: {token}"
                    raise ValueError(msg)
                if start > end:
                    msg = f"Invalid range: start > end in {token}"
                    raise ValueError(msg)
                indices.update(range(start, end + 1))
            except (ValueError, IndexError) as e:
                msg = f"Invalid range format '{token}': {e}"
                raise ValueError(msg) from e
        else:
            # Single index
            try:
                idx = int(token)
                if idx < 0:  # pragma: no cover
                    # Defensive check: unreachable via string parsing API because
                    # negative numbers in string form always contain "-" which routes
                    # to range branch. This check protects against edge cases or
                    # direct integer injection (not possible via current API).
                    msg = f"Negative index not allowed: {idx}"
                    raise ValueError(msg)
                indices.add(idx)
            except ValueError as e:
                msg = f"Invalid index format '{token}': {e}"
                raise ValueError(msg) from e

    return sorted(indices)


def _parse_prioritized_indices(priority_str: str) -> dict[int, int]:
    """Parse x.pe parameter format: file_index:priority pairs (BEP 53).

    Examples:
        "0:4,2:3" -> {0: 4, 2: 3}  # file 0 priority 4, file 2 priority 3
        "1:2" -> {1: 2}
        "0:4,3-5:3" -> {0: 4, 3: 3, 4: 3, 5: 3}  # range support

    Args:
        priority_str: Comma-separated file_index:priority pairs

    Returns:
        Dictionary mapping file_index -> priority (0-4)

    Raises:
        ValueError: If format is invalid or priority out of range

    """
    if not priority_str.strip():
        return {}

    priorities: dict[int, int] = {}

    for raw_token in priority_str.split(","):
        token = raw_token.strip()
        if not token:
            continue

        if ":" not in token:
            msg = f"Missing ':' separator in priority pair: {token}"
            raise ValueError(msg)

        try:
            file_part, priority_part = token.rsplit(":", 1)
            file_part = file_part.strip()
            priority_part = priority_part.strip()

            priority = int(priority_part)
            if priority < 0 or priority > 4:
                msg = f"Priority must be 0-4 (got {priority} in '{token}')"
                raise ValueError(msg)

            # Parse file index (may be range or single)
            if "-" in file_part:
                # Range format: "start-end:priority"
                parts = file_part.split("-", 1)
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                if start < 0 or end < 0:
                    msg = f"Negative indices not allowed: {file_part}"
                    raise ValueError(msg)
                if start > end:
                    msg = f"Invalid range: start > end in {file_part}"
                    raise ValueError(msg)
                # Apply same priority to all indices in range
                for idx in range(start, end + 1):
                    priorities[idx] = priority
            else:
                # Single index
                file_index = int(file_part)
                if file_index < 0:  # pragma: no cover
                    # Defensive check: unreachable via string parsing API because
                    # negative numbers in string form always contain "-" which routes
                    # to range branch. This check protects against edge cases or
                    # direct integer injection (not possible via current API).
                    msg = f"Negative index not allowed: {file_index}"
                    raise ValueError(msg)
                priorities[file_index] = priority

        except (ValueError, IndexError) as e:
            msg = f"Invalid priority pair format '{token}': {e}"
            raise ValueError(msg) from e

    return priorities


def parse_magnet(uri: str) -> MagnetInfo:
    """Parse a magnet URI and return `MagnetInfo`.

    Supports: xt=urn:btih:<hash>, dn, tr (multiple), ws (multiple).
    BEP 53: so (selected indices), x.pe (prioritized indices).
    """
    import logging  # pragma: no cover - import statement

    logger = logging.getLogger(__name__)

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

    # BEP 53: Parse so parameter (selected file indices)
    selected_indices = None
    so_values = qs.get("so", [])
    if so_values:
        try:
            # Take first so value (per BEP 53, multiple may be present)
            selected_indices = _parse_index_list(so_values[0])
        except (ValueError, IndexError) as e:
            # Log warning but don't fail parsing
            logger.warning("Invalid 'so' parameter in magnet URI: %s", e)
            selected_indices = None

    # BEP 53: Parse x.pe parameter (prioritized file indices)
    prioritized_indices = None
    x_pe_values = qs.get("x.pe", [])
    if x_pe_values:
        try:
            # Take first x.pe value
            prioritized_indices = _parse_prioritized_indices(x_pe_values[0])
        except (ValueError, IndexError) as e:
            logger.warning("Invalid 'x.pe' parameter in magnet URI: %s", e)
            prioritized_indices = None

    return MagnetInfo(
        info_hash=info_hash,
        display_name=display_name,
        trackers=trackers,
        web_seeds=web_seeds,
        selected_indices=selected_indices,
        prioritized_indices=prioritized_indices,
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
        "is_magnet": True,  # CRITICAL: Mark as magnet link for DHT setup to prioritize DHT queries
    }


def validate_and_normalize_indices(
    indices: list[int] | None,
    num_files: int,
    parameter_name: str = "indices",
) -> list[int]:
    """Validate file indices against actual file count (BEP 53).

    Args:
        indices: List of file indices from magnet URI
        num_files: Actual number of files in torrent
        parameter_name: Name of parameter for error messages

    Returns:
        Validated, sorted, deduplicated list of indices in range [0, num_files)

    """
    import logging  # pragma: no cover - import statement

    logger = logging.getLogger(__name__)

    if not indices:
        return []

    if num_files <= 0:
        logger.warning(
            "Cannot validate %s: torrent has no files (num_files=%d)",
            parameter_name,
            num_files,
        )
        return []

    valid_indices: list[int] = []
    invalid_count = 0

    for idx in indices:
        if 0 <= idx < num_files:
            valid_indices.append(idx)
        else:
            invalid_count += 1
            logger.debug(
                "File index %d from %s is out of range [0, %d), ignoring",
                idx,
                parameter_name,
                num_files,
            )

    if invalid_count > 0:
        logger.warning(
            "Filtered out %d invalid file indices from %s (out of %d total files)",
            invalid_count,
            parameter_name,
            num_files,
        )

    # Deduplicate and sort
    return sorted(set(valid_indices))


def build_torrent_data_from_metadata(  # pragma: no cover - BEP 9 (not BEP 53), tested in test_magnet.py
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
    if not isinstance(file_info, dict):  # pragma: no cover
        # Defensive type check: file_info is always a dict from the branches above.
        # This check exists for type checker satisfaction but is unreachable in practice.
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

    # Extract private flag from info dictionary (BEP 27)
    private_value = info_dict.get(b"private", 0)
    is_private = bool(private_value)

    return {
        "announce": "",
        "announce_list": [],
        "info_hash": info_hash,
        "info": info_dict,
        "file_info": file_info,
        "pieces_info": pieces_info,
        "name": file_info["name"],
        "is_private": is_private,
    }


async def apply_magnet_file_selection(
    file_selection_manager: Any,
    magnet_info: MagnetInfo,
    num_files: int,
    respect_indices: bool = True,
) -> None:
    """Apply file selection from magnet URI indices (BEP 53).

    Args:
        file_selection_manager: FileSelectionManager instance
        magnet_info: Parsed magnet info with indices
        num_files: Number of files in torrent
        respect_indices: Whether to respect indices (from config)

    Raises:
        ValueError: If indices are invalid (in strict mode)

    """
    import logging  # pragma: no cover - import statement

    from ccbt.piece.file_selection import FilePriority

    logger = logging.getLogger(__name__)

    if not respect_indices:
        logger.debug("Magnet index respect disabled, skipping file selection")
        return

    # Skip single-file torrents
    if num_files <= 1:
        logger.debug("Single-file torrent, skipping magnet file selection")
        return

    # Validate and normalize selected indices
    selected_indices = None
    if magnet_info.selected_indices:
        selected_indices = validate_and_normalize_indices(
            magnet_info.selected_indices,
            num_files,
            parameter_name="so",
        )
        if selected_indices:
            # Deselect all files first, then select only specified indices
            await file_selection_manager.deselect_all()
            await file_selection_manager.select_files(selected_indices)
            logger.info(
                "Applied magnet file selection: selected %d file(s) from 'so' parameter",
                len(selected_indices),
            )
        else:
            logger.warning(
                "Magnet 'so' parameter provided but no valid indices after validation",
            )

    # Apply priorities from x.pe parameter
    if magnet_info.prioritized_indices:
        priority_count = 0
        for file_index, priority_value in magnet_info.prioritized_indices.items():
            # Validate file index
            if 0 <= file_index < num_files:
                # Convert integer priority to FilePriority enum
                try:
                    priority = FilePriority(priority_value)
                    await file_selection_manager.set_file_priority(file_index, priority)
                    priority_count += 1
                except ValueError:
                    logger.warning(
                        "Invalid priority value %d for file %d (must be 0-4)",
                        priority_value,
                        file_index,
                    )
            else:
                logger.debug(
                    "File index %d from 'x.pe' is out of range [0, %d), ignoring",
                    file_index,
                    num_files,
                )

        if priority_count > 0:
            logger.info(
                "Applied magnet file priorities: set priority for %d file(s) from 'x.pe' parameter",
                priority_count,
            )


def generate_magnet_link(
    info_hash: bytes,
    display_name: str | None = None,
    trackers: list[str] | None = None,
    web_seeds: list[str] | None = None,
    selected_indices: list[int] | None = None,
    prioritized_indices: dict[int, int] | None = None,
    use_base32: bool = False,
) -> str:
    """Generate a magnet URI with optional file indices (BEP 53).

    Args:
        info_hash: 20-byte info hash
        display_name: Optional display name (dn parameter)
        trackers: Optional list of tracker URLs (tr parameters)
        web_seeds: Optional list of web seed URLs (ws parameters)
        selected_indices: Optional list of file indices for so parameter
        prioritized_indices: Optional dict of file_index->priority for x.pe parameter
        use_base32: Whether to encode info hash as base32 (default: hex)

    Returns:
        Complete magnet URI string

    """
    import base64  # pragma: no cover - import statement

    # Build base magnet URI
    parts = ["magnet:?xt=urn:btih:"]

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

    # Add web seeds
    if web_seeds:
        for web_seed in web_seeds:
            encoded_web_seed = urllib.parse.quote(web_seed, safe=":/?#[]@!$&'()*+,;=")
            parts.append(f"ws={encoded_web_seed}")

    # Add so parameter (selected indices)
    if selected_indices:
        # Format as comma-separated indices (ranges can be optimized but we'll use simple format)
        so_value = ",".join(str(idx) for idx in sorted(set(selected_indices)))
        parts.append(f"so={so_value}")

    # Add x.pe parameter (prioritized indices)
    if prioritized_indices:
        # Format as "file_index:priority" pairs
        pe_parts = []
        for file_idx in sorted(prioritized_indices.keys()):
            priority = prioritized_indices[file_idx]
            pe_parts.append(f"{file_idx}:{priority}")
        x_pe_value = ",".join(pe_parts)
        parts.append(f"x.pe={x_pe_value}")

    return "&".join(parts)
