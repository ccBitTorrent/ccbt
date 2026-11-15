"""Unit tests for the MDB shard format (upstream, version 2)."""

from __future__ import annotations

import pytest

from ccbt.storage.xet_hashing import XetHasher
from ccbt.storage.xet_shard import (
    FileInfo,
    FileTerm,
    XorbChunkEntry,
    XetShard,
    XorbInfo,
    parse_shard,
    serialize_shard_for_upload,
)


def _shard() -> tuple[XetShard, FileInfo, list[tuple[bytes, int]]]:
    pairs = [(XetHasher.compute_chunk_hash(bytes([i]) * (100 + i)), 100 + i) for i in range(3)]
    xorb_hash = XetHasher.compute_xorb_hash(pairs)
    info = FileInfo(
        file_hash=XetHasher.compute_file_hash(pairs),
        terms=[FileTerm(xorb_hash, 0, sum(s for _h, s in pairs), 0, 3)],
        verification=[XetHasher.compute_range_hash([h for h, _s in pairs])],
    )
    shard = XetShard()
    shard.add_file_info(info)
    shard.add_xorb_info(
        XorbInfo(
            xorb_hash=xorb_hash,
            chunks=[XorbChunkEntry(h, 0, s) for h, s in pairs],
            num_bytes_on_disk=999,
        )
    )
    return shard, info, pairs


class TestXetShard:
    def test_roundtrip_with_footer(self) -> None:
        shard, info, pairs = _shard()
        data = shard.serialize(hmac_key=b"k" * 32, creation_timestamp=42)
        parsed = parse_shard(data)
        assert parsed.footer is not None
        assert parsed.footer.hmac_key == b"k" * 32
        assert parsed.footer.creation_timestamp == 42
        got = parsed.get_file_reconstruction(info.file_hash)
        assert got is not None and got.terms == info.terms
        assert parsed.contains_chunk(pairs[1][0])
        assert parsed.chunk_location(pairs[1][0]) == (info.terms[0].xorb_hash, 1)

    def test_upload_form_has_raw_hashes_and_no_footer(self) -> None:
        shard, _info, pairs = _shard()
        parsed = parse_shard(serialize_shard_for_upload(shard))
        assert parsed.footer is None
        assert parsed.xorbs[0].chunks[0].chunk_hash == pairs[0][0]

    def test_invalid_inputs(self) -> None:
        with pytest.raises(ValueError):
            parse_shard(b"")
        with pytest.raises(ValueError):
            parse_shard(b"X" * 100)
        shard, _i, _p = _shard()
        data = bytearray(shard.serialize(hmac_key=b"k" * 32))
        data[32:40] = (99).to_bytes(8, "little")
        with pytest.raises(ValueError):
            parse_shard(bytes(data))

    def test_truncated_shard_rejected(self) -> None:
        shard, _i, _p = _shard()
        data = shard.serialize(hmac_key=b"k" * 32)
        with pytest.raises(ValueError):
            parse_shard(data[:60])

    def test_multiple_files_sorted(self) -> None:
        shard, info, _pairs = _shard()
        other = FileInfo(file_hash=XetHasher.compute_file_hash([(bytes(32), 1)]), terms=[])
        shard.add_file_info(other)
        parsed = parse_shard(shard.serialize(hmac_key=b"k" * 32))
        assert len(parsed.files) == 2
        assert parsed.get_file_reconstruction(other.file_hash) is not None

    def test_sha256_metadata_ext(self) -> None:
        shard, info, _pairs = _shard()
        info.sha256 = bytes(range(32))
        parsed = parse_shard(shard.serialize(hmac_key=b"k" * 32))
        got = parsed.get_file_reconstruction(info.file_hash)
        assert got is not None and got.sha256 == bytes(range(32))

    def test_unknown_file(self) -> None:
        shard, _i, _p = _shard()
        parsed = parse_shard(shard.serialize(hmac_key=b"k" * 32))
        assert parsed.get_file_reconstruction(bytes(32)) is None
        assert not parsed.contains_chunk(bytes(32))
