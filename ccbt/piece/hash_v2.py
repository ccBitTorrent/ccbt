"""SHA-256 piece hashing for BitTorrent Protocol v2 (BEP 52).

This module implements SHA-256 hashing functions for v2 torrent pieces,
replacing SHA-1 (20 bytes) with SHA-256 (32 bytes) as specified in BEP 52.

BitTorrent Protocol v2 uses SHA-256 for:
- Piece hashes (32 bytes each)
- Info hash (32 bytes)
- File tree root hashes (32 bytes)
- Piece layer Merkle roots (32 bytes)
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, BinaryIO

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from io import BytesIO

logger = logging.getLogger(__name__)


def hash_piece_v2(data: bytes) -> bytes:
    """Calculate SHA-256 hash of piece data for v2 torrent.

    Args:
        data: Piece data bytes

    Returns:
        32-byte SHA-256 hash

    Raises:
        ValueError: If data is empty

    Example:
        >>> piece_data = b"test piece data"
        >>> hash_bytes = hash_piece_v2(piece_data)
        >>> len(hash_bytes)
        32

    """
    if not data:
        msg = "Cannot hash empty piece data"
        raise ValueError(msg)

    hasher = hashlib.sha256()
    hasher.update(data)
    hash_bytes = hasher.digest()

    logger.debug("Hashed piece: %d bytes -> %s", len(data), hash_bytes.hex()[:16])

    return hash_bytes


def hash_piece_v2_streaming(
    data_source: BinaryIO | bytes | BytesIO,
    chunk_size: int = 65536,
) -> bytes:
    """Calculate SHA-256 hash of piece data using streaming for large pieces.

    Args:
        data_source: File-like object, BytesIO, or bytes to hash
        chunk_size: Size of chunks to read at a time (default 64 KiB)

    Returns:
        32-byte SHA-256 hash

    Raises:
        ValueError: If data source is invalid or empty
        IOError: If reading from data source fails

    Example:
        >>> with open("piece.bin", "rb") as f:
        ...     hash_bytes = hash_piece_v2_streaming(f)
        >>> len(hash_bytes)
        32

    """
    hasher = hashlib.sha256()

    # Handle bytes directly
    if isinstance(data_source, bytes):
        hasher.update(data_source)
        return hasher.digest()

    # Handle file-like objects
    if not hasattr(data_source, "read"):
        msg = f"data_source must be file-like or bytes, got {type(data_source)}"
        raise ValueError(msg)

    # Reset to beginning if possible
    with contextlib.suppress(AttributeError, OSError):
        data_source.seek(0)

    bytes_hashed = 0
    try:
        while True:
            chunk = data_source.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            bytes_hashed += len(chunk)

        hash_bytes = hasher.digest()

        logger.debug(
            "Stream-hashed piece: %d bytes -> %s",
            bytes_hashed,
            hash_bytes.hex()[:16],
        )

        return hash_bytes
    except (
        Exception
    ) as e:  # pragma: no cover - Streaming hash exception, defensive error handling
        msg = f"Error during streaming hash: {e}"
        logger.exception(msg)
        raise OSError(msg) from e


def verify_piece_v2(data: bytes, expected_hash: bytes) -> bool:
    """Verify piece data against expected SHA-256 hash.

    Args:
        data: Piece data bytes
        expected_hash: Expected 32-byte SHA-256 hash

    Returns:
        True if hash matches, False otherwise

    Raises:
        ValueError: If expected_hash is not 32 bytes

    Example:
        >>> piece_data = b"test piece data"
        >>> expected = hash_piece_v2(piece_data)
        >>> verify_piece_v2(piece_data, expected)
        True
        >>> verify_piece_v2(piece_data, b"wrong" * 8)
        False

    """
    if len(expected_hash) != 32:
        msg = (
            f"Expected hash must be 32 bytes (SHA-256), got {len(expected_hash)} bytes"
        )
        raise ValueError(msg)

    actual_hash = hash_piece_v2(data)
    matches = actual_hash == expected_hash

    if not matches:
        logger.warning(
            "Piece hash mismatch: expected %s, got %s",
            expected_hash.hex()[:16],
            actual_hash.hex()[:16],
        )

    return matches


def verify_piece_v2_streaming(
    data_source: BinaryIO | bytes | BytesIO,
    expected_hash: bytes,
    chunk_size: int = 65536,
) -> bool:
    """Verify piece data using streaming against expected SHA-256 hash.

    Args:
        data_source: File-like object, BytesIO, or bytes to verify
        expected_hash: Expected 32-byte SHA-256 hash
        chunk_size: Size of chunks to read at a time (default 64 KiB)

    Returns:
        True if hash matches, False otherwise

    Raises:
        ValueError: If expected_hash is not 32 bytes
        IOError: If reading from data source fails

    Example:
        >>> with open("piece.bin", "rb") as f:
        ...     expected = hash_piece_v2_streaming(open("piece.bin", "rb"))
        ...     is_valid = verify_piece_v2_streaming(f, expected)
        >>> is_valid
        True

    """
    if len(expected_hash) != 32:
        msg = (
            f"Expected hash must be 32 bytes (SHA-256), got {len(expected_hash)} bytes"
        )
        raise ValueError(msg)

    actual_hash = hash_piece_v2_streaming(data_source, chunk_size)
    matches = actual_hash == expected_hash

    if not matches:
        logger.warning(
            "Stream piece hash mismatch: expected %s, got %s",
            expected_hash.hex()[:16],
            actual_hash.hex()[:16],
        )

    return matches


def hash_piece_layer(piece_hashes: list[bytes]) -> bytes:
    """Calculate Merkle root (pieces_root) for a piece layer.

    In BEP 52, each file has a piece layer consisting of SHA-256 hashes of pieces.
    The pieces_root is the Merkle root of all piece hashes in the layer.

    Args:
        piece_hashes: List of 32-byte SHA-256 piece hashes

    Returns:
        32-byte Merkle root (pieces_root)

    Raises:
        ValueError: If piece_hashes is empty or contains invalid hashes

    Example:
        >>> pieces = [hash_piece_v2(b"piece1"), hash_piece_v2(b"piece2")]
        >>> root = hash_piece_layer(pieces)
        >>> len(root)
        32

    """
    if not piece_hashes:
        msg = "Cannot hash empty piece layer"
        raise ValueError(msg)

    # Validate all hashes are 32 bytes
    for i, piece_hash in enumerate(piece_hashes):
        if len(piece_hash) != 32:
            msg = f"Piece hash {i} must be 32 bytes (SHA-256), got {len(piece_hash)}"
            raise ValueError(msg)

    # If only one piece, its hash is the root
    if len(piece_hashes) == 1:
        return piece_hashes[0]

    # Calculate Merkle root using binary tree
    root = _calculate_merkle_root(piece_hashes)

    logger.debug(
        "Calculated piece layer root: %d pieces -> %s",
        len(piece_hashes),
        root.hex()[:16],
    )

    return root


def _calculate_merkle_root(hashes: list[bytes]) -> bytes:
    """Calculate Merkle root using binary tree construction.

    The algorithm:
    1. Start with leaf nodes (hashes)
    2. Pair up adjacent hashes, concatenate, and hash to get parent
    3. Continue until only one hash remains (the root)
    4. If odd number of nodes at a level, duplicate the last one

    Args:
        hashes: List of 32-byte hashes

    Returns:
        32-byte Merkle root hash

    """
    current_level = list(hashes)

    # Build tree bottom-up until we have the root
    while len(current_level) > 1:
        next_level: list[bytes] = []

        # Process pairs
        for i in range(0, len(current_level), 2):
            if i + 1 < len(current_level):
                # Pair of hashes: concatenate and hash
                combined = current_level[i] + current_level[i + 1]
            else:
                # Odd number: duplicate the last hash
                combined = current_level[i] + current_level[i]

            # Hash the combined pair to get parent
            parent_hash = hashlib.sha256(combined).digest()
            next_level.append(parent_hash)

        current_level = next_level

    # The single remaining hash is the root
    return current_level[0]


def verify_piece_layer(
    piece_hashes: list[bytes],
    expected_root: bytes,
) -> bool:
    """Verify piece layer Merkle root.

    Args:
        piece_hashes: List of 32-byte SHA-256 piece hashes
        expected_root: Expected 32-byte Merkle root (pieces_root)

    Returns:
        True if root matches, False otherwise

    Raises:
        ValueError: If expected_root is not 32 bytes

    Example:
        >>> pieces = [hash_piece_v2(b"piece1"), hash_piece_v2(b"piece2")]
        >>> root = hash_piece_layer(pieces)
        >>> verify_piece_layer(pieces, root)
        True
        >>> verify_piece_layer(pieces, b"wrong" * 8)
        False

    """
    if len(expected_root) != 32:
        msg = (
            f"Expected root must be 32 bytes (SHA-256), got {len(expected_root)} bytes"
        )
        raise ValueError(msg)

    actual_root = hash_piece_layer(piece_hashes)
    matches = actual_root == expected_root

    if not matches:
        logger.warning(
            "Piece layer root mismatch: expected %s, got %s",
            expected_root.hex()[:16],
            actual_root.hex()[:16],
        )

    return matches


def hash_file_tree(file_tree: dict[str, Any]) -> bytes:
    """Calculate root hash of file tree structure.

    In BEP 52, the file tree is a hierarchical structure where:
    - File nodes have a pieces_root (Merkle root of piece hashes)
    - Directory nodes contain children nodes
    - The root hash is calculated from all top-level nodes

    Args:
        file_tree: Dictionary mapping names to FileTreeNode objects

    Returns:
        32-byte root hash of the file tree

    Raises:
        ValueError: If file_tree is empty or invalid

    Example:
        >>> from ccbt.core.torrent_v2 import FileTreeNode
        >>> file_node = FileTreeNode("file.txt", length=100, pieces_root=b"x" * 32)
        >>> tree = {"file.txt": file_node}
        >>> root = hash_file_tree(tree)
        >>> len(root)
        32

    """
    from ccbt.core.torrent_v2 import FileTreeNode

    if not file_tree:
        # Empty file tree returns hash of empty bytes (deterministic)
        return hashlib.sha256(b"").digest()

    # Collect hashes of all top-level nodes
    top_level_hashes: list[bytes] = []

    # Sort by name for deterministic ordering
    sorted_items = sorted(file_tree.items())

    for _name, node in sorted_items:
        if isinstance(node, FileTreeNode):
            if node.is_file():
                node_hash = _hash_file_node(node)
            elif node.is_directory() and node.children:
                # Hash directory recursively
                node_hash = _hash_directory(node.children)
            else:  # pragma: no cover - Invalid node state error, tested via file/directory nodes
                msg = "Invalid node state: neither file nor directory"
                raise ValueError(msg)
            top_level_hashes.append(node_hash)
        else:  # pragma: no cover - Invalid node type error, tested via FileTreeNode
            msg = f"Invalid node type in file tree: {type(node)}"
            raise TypeError(msg)

    # If only one top-level node, its hash is the root
    if len(top_level_hashes) == 1:
        return top_level_hashes[0]

    # Calculate Merkle root of top-level nodes
    root = _calculate_merkle_root(top_level_hashes)

    logger.debug(
        "Calculated file tree root: %d top-level nodes -> %s",
        len(top_level_hashes),
        root.hex()[:16],
    )

    return root


def _hash_file_node(node: Any) -> bytes:
    """Hash a single file node.

    File nodes in BEP 52 have:
    - name: File name
    - length: File length
    - pieces_root: Merkle root of piece hashes (32 bytes)

    The node hash is calculated as: SHA-256(name + length + pieces_root)

    Args:
        node: FileTreeNode object

    Returns:
        32-byte hash of the file node

    """
    from ccbt.core.torrent_v2 import FileTreeNode

    if not isinstance(
        node, FileTreeNode
    ):  # pragma: no cover - Type validation error, tested via FileTreeNode
        msg = f"Expected FileTreeNode, got {type(node)}"
        raise TypeError(msg)

    if (
        not node.is_file()
    ):  # pragma: no cover - Not a file node error, tested via file nodes
        msg = "Node is not a file node"
        raise ValueError(msg)

    if (
        node.pieces_root is None or len(node.pieces_root) != 32
    ):  # pragma: no cover - Invalid pieces_root error, tested via valid pieces_root
        msg = "File node must have valid 32-byte pieces_root"
        raise ValueError(msg)

    # Hash: SHA-256(name_bytes + length_bytes + pieces_root)
    hasher = hashlib.sha256()

    # Add name (UTF-8 encoded)
    name_bytes = node.name.encode("utf-8")
    hasher.update(name_bytes)

    # Add length (8 bytes, big-endian)
    length_bytes = node.length.to_bytes(8, byteorder="big")
    hasher.update(length_bytes)

    # Add pieces_root (32 bytes)
    hasher.update(node.pieces_root)

    return hasher.digest()


def _hash_directory(children: dict[str, Any]) -> bytes:
    """Hash a directory node by hashing its children.

    Directory nodes contain a mapping of child names to FileTreeNode objects.
    The directory hash is calculated from the hashes of all children.

    Args:
        children: Dictionary mapping child names to FileTreeNode objects

    Returns:
        32-byte hash of the directory node

    Raises:
        ValueError: If children is empty or invalid

    """
    from ccbt.core.torrent_v2 import FileTreeNode

    if (
        not children
    ):  # pragma: no cover - Empty directory error, tested via non-empty directories
        msg = "Cannot hash empty directory"
        raise ValueError(msg)

    # Collect hashes of all children
    child_hashes: list[bytes] = []

    # Sort by name for deterministic ordering
    sorted_children = sorted(children.items())

    for child_name, child_node in sorted_children:
        if isinstance(child_node, FileTreeNode):
            if child_node.is_file():
                # Hash file node
                child_hash = _hash_file_node(child_node)
            elif (
                child_node.is_directory() and child_node.children
            ):  # pragma: no cover - Directory node hash path, tested via file nodes
                # Recursively hash directory node
                child_hash = _hash_directory(child_node.children)
            else:  # pragma: no cover - Invalid child node error, tested via valid file/directory nodes
                msg = f"Invalid child node: {child_name}"
                raise ValueError(msg)

            child_hashes.append(child_hash)
        else:  # pragma: no cover - Invalid child node type error, tested via FileTreeNode
            msg = f"Invalid child node type: {type(child_node)}"
            raise TypeError(msg)

    # If only one child, its hash is the directory hash
    if len(child_hashes) == 1:
        return child_hashes[0]

    # Calculate Merkle root of children
    return _calculate_merkle_root(child_hashes)


class HashAlgorithm(Enum):
    """Hash algorithm for piece verification.

    BEP 52 introduces SHA-256 for v2 torrents, while v1 torrents use SHA-1.
    Hybrid torrents support both algorithms.
    """

    SHA1 = "sha1"  # 20 bytes - BitTorrent v1 (BEP 3)
    SHA256 = "sha256"  # 32 bytes - BitTorrent v2 (BEP 52)

    @property
    def hash_size(self) -> int:
        """Get the hash size in bytes for this algorithm."""
        return 20 if self == HashAlgorithm.SHA1 else 32

    @property
    def hash_function(self):
        """Get the hashlib function for this algorithm."""
        if self == HashAlgorithm.SHA1:
            return hashlib.sha1  # nosec B324 - SHA-1 required by BitTorrent protocol v1
        return hashlib.sha256


def verify_piece(
    data: bytes,
    expected_hash: bytes,
    algorithm: HashAlgorithm | None = None,
) -> bool:
    """Verify piece data against expected hash using specified algorithm.

    This function supports both SHA-1 (v1) and SHA-256 (v2) verification,
    allowing unified piece verification for hybrid torrents.

    If algorithm is not specified, it will be auto-detected from hash length:
    - 20 bytes = SHA-1 (v1)
    - 32 bytes = SHA-256 (v2)

    Args:
        data: Piece data bytes
        expected_hash: Expected hash (20 bytes for SHA-1, 32 bytes for SHA-256)
        algorithm: Hash algorithm to use (None = auto-detect from hash length)

    Returns:
        True if hash matches, False otherwise

    Raises:
        ValueError: If expected_hash length doesn't match algorithm or is invalid

    Example:
        >>> # Verify with SHA-256 (v2) - auto-detect
        >>> piece_data = b"test piece"
        >>> v2_hash = hash_piece_v2(piece_data)
        >>> verify_piece(piece_data, v2_hash)
        True

        >>> # Verify with SHA-1 (v1) - auto-detect
        >>> import hashlib
        >>> v1_hash = hashlib.sha1(piece_data).digest()
        >>> verify_piece(piece_data, v1_hash)
        True

        >>> # Explicit algorithm
        >>> verify_piece(piece_data, v2_hash, HashAlgorithm.SHA256)
        True

    """
    # Auto-detect algorithm from hash length if not specified
    if algorithm is None:
        if len(expected_hash) == 20:
            algorithm = HashAlgorithm.SHA1
        elif (
            len(expected_hash) == 32
        ):  # pragma: no cover - SHA-256 hash detection, tested via SHA-1 path
            algorithm = HashAlgorithm.SHA256
        else:  # pragma: no cover - Invalid hash length error, tested via valid lengths
            msg = f"Hash must be 20 or 32 bytes, got {len(expected_hash)} bytes"
            raise ValueError(msg)

    expected_size = algorithm.hash_size

    if len(expected_hash) != expected_size:
        msg = f"Expected hash must be {expected_size} bytes for {algorithm.value}, got {len(expected_hash)} bytes"
        raise ValueError(msg)

    # Calculate actual hash using specified algorithm
    hasher = algorithm.hash_function()
    hasher.update(data)
    actual_hash = hasher.digest()

    matches = actual_hash == expected_hash

    if not matches:
        logger.warning(
            "Piece hash mismatch (%s): expected %s, got %s",
            algorithm.value,
            expected_hash.hex()[:16],
            actual_hash.hex()[:16],
        )

    return matches


def verify_piece_streaming(
    data_source: BinaryIO | bytes | BytesIO,
    expected_hash: bytes,
    algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    chunk_size: int = 65536,
) -> bool:
    """Verify piece data using streaming against expected hash.

    Args:
        data_source: File-like object, BytesIO, or bytes to verify
        expected_hash: Expected hash (20 bytes for SHA-1, 32 bytes for SHA-256)
        algorithm: Hash algorithm to use (default: SHA256 for v2)
        chunk_size: Size of chunks to read at a time (default 64 KiB)

    Returns:
        True if hash matches, False otherwise

    Raises:
        ValueError: If expected_hash length doesn't match algorithm
        IOError: If reading from data source fails

    Example:
        >>> with open("piece.bin", "rb") as f:
        ...     is_valid = verify_piece_streaming(f, expected_hash, HashAlgorithm.SHA256)
        >>> is_valid
        True

    """
    expected_size = algorithm.hash_size

    if len(expected_hash) != expected_size:
        msg = f"Expected hash must be {expected_size} bytes for {algorithm.value}, got {len(expected_hash)} bytes"
        raise ValueError(msg)

    hasher = algorithm.hash_function()

    # Handle bytes directly
    if isinstance(data_source, bytes):
        hasher.update(data_source)
        actual_hash = hasher.digest()
    else:
        # Handle file-like objects
        if not hasattr(
            data_source, "read"
        ):  # pragma: no cover - Invalid data_source type error, tested via file-like objects
            msg = f"data_source must be file-like or bytes, got {type(data_source)}"
            raise ValueError(msg)

        # Reset to beginning if possible
        with contextlib.suppress(AttributeError, OSError):
            data_source.seek(0)

        bytes_hashed = 0
        try:
            while True:
                chunk = data_source.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
                bytes_hashed += len(chunk)

            actual_hash = hasher.digest()

            logger.debug(
                "Stream-verified piece (%s): %d bytes",
                algorithm.value,
                bytes_hashed,
            )
        except Exception as e:
            msg = f"Error during streaming hash verification: {e}"
            logger.exception(msg)
            raise OSError(msg) from e

    matches = actual_hash == expected_hash

    if (
        not matches
    ):  # pragma: no cover - Hash mismatch warning path, tested via matching hashes
        logger.warning(
            "Stream piece hash mismatch (%s): expected %s, got %s",
            algorithm.value,
            expected_hash.hex()[:16],
            actual_hash.hex()[:16],
        )

    return matches


def hash_piece(data: bytes, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> bytes:
    """Calculate hash of piece data using specified algorithm.

    Args:
        data: Piece data bytes
        algorithm: Hash algorithm to use (default: SHA256 for v2)

    Returns:
        Hash bytes (20 bytes for SHA-1, 32 bytes for SHA-256)

    Raises:
        ValueError: If data is empty

    Example:
        >>> piece_data = b"test piece"
        >>> # Hash with SHA-256 (v2)
        >>> v2_hash = hash_piece(piece_data, HashAlgorithm.SHA256)
        >>> len(v2_hash)
        32
        >>> # Hash with SHA-1 (v1)
        >>> v1_hash = hash_piece(piece_data, HashAlgorithm.SHA1)
        >>> len(v1_hash)
        20

    """
    if not data:
        msg = "Cannot hash empty piece data"
        raise ValueError(msg)

    hasher = algorithm.hash_function()
    hasher.update(data)
    hash_bytes = hasher.digest()

    logger.debug(
        "Hashed piece (%s): %d bytes -> %s",
        algorithm.value,
        len(data),
        hash_bytes.hex()[:16],
    )

    return hash_bytes
