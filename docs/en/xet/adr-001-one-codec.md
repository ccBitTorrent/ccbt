# ADR-001: One Xet codec, legacy stores are import-only

## Context

The pre-v2 implementation used a private chunker (16 KiB target, 32-bit
masked rolling hash), plain BLAKE3/SHA-256 hashes, a private xorb
container, and a private `SHAR` shard. Those bytes are incompatible with
upstream Xet and with any other implementation, so deduplication only
worked inside one installation. Maintaining two codecs (private native
plus upstream-compatible) would keep two hash namespaces forever.

## Decision

- Native BEP XET v2 adopts the upstream codec suite
  (`xet-blake3-gearhash-lz4:v2`): 64 KiB Gearhash CDC, BLAKE3 keyed
  hashing, upstream xorb serialization, upstream MDB shard.
- Legacy chunk stores, xorbs, shards, and `.tonic` files created before
  v2 are labelled `legacy-v1`. They are never written again and never
  mixed with v2 chunks for the same file.
- `ccbt xet migrate-legacy` performs a one-time import: it reads a
  legacy workspace/store, re-chunks file contents with the v2 chunker,
  stores v2 chunks, and writes `.tonic` files with `format_version=2`
  and `suite=xet-blake3-gearhash-lz4:v2`. On any failure it reports the
  failing path and leaves the legacy data untouched.
- `.tonic` v2 requires `format_version` and `suite`; parsers accept v1
  files only to feed the migration path.

## Consequences

- Existing workspaces need one migration run; chunk hashes change, so
  peers must re-announce. This is accepted because legacy hashes could
  never interoperate anyway.
- There is exactly one chunk identity across native sync, the local
  store, the CAS client, and the CAS server, which makes cross-torrent
  and cross-implementation deduplication testable.
