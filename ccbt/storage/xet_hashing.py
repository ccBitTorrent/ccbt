r"""Xet protocol hashing (upstream suite XET-BLAKE3-GEARHASH-LZ4).

Implements the hashing construction from the Hugging Face Xet
specification (xet-core ``merklehash``):

- chunk hash: BLAKE3 keyed hash with ``DATA_KEY``
- internal Merkle node: BLAKE3 keyed hash with ``INTERNAL_NODE_KEY`` over
  ``"{hash_hex} : {size}\n"`` lines for a group of (hash, size) pairs
- aggregated (xorb) hash: iterative grouping with branching factor 4
  (groups of 2..9, cut when the next hash satisfies ``hash % 4 == 0``)
- file hash: aggregated root rehashed with a 32-byte zero key
- term verification: BLAKE3 keyed hash with ``VERIFICATION_KEY`` over the
  concatenated raw chunk hashes of the term
- shard chunk-hash protection ("HMAC"): keyed BLAKE3 of the hash bytes

MerkleHash hex encoding follows upstream ``DataHash::hex``: each 8-byte
block is interpreted as a little-endian u64 and printed as 16 lowercase
hex digits, so hex is block-reversed relative to a raw ``bytes.hex()``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from collections.abc import Callable

from ccbt.storage.xet_chunking import GearhashChunker

try:
    import blake3
except ImportError:  # pragma: no cover
    blake3 = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Keys from the Xet specification (xet-core data_hash.rs).
DATA_KEY = bytes(
    [
        102,
        151,
        245,
        119,
        91,
        149,
        80,
        222,
        49,
        53,
        203,
        172,
        165,
        151,
        24,
        28,
        157,
        228,
        33,
        16,
        155,
        235,
        43,
        88,
        180,
        208,
        176,
        75,
        147,
        173,
        242,
        41,
    ]
)
INTERNAL_NODE_KEY = bytes(
    [
        1,
        126,
        197,
        199,
        165,
        71,
        41,
        150,
        253,
        148,
        102,
        102,
        180,
        138,
        2,
        230,
        93,
        221,
        83,
        111,
        55,
        199,
        109,
        210,
        248,
        99,
        82,
        230,
        74,
        83,
        113,
        63,
    ]
)
VERIFICATION_KEY = bytes(
    [
        127,
        24,
        87,
        214,
        206,
        86,
        237,
        102,
        18,
        127,
        249,
        19,
        231,
        165,
        195,
        243,
        164,
        205,
        38,
        213,
        181,
        219,
        73,
        230,
        65,
        36,
        152,
        127,
        40,
        251,
        148,
        195,
    ]
)
ZERO_KEY = bytes(32)

_BRANCHING_FACTOR = 4
_MAX_GROUP_SIZE = 2 * _BRANCHING_FACTOR + 1


def _keyed(data: bytes, key: bytes) -> bytes:
    if blake3 is None:  # pragma: no cover
        msg = "blake3 is required for XET hashing"
        raise RuntimeError(msg)
    return blake3.blake3(data, key=key).digest()


def hash_to_hex(hash_bytes: bytes) -> str:
    """Encode a 32-byte hash the way upstream MerkleHash hex does."""
    if len(hash_bytes) != 32:
        msg = f"hash must be 32 bytes, got {len(hash_bytes)}"
        raise ValueError(msg)
    return "".join(
        f"{int.from_bytes(hash_bytes[i : i + 8], 'little'):016x}"
        for i in range(0, 32, 8)
    )


def hex_to_hash(text: str) -> bytes:
    """Decode an upstream MerkleHash hex string to raw 32 bytes."""
    if len(text) != 64:
        msg = f"hash hex must be 64 chars, got {len(text)}"
        raise ValueError(msg)
    out = bytearray()
    for i in range(0, 64, 16):
        out += int(text[i : i + 16], 16).to_bytes(8, "little")
    return bytes(out)


def truncate_hash(hash_bytes: bytes) -> int:
    """Upstream truncate_hash: first u64 (little-endian) of the hash."""
    return int.from_bytes(hash_bytes[:8], "little")


class XetHasher:
    """Xet hashing functions (single BLAKE3 suite, no fallback identity)."""

    HASH_SIZE = 32
    HASH_IDENTITY_PREFIX = "xet-hash:v2:"
    SUITE = "xet-blake3-gearhash-lz4:v2"

    @staticmethod
    def normalize_hash_algorithm(algorithm: Optional[str] = None) -> str:
        """Normalize a hash algorithm name; only blake3 exists in v2."""
        value = (algorithm or "blake3").lower()
        if value in {"auto", "blake3", "xet-hash:v1:blake3", "xet-hash:v2:blake3"}:
            return "blake3"
        msg = f"Unsupported XET hash algorithm for suite v2: {value}"
        raise ValueError(msg)

    @staticmethod
    def get_hash_identity(algorithm: Optional[str] = None) -> str:
        """Public method."""
        XetHasher.normalize_hash_algorithm(algorithm)
        return f"{XetHasher.HASH_IDENTITY_PREFIX}blake3"

    @staticmethod
    def get_hash_algorithm() -> str:
        """Public method."""
        return "blake3"

    @staticmethod
    def _resolve_algorithm(algorithm: Optional[str] = None) -> str:
        return XetHasher.normalize_hash_algorithm(algorithm)

    @staticmethod
    def compute_chunk_hash(chunk_data: bytes, algorithm: Optional[str] = None) -> bytes:
        """BLAKE3 keyed (DATA_KEY) hash of chunk bytes."""
        XetHasher.normalize_hash_algorithm(algorithm)
        return _keyed(chunk_data, DATA_KEY)

    @staticmethod
    def compute_internal_node_hash(data: bytes) -> bytes:
        """Public method."""
        return _keyed(data, INTERNAL_NODE_KEY)

    @staticmethod
    def hmac_hash(hash_bytes: bytes, key: bytes) -> bytes:
        """Keyed BLAKE3 of a hash (shard chunk-hash protection)."""
        if len(hash_bytes) != 32 or len(key) != 32:
            msg = "hmac_hash expects 32-byte hash and key"
            raise ValueError(msg)
        return _keyed(hash_bytes, key)

    @staticmethod
    def _merged_hash_of_sequence(pairs: list[tuple[bytes, int]]) -> tuple[bytes, int]:
        buf = "".join(f"{hash_to_hex(h)} : {size}\n" for h, size in pairs)
        return _keyed(buf.encode(), INTERNAL_NODE_KEY), sum(s for _, s in pairs)

    @staticmethod
    def _next_merge_cut(pairs: list[tuple[bytes, int]]) -> int:
        if len(pairs) <= 2:
            return len(pairs)
        end = min(_MAX_GROUP_SIZE, len(pairs))
        for i in range(2, end):
            h = pairs[i][0]
            if int.from_bytes(h[24:32], "little") % _BRANCHING_FACTOR == 0:
                return i + 1
        return end

    @staticmethod
    def aggregated_hash(pairs: list[tuple[bytes, int]]) -> bytes:
        """Aggregated Merkle root over ordered (chunk_hash, size) pairs."""
        if not pairs:
            return bytes(32)
        hv = list(pairs)
        while len(hv) > 1:
            nxt: list[tuple[bytes, int]] = []
            idx = 0
            while idx < len(hv):
                cut = idx + XetHasher._next_merge_cut(hv[idx:])
                nxt.append(XetHasher._merged_hash_of_sequence(hv[idx:cut]))
                idx = cut
            hv = nxt
        return hv[0][0]

    @staticmethod
    def compute_xorb_hash(
        chunks: list[tuple[bytes, int]], algorithm: Optional[str] = None
    ) -> bytes:
        """Xorb hash: aggregated root over its (chunk_hash, size) list."""
        XetHasher.normalize_hash_algorithm(algorithm)
        return XetHasher.aggregated_hash(list(chunks))

    @staticmethod
    def compute_file_hash(
        chunks: list[tuple[bytes, int]], algorithm: Optional[str] = None
    ) -> bytes:
        """File hash: aggregated root rehashed with the zero key."""
        XetHasher.normalize_hash_algorithm(algorithm)
        if not chunks:
            return bytes(32)
        return _keyed(XetHasher.aggregated_hash(list(chunks)), ZERO_KEY)

    @staticmethod
    def compute_range_hash(chunk_hashes: list[bytes]) -> bytes:
        """Term verification hash over concatenated raw chunk hashes."""
        return _keyed(b"".join(chunk_hashes), VERIFICATION_KEY)

    @staticmethod
    def build_merkle_tree(
        chunks: list[bytes], algorithm: Optional[str] = None
    ) -> bytes:
        """Aggregated root over chunk *data* (hashes each chunk first)."""
        pairs = [
            (XetHasher.compute_chunk_hash(c, algorithm=algorithm), len(c))
            for c in chunks
        ]
        return XetHasher.aggregated_hash(pairs)

    @staticmethod
    def build_merkle_tree_from_hashes(
        chunk_hashes: list[bytes],
        sizes: Optional[list[int]] = None,
        algorithm: Optional[str] = None,
    ) -> bytes:
        """Aggregated root over precomputed (hash, size) pairs.

        ``sizes`` is required for a correct upstream root; when omitted
        sizes default to 0, which matches upstream reference vectors
        with zero-length entries but is not a file hash. Prefer
        :meth:`compute_file_hash` for files.
        """
        _ = algorithm  # API compat with callers that pass algorithm=
        for h in chunk_hashes:
            if len(h) != XetHasher.HASH_SIZE:
                msg = f"Invalid hash size: expected {XetHasher.HASH_SIZE}, got {len(h)}"
                raise ValueError(msg)
        if sizes is None:
            sizes = [0] * len(chunk_hashes)
        if len(sizes) != len(chunk_hashes):
            msg = "sizes must match chunk_hashes length"
            raise ValueError(msg)
        return XetHasher.aggregated_hash(list(zip(chunk_hashes, sizes)))

    @staticmethod
    def verify_chunk_hash(
        chunk_data: bytes, expected_hash: bytes, algorithm: Optional[str] = None
    ) -> bool:
        """Public method."""
        if len(expected_hash) != XetHasher.HASH_SIZE:
            return False
        return (
            XetHasher.compute_chunk_hash(chunk_data, algorithm=algorithm)
            == expected_hash
        )

    @staticmethod
    def hash_file_incremental(
        file_path: str,
        chunk_callback: Optional[Callable[[bytes], None]] = None,
    ) -> bytes:
        """Stream a file through the chunker and return its file hash."""
        chunker = GearhashChunker()
        pairs: list[tuple[bytes, int]] = []
        with open(file_path, "rb") as f:
            while True:
                block = f.read(1024 * 1024)
                if not block:
                    break
                for chunk in chunker.feed(block):
                    pairs.append((XetHasher.compute_chunk_hash(chunk), len(chunk)))
                    if chunk_callback:
                        chunk_callback(chunk)
        for chunk in chunker.finalize():
            pairs.append((XetHasher.compute_chunk_hash(chunk), len(chunk)))
            if chunk_callback:
                chunk_callback(chunk)
        return XetHasher.compute_file_hash(pairs)
