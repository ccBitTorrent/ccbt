"""Unit tests for XetHasher (keyed BLAKE3, aggregated Merkle)."""

from __future__ import annotations

import pytest

from ccbt.storage.xet_chunking import GearhashChunker
from ccbt.storage.xet_hashing import XetHasher, hash_to_hex, hex_to_hash


class TestXetHasher:
    def test_chunk_hash_deterministic(self) -> None:
        assert XetHasher.compute_chunk_hash(b"abc") == XetHasher.compute_chunk_hash(b"abc")
        assert XetHasher.compute_chunk_hash(b"abc") != XetHasher.compute_chunk_hash(b"abd")

    def test_chunk_hash_size(self) -> None:
        assert len(XetHasher.compute_chunk_hash(b"x")) == 32

    def test_no_sha256_fallback(self) -> None:
        with pytest.raises(ValueError):
            XetHasher.compute_chunk_hash(b"x", algorithm="sha256")
        assert XetHasher.normalize_hash_algorithm(None) == "blake3"
        assert XetHasher.get_hash_algorithm() == "blake3"

    def test_verify_chunk_hash(self) -> None:
        data = b"verify me"
        h = XetHasher.compute_chunk_hash(data)
        assert XetHasher.verify_chunk_hash(data, h)
        assert not XetHasher.verify_chunk_hash(b"other", h)
        assert not XetHasher.verify_chunk_hash(data, b"short")

    def test_merkle_from_data_and_hashes_agree(self) -> None:
        chunks = [b"a" * 100, b"b" * 200, b"c" * 300]
        pairs = [(XetHasher.compute_chunk_hash(c), len(c)) for c in chunks]
        assert XetHasher.build_merkle_tree(chunks) == XetHasher.aggregated_hash(pairs)
        assert XetHasher.build_merkle_tree_from_hashes(
            [h for h, _ in pairs], sizes=[s for _, s in pairs]
        ) == XetHasher.aggregated_hash(pairs)

    def test_file_hash_differs_from_xorb_hash(self) -> None:
        pairs = [(XetHasher.compute_chunk_hash(b"a" * 10), 10)]
        assert XetHasher.compute_file_hash(pairs) != XetHasher.compute_xorb_hash(pairs)

    def test_hex_roundtrip(self) -> None:
        h = XetHasher.compute_chunk_hash(b"hex")
        assert hex_to_hash(hash_to_hex(h)) == h
        with pytest.raises(ValueError):
            hex_to_hash("zz")

    def test_range_hash(self) -> None:
        hs = [XetHasher.compute_chunk_hash(bytes([i]) * 50) for i in range(3)]
        assert len(XetHasher.compute_range_hash(hs)) == 32
        assert XetHasher.compute_range_hash(hs) != XetHasher.compute_range_hash(hs[::-1])

    def test_invalid_hash_size_rejected(self) -> None:
        with pytest.raises(ValueError):
            XetHasher.build_merkle_tree_from_hashes([b"short"])

    def test_hash_file_incremental(self, tmp_path) -> None:
        data = bytes(range(256)) * 3000
        p = tmp_path / "f.bin"
        p.write_bytes(data)
        chunker_pairs = []
        for c in GearhashChunker().chunk_buffer(data):
            chunker_pairs.append((XetHasher.compute_chunk_hash(c), len(c)))
        assert XetHasher.hash_file_incremental(str(p)) == XetHasher.compute_file_hash(chunker_pairs)
