"""Golden-vector tests for the upstream Xet codec (suite v2).

Reference values are taken from huggingface/xet-core
(xet_core_structures/src/merklehash/aggregated_hashes.rs,
test_correctness) pinned in dev/xet-conformance.lock.json.
"""

from __future__ import annotations

import random

import pytest
from pydantic import ValidationError

from ccbt.models import DiskConfig
from ccbt.storage.xet_chunking import (
    MASK,
    MAX_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
    TARGET_CHUNK_SIZE,
    GearhashChunker,
)
from ccbt.storage.xet_hashing import XetHasher, hash_to_hex, hex_to_hash
from ccbt.storage.xet_reconstruction import reconstruct_verified
from ccbt.storage.xet_shard import (
    FileInfo,
    FileTerm,
    XorbChunkEntry,
    XetShard,
    XorbInfo,
    parse_shard,
    serialize_shard_for_upload,
)
from ccbt.storage.xet_xorb import Xorb

REF_PAIRS = [
    ("cfc5d07f6f03c29bbf424132963fe08d19a37d5757aaf520bf08119f05cd56d6", 100),
    ("c3e67584b5c4fc2a89837ec39e40f2c8a6bb0b2987ac94cd4b31e5fbdd210a72", 200),
    ("0d2beb91b9196929a5ddec9f6e306924ddf4a24268e3e59fd8464738d525af37", 300),
]
REF_XORB_HASH = "71ec1275fca074724e2dd666921b3277c7cee603e4d025bcab2d4050015be2bc"
REF_FILE_HASH = "54e55dccc6653c612bdb5576c5d3cb34bb31bc4e100248abccf4c908b3ef7715"


def _seeded_blob(size: int = 300_000, seed: int = 42) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.randrange(256) for _ in range(size))


def test_xet_golden_chunking() -> None:
    assert TARGET_CHUNK_SIZE == 65536
    assert MIN_CHUNK_SIZE == 8192
    assert MAX_CHUNK_SIZE == 131072
    assert MASK == 0xFFFF000000000000
    blob = _seeded_blob()
    chunks = GearhashChunker().chunk_buffer(blob)
    assert [len(c) for c in chunks] == [47654, 15669, 85430, 74533, 76714]
    assert b"".join(chunks) == blob
    for c in chunks[:-1]:
        assert MIN_CHUNK_SIZE <= len(c) <= MAX_CHUNK_SIZE
    # Deterministic: same input, same boundaries
    assert GearhashChunker().chunk_buffer(blob) == chunks
    # All-same-byte input: forced cuts at maximum only
    zchunks = GearhashChunker().chunk_buffer(b"a" * 300_000)
    assert [len(c) for c in zchunks] == [131072, 131072, 37856]
    assert GearhashChunker().chunk_buffer(b"") == []
    assert GearhashChunker().chunk_buffer(b"hello xet") == [b"hello xet"]


def test_xet_golden_streaming_equivalence() -> None:
    blob = _seeded_blob(200_000, seed=7)
    expected = GearhashChunker().chunk_buffer(blob)
    chunker = GearhashChunker()
    out: list[bytes] = []
    for i in range(0, len(blob), 997):
        out += chunker.feed(blob[i : i + 997])
    out += chunker.finalize()
    assert out == expected
    # chunk_stream and chunk_file equivalence
    assert list(GearhashChunker().chunk_stream([blob[:5000], blob[5000:]])) == expected


def test_xet_golden_hashing() -> None:
    # Merkle hex is block-reversed little-endian u64 rendering
    h = bytes(range(32))
    assert hash_to_hex(h) == "".join(
        f"{int.from_bytes(h[i:i+8], 'little'):016x}" for i in (0, 8, 16, 24)
    )
    assert hex_to_hash(hash_to_hex(h)) == h
    # Keyed chunk hash is not plain BLAKE3
    import blake3 as _b3

    data = b"golden chunk data"
    assert XetHasher.compute_chunk_hash(data) != _b3.blake3(data).digest()
    assert len(XetHasher.compute_chunk_hash(data)) == 32
    # No silent algorithm fallback in suite v2
    with pytest.raises(ValueError):
        XetHasher.compute_chunk_hash(data, algorithm="sha256")


