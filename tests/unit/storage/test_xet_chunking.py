"""Unit tests for GearhashChunker (upstream Xet CDC)."""

from __future__ import annotations

import pytest

from ccbt.storage.xet_chunking import GearhashChunker


class TestGearhashChunker:
    def test_chunker_initialization(self) -> None:
        c = GearhashChunker()
        assert c.target_size == 65536
        assert c.minimum_chunk == 8192
        assert c.maximum_chunk == 131072
        assert len(c.gear_table) == 256

    def test_chunker_target_size_validation(self) -> None:
        with pytest.raises(ValueError):
            GearhashChunker(target_size=1000)
        with pytest.raises(ValueError):
            GearhashChunker(target_size=32)

    def test_chunk_empty_buffer(self) -> None:
        assert GearhashChunker().chunk_buffer(b"") == []

    def test_chunk_small_buffer(self) -> None:
        data = b"small"
        assert GearhashChunker().chunk_buffer(data) == [data]

    def test_chunk_size_boundaries(self) -> None:
        data = bytes(range(256)) * 2000
        chunks = GearhashChunker().chunk_buffer(data)
        for chunk in chunks[:-1]:
            assert 8192 <= len(chunk) <= 131072

    def test_chunk_consistency(self) -> None:
        data = b"deterministic content" * 5000
        assert GearhashChunker().chunk_buffer(data) == GearhashChunker().chunk_buffer(data)

    def test_chunk_reassembles_correctly(self) -> None:
        data = bytes(range(256)) * 1000
        assert b"".join(GearhashChunker().chunk_buffer(data)) == data

    def test_streaming_matches_buffer(self) -> None:
        data = bytes(range(256)) * 1000
        c = GearhashChunker()
        out: list[bytes] = []
        for i in range(0, len(data), 3333):
            out += c.feed(data[i : i + 3333])
        out += c.finalize()
        assert out == GearhashChunker().chunk_buffer(data)

    def test_edit_locality(self) -> None:
        """A small edit only disturbs nearby chunk boundaries."""
        base = bytes(range(256)) * 2000
        edited = base[:200_000] + b"X" + base[200_001:]
        a = [len(c) for c in GearhashChunker().chunk_buffer(base)]
        b = [len(c) for c in GearhashChunker().chunk_buffer(edited)]
        # Most chunk sizes before the edit point are identical
        prefix = 0
        for x, y in zip(a, b):
            if x != y:
                break
            prefix += 1
        assert prefix >= 1
