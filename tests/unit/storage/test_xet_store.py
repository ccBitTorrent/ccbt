"""WS2 gate tests: transactional verified chunk store."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from ccbt.storage.xet_deduplication import XetDeduplication
from ccbt.storage.xet_hashing import XetHasher


def _make_store(tmp_path: Path) -> XetDeduplication:
    return XetDeduplication(tmp_path / "cache" / "chunks.db")


def _physical_chunks(store: XetDeduplication) -> list[Path]:
    return [
        p
        for p in store.chunk_store_path.iterdir()
        if p.is_file() and p.name != "quarantine"
    ]


async def test_xet_store_cross_torrent_dedup(tmp_path: Path) -> None:
    """Same file content indexed under two torrents stores chunks once."""
    store = _make_store(tmp_path)
    try:
        content = bytes(range(256)) * 3000  # ~768 KiB, several chunks
        file_a = tmp_path / "torrent_a" / "movie.bin"
        file_b = tmp_path / "torrent_b" / "movie.bin"
        for f in (file_a, file_b):
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(content)

        meta_a = await store.index_file_streaming(file_a, file_key="torrent-a/movie.bin")
        physical_after_a = _physical_chunks(store)
        assert physical_after_a

        meta_b = await store.index_file_streaming(file_b, file_key="torrent-b/movie.bin")
        # No new physical chunks for identical content
        assert _physical_chunks(store) == physical_after_a
        assert meta_a.file_hash == meta_b.file_hash
        assert meta_a.chunk_hashes == meta_b.chunk_hashes

        # Both logical files reconstruct byte-identically
        for key, expected in (
            ("torrent-a/movie.bin", tmp_path / "out_a.bin"),
            ("torrent-b/movie.bin", tmp_path / "out_b.bin"),
        ):
            out = await store.reconstruct_file_from_chunks(key, expected)
            assert out.read_bytes() == content

        stats = store.get_cache_stats()
        assert stats["total_chunks"] == len(physical_after_a)
    finally:
        store.close()


async def test_xet_store_verify_on_read(tmp_path: Path) -> None:
    """Corrupt chunk bytes are quarantined and never returned."""
    store = _make_store(tmp_path)
    try:
        data = b"verify me on read" * 100
        h = XetHasher.compute_chunk_hash(data)
        await store.store_chunk(h, data)
        assert await store.get_chunk_data(h) == data

        # Corrupt the physical bytes behind the catalog's back
        path = store.chunk_store_path / h.hex()
        path.write_bytes(b"tampered bytes!")
        assert await store.get_chunk_data(h) is None

        # Quarantined and de-catalogued
        assert (store.chunk_store_path / "quarantine" / h.hex()).exists()
        assert await store.check_chunk_exists(h) is None
        assert store.get_chunk_info(h) is None
    finally:
        store.close()


async def test_xet_store_verify_on_write(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        with pytest.raises(ValueError):
            await store.store_chunk(bytes(32), b"data that hashes elsewhere")
        assert _physical_chunks(store) == []
    finally:
        store.close()


async def test_xet_store_reconstruct_rejects_missing(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    try:
        src = tmp_path / "f.bin"
        src.write_bytes(b"x" * 100_000)
        await store.index_file_streaming(src, file_key="f.bin")
        # Remove a chunk physically and its catalog row stays -> read fails
        chunks = await store.get_file_chunks("f.bin")
        victim = store.chunk_store_path / chunks[0][0].hex()
        victim.write_bytes(b"corrupted")
        with pytest.raises((FileNotFoundError, ValueError)):
            await store.reconstruct_file_from_chunks("f.bin", tmp_path / "o.bin")
        assert not (tmp_path / "o.bin").exists()
    finally:
        store.close()


def test_xet_no_placeholder_modules() -> None:
    for mod in (
        "ccbt.storage.xet_data_aggregator",
        "ccbt.storage.xet_defrag_prevention",
        "ccbt.storage.xet_file_deduplication",
    ):
        assert importlib.util.find_spec(mod) is None, mod
