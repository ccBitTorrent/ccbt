"""MDB Shard format (upstream Xet, file format version 2).

Layout: 48-byte header (32-byte metadata tag, version u64 = 2,
footer_size u64), file-info section, CAS-info section, optional lookup
tables, 200-byte footer. Entries are fixed 48-byte units. Chunk hashes
stored on read shards are HMAC-keyed with the footer key; lookup tables
map truncated hashes (first little-endian u64) to entry indices.
Upload shards omit the footer and the lookup tables.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Optional

from ccbt.storage.xet_hashing import XetHasher, truncate_hash

SHARD_FILE_VERSION = 2
SHARD_HEADER_TAG = b"HFRepoMetaData" + bytes(
    [0, 85, 105, 103, 69, 106, 123, 129, 87, 131, 165, 189, 217, 92, 205, 209, 74, 169]
)
HEADER_SIZE = 48
FOOTER_SIZE = 200
FOOTER_VERSION = 1
BOOKEND = b"\xff" * 32 + b"\x00" * 16
ENTRY_SIZE = 48

FILE_FLAG_WITH_VERIFICATION = 1 << 31
FILE_FLAG_WITH_METADATA_EXT = 1 << 30
CHUNK_FLAG_GLOBAL_DEDUP = 1 << 31

_MAX_ENTRIES_SANITY = 10_000_000


def hash_sort_key(h: bytes) -> tuple[int, int, int, int]:
    """Upstream MerkleHash Ord: compare as four little-endian u64s."""
    return tuple(int.from_bytes(h[i : i + 8], "little") for i in (0, 8, 16, 24))  # type: ignore[return-value]


@dataclass
class FileTerm:
    """Public class."""

    xorb_hash: bytes
    cas_flags: int
    unpacked_length: int
    chunk_index_start: int
    chunk_index_end: int


@dataclass
class FileInfo:
    """Public class."""

    file_hash: bytes
    terms: list[FileTerm] = field(default_factory=list)
    flags: int = 0
    verification: list[bytes] = field(default_factory=list)  # range hash per term
    sha256: Optional[bytes] = None

    @property
    def total_length(self) -> int:
        """Public method."""
        return sum(t.unpacked_length for t in self.terms)


@dataclass
class XorbChunkEntry:
    """Public class."""

    chunk_hash: bytes  # as stored (HMAC-keyed on read shards)
    byte_range_start: int
    unpacked_size: int
    flags: int = 0


@dataclass
class XorbInfo:
    """Public class."""

    xorb_hash: bytes
    flags: int = 0
    chunks: list[XorbChunkEntry] = field(default_factory=list)
    num_bytes_in_cas: int = 0
    num_bytes_on_disk: int = 0


@dataclass
class ShardFooter:
    """Public class."""

    file_info_offset: int
    cas_info_offset: int
    file_lookup_offset: int
    file_lookup_num_entries: int
    xorb_lookup_offset: int
    xorb_lookup_num_entries: int
    chunk_lookup_offset: int
    chunk_lookup_num_entries: int
    hmac_key: bytes
    creation_timestamp: int
    expiry_timestamp: int
    stored_bytes_on_disk: int
    materialized_bytes: int
    stored_bytes: int
    footer_offset: int


class XetShard:
    """One parsed/buildable MDB shard."""

    def __init__(self) -> None:
        """Initialize instance."""
        self.files: list[FileInfo] = []
        self.xorbs: list[XorbInfo] = []
        self.footer: Optional[ShardFooter] = None
        self._chunk_lookup: dict[int, tuple[int, int]] = {}
        self._file_lookup: dict[int, int] = {}
        self._xorb_lookup: dict[int, int] = {}

    def add_file_info(self, info: FileInfo) -> None:
        """Public method."""
        self.files.append(info)

    def add_xorb_info(self, info: XorbInfo) -> None:
        """Public method."""
        self.xorbs.append(info)

    # ---------------------------------------------------------- serialize
    def serialize(
        self,
        *,
        include_footer: bool = True,
        hmac_key: Optional[bytes] = None,
        creation_timestamp: int = 0,
        expiry_timestamp: int = 0xFFFF_FFFF_FFFF_FFFF,
    ) -> bytes:
        """Public method."""
        if include_footer and hmac_key is None:
            hmac_key = secrets.token_bytes(32)
        key = hmac_key or bytes(32)

        out = bytearray()
        out += SHARD_HEADER_TAG
        out += SHARD_FILE_VERSION.to_bytes(8, "little")
        out += (FOOTER_SIZE if include_footer else 0).to_bytes(8, "little")

        file_info_offset = len(out)
        file_lookup: list[tuple[int, int]] = []
        files_sorted = sorted(self.files, key=lambda f: hash_sort_key(f.file_hash))
        entry_index = 0
        for info in files_sorted:
            if info.verification and len(info.verification) != len(info.terms):
                msg = "verification entries must match term count"
                raise ValueError(msg)
            has_meta = info.sha256 is not None
            flags = 0
            if info.verification:
                flags |= FILE_FLAG_WITH_VERIFICATION
            if has_meta:
                flags |= FILE_FLAG_WITH_METADATA_EXT
            following = (
                len(info.terms)
                + (len(info.verification) if info.verification else 0)
                + (1 if has_meta else 0)
            )
            file_lookup.append((truncate_hash(info.file_hash), entry_index))
            out += info.file_hash
            out += flags.to_bytes(4, "little")
            out += len(info.terms).to_bytes(
                4, "little"
            )  # upstream: num_entries == term count
            out += b"\x00" * 8
            for term in info.terms:
                if not (0 <= term.unpacked_length < 2**32):
                    msg = "term unpacked_length does not fit u32"
                    raise ValueError(msg)
                out += term.xorb_hash
                out += term.cas_flags.to_bytes(4, "little")
                out += term.unpacked_length.to_bytes(4, "little")
                out += term.chunk_index_start.to_bytes(4, "little")
                out += term.chunk_index_end.to_bytes(4, "little")
            for range_hash in info.verification:
                out += range_hash
                out += b"\x00" * 16
            if has_meta:
                if info.sha256 is None:
                    msg = "sha256 metadata flagged but missing"
                    raise ValueError(msg)
                out += info.sha256
                out += b"\x00" * 16
            entry_index += 1 + following
        out += BOOKEND

        cas_info_offset = len(out)
        xorb_lookup: list[tuple[int, int]] = []
        chunk_lookup: list[tuple[bytes, int, int]] = []
        xorbs_sorted = sorted(self.xorbs, key=lambda x: hash_sort_key(x.xorb_hash))
        block_index = 0
        total_in_cas = 0
        total_on_disk = 0
        for xorb in xorbs_sorted:
            num_bytes_in_cas = sum(c.unpacked_size for c in xorb.chunks)
            total_in_cas += num_bytes_in_cas
            total_on_disk += xorb.num_bytes_on_disk
            xorb_lookup.append((truncate_hash(xorb.xorb_hash), block_index))
            out += xorb.xorb_hash
            out += xorb.flags.to_bytes(4, "little")
            out += len(xorb.chunks).to_bytes(4, "little")
            out += num_bytes_in_cas.to_bytes(4, "little")
            out += xorb.num_bytes_on_disk.to_bytes(4, "little")
            offset = 0
            for ci, chunk in enumerate(xorb.chunks):
                stored = (
                    XetHasher.hmac_hash(chunk.chunk_hash, key)
                    if include_footer
                    else chunk.chunk_hash
                )
                out += stored
                out += offset.to_bytes(4, "little")
                out += chunk.unpacked_size.to_bytes(4, "little")
                out += chunk.flags.to_bytes(4, "little")
                out += b"\x00" * 4
                chunk_lookup.append((stored, block_index, ci))
                offset += chunk.unpacked_size
            block_index += 1 + len(xorb.chunks)
        out += BOOKEND

        materialized = sum(f.total_length for f in self.files)
        if not include_footer:
            return bytes(out)

        file_lookup_offset = len(out)
        for trunc, idx in sorted(file_lookup):
            out += trunc.to_bytes(8, "little")
            out += idx.to_bytes(4, "little")
        xorb_lookup_offset = len(out)
        for trunc, idx in sorted(xorb_lookup):
            out += trunc.to_bytes(8, "little")
            out += idx.to_bytes(4, "little")
        chunk_lookup_offset = len(out)
        for stored, bidx, cidx in sorted(
            chunk_lookup, key=lambda e: truncate_hash(e[0])
        ):
            out += truncate_hash(stored).to_bytes(8, "little")
            out += bidx.to_bytes(4, "little")
            out += cidx.to_bytes(4, "little")

        footer_offset = len(out)
        out += FOOTER_VERSION.to_bytes(8, "little")
        out += file_info_offset.to_bytes(8, "little")
        out += cas_info_offset.to_bytes(8, "little")
        out += file_lookup_offset.to_bytes(8, "little")
        out += len(file_lookup).to_bytes(8, "little")
        out += xorb_lookup_offset.to_bytes(8, "little")
        out += len(xorb_lookup).to_bytes(8, "little")
        out += chunk_lookup_offset.to_bytes(8, "little")
        out += len(chunk_lookup).to_bytes(8, "little")
        out += key
        out += creation_timestamp.to_bytes(8, "little")
        out += expiry_timestamp.to_bytes(8, "little")
        out += b"\x00" * 48  # _buffer: [u64; 6]
        out += total_on_disk.to_bytes(8, "little")
        out += materialized.to_bytes(8, "little")
        out += total_in_cas.to_bytes(8, "little")
        out += footer_offset.to_bytes(8, "little")
        if len(out) - footer_offset != FOOTER_SIZE:
            msg = "MDB shard footer size mismatch"
            raise RuntimeError(msg)
        return bytes(out)

    # ------------------------------------------------------------ queries
    def get_file_reconstruction(self, file_hash: bytes) -> Optional[FileInfo]:
        """Public method."""
        for info in self.files:
            if info.file_hash == file_hash:
                return info
        return None

    def _sorted_xorbs(self) -> list[XorbInfo]:
        return sorted(self.xorbs, key=lambda x: hash_sort_key(x.xorb_hash))

    def _xorb_entry_at_block(self, block_index: int) -> Optional[XorbInfo]:
        idx = 0
        for xorb in self._sorted_xorbs():
            if idx == block_index:
                return xorb
            idx += 1 + len(xorb.chunks)
        return None

    def _keyed(self, chunk_hash: bytes) -> bytes:
        if self.footer is not None:
            return XetHasher.hmac_hash(chunk_hash, self.footer.hmac_key)
        return chunk_hash

    def contains_chunk(self, chunk_hash: bytes) -> bool:
        """Public method."""
        return self.chunk_location(chunk_hash) is not None

    def chunk_dedup_query(self, chunk_hash: bytes) -> bool:
        """Upstream shard dedup query: raw hash in, answer out."""
        return self.contains_chunk(chunk_hash)

    def chunk_location(self, chunk_hash: bytes) -> Optional[tuple[bytes, int]]:
        """Return (xorb_hash, chunk index) for a RAW chunk hash."""
        keyed = self._keyed(chunk_hash)
        if self._chunk_lookup:
            loc = self._chunk_lookup.get(truncate_hash(keyed))
            if loc is not None:
                block_idx, chunk_idx = loc
                xorb = self._xorb_entry_at_block(block_idx)
                if (
                    xorb is not None
                    and chunk_idx < len(xorb.chunks)
                    and xorb.chunks[chunk_idx].chunk_hash == keyed
                ):
                    return (xorb.xorb_hash, chunk_idx)
                return None
        for xorb in self.xorbs:
            for i, entry in enumerate(xorb.chunks):
                if entry.chunk_hash in (chunk_hash, keyed):
                    return (xorb.xorb_hash, i)
        return None


def serialize_shard(shard: XetShard, **kwargs: object) -> bytes:
    """Public function."""
    return shard.serialize(**kwargs)  # type: ignore[arg-type]


def serialize_shard_for_upload(shard: XetShard) -> bytes:
    """Footerless shard for POST /shards (raw chunk hashes)."""
    return shard.serialize(include_footer=False, hmac_key=None)


def build_xorb_info(
    xorb_hash: bytes, chunks: list[tuple[bytes, bytes]], num_bytes_on_disk: int
) -> XorbInfo:
    """Public function."""
    return XorbInfo(
        xorb_hash=xorb_hash,
        chunks=[
            XorbChunkEntry(
                chunk_hash=h,
                byte_range_start=sum(len(d) for _h2, d in chunks[:i]),
                unpacked_size=len(d),
            )
            for i, (h, d) in enumerate(chunks)
        ],
        num_bytes_in_cas=sum(len(d) for _h, d in chunks),
        num_bytes_on_disk=num_bytes_on_disk,
    )


def parse_shard(data: bytes) -> XetShard:
    """Parse an MDB shard (with or without footer). Validates bounds."""
    if len(data) < HEADER_SIZE:
        msg = "shard too short for header"
        raise ValueError(msg)
    if data[:32] != SHARD_HEADER_TAG:
        msg = "invalid shard header tag"
        raise ValueError(msg)
    version = int.from_bytes(data[32:40], "little")
    if version != SHARD_FILE_VERSION:
        msg = f"unsupported shard file format version: {version}"
        raise ValueError(msg)
    footer_size = int.from_bytes(data[40:48], "little")
    if footer_size not in (0, FOOTER_SIZE):
        msg = f"invalid shard footer size: {footer_size}"
        raise ValueError(msg)

    shard = XetShard()
    footer: Optional[ShardFooter] = None
    if footer_size:
        if len(data) < HEADER_SIZE + FOOTER_SIZE:
            msg = "shard too short for footer"
            raise ValueError(msg)
        f = data[len(data) - FOOTER_SIZE :]

        def u64(off: int) -> int:
            return int.from_bytes(f[off : off + 8], "little")

        if u64(0) != FOOTER_VERSION:
            msg = f"unsupported shard footer version: {u64(0)}"
            raise ValueError(msg)
        footer = ShardFooter(
            file_info_offset=u64(8),
            cas_info_offset=u64(16),
            file_lookup_offset=u64(24),
            file_lookup_num_entries=u64(32),
            xorb_lookup_offset=u64(40),
            xorb_lookup_num_entries=u64(48),
            chunk_lookup_offset=u64(56),
            chunk_lookup_num_entries=u64(64),
            hmac_key=f[72:104],
            creation_timestamp=u64(104),
            expiry_timestamp=u64(112),
            stored_bytes_on_disk=u64(168),
            materialized_bytes=u64(176),
            stored_bytes=u64(184),
            footer_offset=u64(192),
        )
        shard.footer = footer

    limit = len(data) - footer_size if footer_size else len(data)

    def require(off: int, n: int) -> None:
        if off < 0 or off + n > limit:
            msg = "shard entry out of bounds"
            raise ValueError(msg)

    offset = HEADER_SIZE
    while True:  # file-info section
        require(offset, ENTRY_SIZE)
        entry = data[offset : offset + ENTRY_SIZE]
        if entry == BOOKEND:
            offset += ENTRY_SIZE
            break
        file_hash = entry[:32]
        flags = int.from_bytes(entry[32:36], "little")
        num_terms = int.from_bytes(entry[36:40], "little")
        if num_terms > _MAX_ENTRIES_SANITY:
            msg = f"implausible shard term count: {num_terms}"
            raise ValueError(msg)
        has_verif = bool(flags & FILE_FLAG_WITH_VERIFICATION)
        has_meta = bool(flags & FILE_FLAG_WITH_METADATA_EXT)
        following = num_terms + (num_terms if has_verif else 0) + (1 if has_meta else 0)
        require(offset, (1 + following) * ENTRY_SIZE)
        info = FileInfo(file_hash=file_hash, flags=flags)
        pos = offset + ENTRY_SIZE
        for _ in range(num_terms):
            e = data[pos : pos + ENTRY_SIZE]
            info.terms.append(
                FileTerm(
                    xorb_hash=e[:32],
                    cas_flags=int.from_bytes(e[32:36], "little"),
                    unpacked_length=int.from_bytes(e[36:40], "little"),
                    chunk_index_start=int.from_bytes(e[40:44], "little"),
                    chunk_index_end=int.from_bytes(e[44:48], "little"),
                )
            )
            pos += ENTRY_SIZE
        if has_verif:
            for _ in range(num_terms):
                info.verification.append(data[pos : pos + 32])
                pos += ENTRY_SIZE
        if has_meta:
            info.sha256 = data[pos : pos + 32]
            pos += ENTRY_SIZE
        shard.files.append(info)
        offset += (1 + following) * ENTRY_SIZE

    while True:  # CAS-info section
        require(offset, ENTRY_SIZE)
        entry = data[offset : offset + ENTRY_SIZE]
        if entry == BOOKEND:
            offset += ENTRY_SIZE
            break
        xorb_hash = entry[:32]
        flags = int.from_bytes(entry[32:36], "little")
        num_chunks = int.from_bytes(entry[36:40], "little")
        if num_chunks > _MAX_ENTRIES_SANITY:
            msg = f"implausible shard xorb chunk count: {num_chunks}"
            raise ValueError(msg)
        require(offset, (1 + num_chunks) * ENTRY_SIZE)
        xinfo = XorbInfo(
            xorb_hash=xorb_hash,
            flags=flags,
            num_bytes_in_cas=int.from_bytes(entry[40:44], "little"),
            num_bytes_on_disk=int.from_bytes(entry[44:48], "little"),
        )
        pos = offset + ENTRY_SIZE
        for _ in range(num_chunks):
            e = data[pos : pos + ENTRY_SIZE]
            xinfo.chunks.append(
                XorbChunkEntry(
                    chunk_hash=e[:32],
                    byte_range_start=int.from_bytes(e[32:36], "little"),
                    unpacked_size=int.from_bytes(e[36:40], "little"),
                    flags=int.from_bytes(e[40:44], "little"),
                )
            )
            pos += ENTRY_SIZE
        shard.xorbs.append(xinfo)
        offset += (1 + num_chunks) * ENTRY_SIZE

    if footer is not None:
        file_lookup = shard._file_lookup  # noqa: SLF001
        xorb_lookup = shard._xorb_lookup  # noqa: SLF001
        chunk_lookup = shard._chunk_lookup  # noqa: SLF001
        for base, count, size, target in (
            (
                footer.file_lookup_offset,
                footer.file_lookup_num_entries,
                12,
                file_lookup,
            ),
            (
                footer.xorb_lookup_offset,
                footer.xorb_lookup_num_entries,
                12,
                xorb_lookup,
            ),
        ):
            for i in range(count):
                require(base + i * size, size)
                e = data[base + i * size : base + i * size + size]
                target[int.from_bytes(e[:8], "little")] = int.from_bytes(
                    e[8:12], "little"
                )  # type: ignore[arg-type]
        clo, n = footer.chunk_lookup_offset, footer.chunk_lookup_num_entries
        for i in range(n):
            require(clo + i * 16, 16)
            e = data[clo + i * 16 : clo + i * 16 + 16]
            chunk_lookup[int.from_bytes(e[:8], "little")] = (
                int.from_bytes(e[8:12], "little"),
                int.from_bytes(e[12:16], "little"),
            )
    return shard
