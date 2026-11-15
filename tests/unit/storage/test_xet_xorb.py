"""Unit tests for Xorb (upstream serialization)."""

from __future__ import annotations

import pytest

from ccbt.storage.xet_hashing import XetHasher
from ccbt.storage.xet_xorb import MAX_XORB_CHUNKS, Xorb, byte_grouping_4, byte_ungrouping_4


def _xorb_with(chunks: list[bytes]) -> Xorb:
    x = Xorb()
    for c in chunks:
        assert x.add_chunk(XetHasher.compute_chunk_hash(c), c)
    return x


class TestXorb:
    def test_initialization(self) -> None:
        x = Xorb()
        assert x.get_chunk_count() == 0
        assert x.get_total_size() == 0
        assert not x.is_full()

    def test_add_chunk_invalid_hash(self) -> None:
        with pytest.raises(ValueError):
            Xorb().add_chunk(b"short", b"data")

    def test_serialize_empty(self) -> None:
        assert Xorb().serialize() == b""
        assert Xorb.deserialize(b"").get_chunk_count() == 0

    def test_roundtrip_uncompressed(self) -> None:
        chunks = [b"alpha" * 100, b"beta" * 200]
        x = _xorb_with(chunks)
        back = Xorb.deserialize(x.serialize())
        assert [d for _h, d in back.chunks] == chunks
        assert back.get_xorb_hash() == x.get_xorb_hash()

    def test_roundtrip_compressed(self) -> None:
        chunks = [b"a" * 5000, bytes(range(256)) * 40]
        x = _xorb_with(chunks)
        raw = x.serialize(compress=True)
        back = Xorb.deserialize(raw)
        assert [d for _h, d in back.chunks] == chunks
        assert len(raw) < len(x.serialize(compress=False))

    def test_no_container_magic(self) -> None:
        raw = _xorb_with([b"hello"]).serialize()
        assert raw[0] == 0  # chunk header version
        assert len(raw) == 8 + 5

    def test_deserialize_truncated(self) -> None:
        raw = _xorb_with([b"hello world"]).serialize()
        with pytest.raises(ValueError):
            Xorb.deserialize(raw[:-2])
        with pytest.raises(ValueError):
            Xorb.deserialize(b"\x00\x01")

    def test_get_chunk_by_hash(self) -> None:
        x = _xorb_with([b"one", b"two"])
        h = XetHasher.compute_chunk_hash(b"two")
        assert x.get_chunk_by_hash(h) == b"two"
        assert x.get_chunk_by_hash(bytes(32)) is None

    def test_clear(self) -> None:
        x = _xorb_with([b"one"])
        x.clear()
        assert x.get_chunk_count() == 0

    def test_chunk_limit(self) -> None:
        x = Xorb()
        for i in range(MAX_XORB_CHUNKS):
            assert x.add_chunk(XetHasher.compute_chunk_hash(bytes([i % 256])), b"x")
        assert not x.add_chunk(XetHasher.compute_chunk_hash(b"y"), b"x")
        assert x.is_full()

    def test_bg4_roundtrip(self) -> None:
        for n in (0, 1, 2, 3, 4, 5, 100, 101):
            data = bytes(range(n % 256 for _ in range(n))) if False else bytes(i % 256 for i in range(n))
            assert byte_ungrouping_4(byte_grouping_4(data), n) == data

    def test_read_chunk_range(self) -> None:
        chunks = [b"c0", b"c1x", b"c2yy"]
        raw = _xorb_with(chunks).serialize()
        assert Xorb.read_chunk(raw, 2) == b"c2yy"
        assert Xorb.read_chunk_range(raw, 0, 2) == b"c0c1x"
        with pytest.raises(ValueError):
            Xorb.read_chunk(raw, 5)