def test_xet_golden_merkle() -> None:
    pairs = [(hex_to_hash(h), s) for h, s in REF_PAIRS]
    assert hash_to_hex(XetHasher.compute_xorb_hash(pairs)) == REF_XORB_HASH
    assert hash_to_hex(XetHasher.compute_file_hash(pairs)) == REF_FILE_HASH
    assert hash_to_hex(XetHasher.aggregated_hash(pairs)) == REF_XORB_HASH
    # Empty inputs
    assert XetHasher.compute_xorb_hash([]) == bytes(32)
    assert XetHasher.compute_file_hash([]) == bytes(32)
    # Single pair xorb hash == the hash itself (upstream reference)
    one = [(hex_to_hash(REF_PAIRS[0][0]), 100)]
    assert hash_to_hex(XetHasher.compute_xorb_hash(one)) == REF_PAIRS[0][0]


def _make_xorb_and_shard(blob: bytes):
    chunks = GearhashChunker().chunk_buffer(blob)
    pairs = [(XetHasher.compute_chunk_hash(c), len(c)) for c in chunks]
    xorb = Xorb()
    for (h, _s), c in zip(pairs, chunks):
        assert xorb.add_chunk(h, c)
    raw = xorb.serialize(compress=True)
    info = FileInfo(
        file_hash=XetHasher.compute_file_hash(pairs),
        terms=[
            FileTerm(
                xorb_hash=xorb.get_xorb_hash(),
                cas_flags=0,
                unpacked_length=len(blob),
                chunk_index_start=0,
                chunk_index_end=len(chunks),
            )
        ],
        verification=[XetHasher.compute_range_hash([h for h, _ in pairs])],
    )
    shard = XetShard()
    shard.add_file_info(info)
    shard.add_xorb_info(
        XorbInfo(
            xorb_hash=xorb.get_xorb_hash(),
            chunks=[
                XorbChunkEntry(chunk_hash=h, byte_range_start=0, unpacked_size=s)
                for h, s in pairs
            ],
            num_bytes_on_disk=len(raw),
        )
    )
    return chunks, pairs, xorb, raw, info, shard


def test_xet_golden_xorb_roundtrip() -> None:
    blob = _seeded_blob(120_000, seed=3)
    chunks, pairs, xorb, raw, _info, _shard = _make_xorb_and_shard(blob)
    assert raw[:1] == b"\x00"  # first chunk header version byte; no container magic
    back = Xorb.deserialize(raw)
    assert [d for _h, d in back.chunks] == chunks
    assert back.get_xorb_hash() == xorb.get_xorb_hash()
    # Uncompressed roundtrip too
    back2 = Xorb.deserialize(xorb.serialize(compress=False))
    assert [d for _h, d in back2.chunks] == chunks
    # Range reads
    assert Xorb.read_chunk(raw, 1) == chunks[1]
    assert Xorb.read_chunk_range(raw, 0, 2) == chunks[0] + chunks[1]
    with pytest.raises(ValueError):
        Xorb.deserialize(b"\x01" + raw[1:])


def test_xet_golden_shard_roundtrip() -> None:
    blob = _seeded_blob(120_000, seed=5)
    _chunks, pairs, _xorb, raw, info, shard = _make_xorb_and_shard(blob)
    data = shard.serialize(hmac_key=bytes(range(32)), creation_timestamp=123)
    assert data[:14] == b"HFRepoMetaData"
    parsed = parse_shard(data)
    assert parsed.footer is not None
    assert parsed.footer.creation_timestamp == 123
    finfo = parsed.get_file_reconstruction(info.file_hash)
    assert finfo is not None
    assert finfo.terms[0].chunk_index_end == len(pairs)
    assert finfo.verification == info.verification
    # Chunk hashes are HMAC-keyed on disk but queries take raw hashes
    assert parsed.xorbs[0].chunks[0].chunk_hash != pairs[0][0]
    assert parsed.contains_chunk(pairs[2][0])
    assert parsed.chunk_location(pairs[2][0]) == (info.terms[0].xorb_hash, 2)
    assert not parsed.contains_chunk(bytes(32))
    # Upload form: no footer, raw chunk hashes
    upload = serialize_shard_for_upload(shard)
    parsed_up = parse_shard(upload)
    assert parsed_up.footer is None
    assert parsed_up.xorbs[0].chunks[0].chunk_hash == pairs[0][0]
    # Verified reconstruction from the parsed shard
    assert reconstruct_verified(finfo, lambda _h: raw) == blob
    # Corruption is detected
    bad = bytearray(raw)
    bad[-1] ^= 0xFF
    with pytest.raises(Exception):
        reconstruct_verified(finfo, lambda _h: bytes(bad))


def test_xet_golden_config_target() -> None:
    with pytest.raises(ValueError):
        GearhashChunker(target_size=1000)  # not a power of two


def test_xet_config_target_enforced() -> None:
    assert DiskConfig().xet_chunk_target_size == 65536
    with pytest.raises(ValidationError):
        DiskConfig(xet_chunk_target_size=16384)
