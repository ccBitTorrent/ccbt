# ccBT BEP XET Native Specification v2

Status: normative for implementation. Until the big-bang release gate (G9 in
`dev/xet-claim-registry.yaml`) passes, every feature described here is
experimental and no documentation may claim it is supported.

## 1. Suite identity

- Suite string: `xet-blake3-gearhash-lz4:v2`
- Chunking: Gearhash CDC, target 65536 bytes, minimum 8192, maximum 131072,
  mask `0xFFFF000000000000`, 64-bit wrapping state `h = (h << 1) + TABLE[b]`,
  state reset to 0 at every boundary, forced boundary at maximum size.
  The 256-entry TABLE is the upstream rust-gearhash table (IETF
  draft-denis-xet Appendix B). Any other target size is a configuration
  error when XET is enabled; it is never a silent alternate namespace.
- Hashing: BLAKE3 only. Chunk hash = BLAKE3 keyed hash with `DATA_KEY`.
  Internal Merkle node = BLAKE3 keyed hash with `INTERNAL_NODE_KEY` over
  lines `"{chunk_hash_hex} : {size}\n"`. File hash = Merkle root rehashed
  with a 32-byte zero key. Term verification = BLAKE3 keyed hash with
  `VERIFICATION_KEY` over concatenated raw chunk hashes in the term.
  Shard chunk-hash protection = the same keyed BLAKE3 operation used as an
  HMAC with the shard footer key. Keys are defined in
  `ccbt/storage/xet_hashing.py` and pinned by golden tests.
- Hash identity on the wire: `xet-hash:v2:blake3`. A peer advertising any
  other suite is rejected for XET purposes (hard mismatch, no fallback).
- Legacy stores and `.tonic` files without a suite are `legacy-v1`:
  read-only import via `ccbt xet migrate-legacy`, never mixed with v2
  chunks for the same file.

## 2. Formats

- Xorb: upstream serialization. A bare sequence of chunks; each chunk is an
  8-byte header (version u8 = 0, compressed size u24 LE, compression u8 in
  {0=None, 1=LZ4-frame, 2=ByteGrouping4+LZ4}, uncompressed size u24 LE)
  followed by payload. Maximum 8192 chunks; writers cut at about 64 MiB
  uncompressed. No container header, no stored hashes, no footer.
  Xorb identity is the Merkle root over its ordered (chunk_hash, size) list.
- Shard: upstream MDB shard. 48-byte header (32-byte `HFRepoMetaData` tag,
  version u64 = 2, footer_size u64), file-info section, CAS-info section,
  lookup tables, 200-byte footer (version 1). File-info entries carry
  reconstruction terms and per-term verification entries; a SHA-256
  metadata extension is present for Hub/LFS files. Footer is omitted in
  shard-upload serialization. Chunk hashes in a response shard may be
  keyed with the footer HMAC key.
- Reconstruction: a file is an ordered list of terms
  `(xorb_hash, unpacked_length, chunk_index_start, chunk_index_end)`,
  end-exclusive. Concatenating decoded term chunks in order yields the
  file bytes (or the requested byte range).

## 3. BEP 10 extension (native transport)

- Extension name `xet`, negotiated through the BEP 10 `m` dictionary with
  peer-local IDs. Handshake payload advertises suite, workspace bindings,
  allowlist hash, Ed25519 public key, nonce, and proof-of-possession
  signature over the canonical handshake payload.
- Message types (first payload byte):
  - `0x01` CHUNK_REQUEST: request_id u32 BE, chunk_hash 32 bytes.
  - `0x02` CHUNK_RESPONSE: request_id u32 BE, chunk_hash 32, length u32 BE, data.
  - `0x03` CHUNK_NOT_FOUND: request_id u32 BE, chunk_hash 32.
  - `0x04` CHUNK_ERROR: request_id u32 BE, chunk_hash 32, code u32 BE, message UTF-8.
  - `0x10` FOLDER_VERSION_REQUEST, `0x11` FOLDER_VERSION_RESPONSE.
  - `0x12` FOLDER_UPDATE_NOTIFY (versioned; workspace id, op, path, file hash, git ref, metadata version).
  - `0x13` FOLDER_SYNC_MODE_REQUEST, `0x14` FOLDER_SYNC_MODE_RESPONSE.
  - `0x20` FOLDER_METADATA_REQUEST, `0x21` FOLDER_METADATA_RESPONSE (16 KiB pieces), `0x22` FOLDER_METADATA_NOT_FOUND.
  - `0x30` BLOOM_FILTER_REQUEST, `0x31` BLOOM_FILTER_RESPONSE.
  - `0x40` GOSSIP_SYNC (JSON batch, seen-set deduplicated).
  - `0x50` RAFT_VOTE_REQUEST, `0x51` RAFT_VOTE_RESPONSE,
    `0x52` RAFT_APPEND_ENTRIES, `0x53` RAFT_APPEND_ENTRIES_RESPONSE.
  - `0x60` CONSENSUS_PROPOSE, `0x61` CONSENSUS_VOTE (Byzantine mode, signed).
- Limits: chunk payload at most 131072 bytes; extension message at most
  256 KiB; per-peer in-flight requests bounded by configuration; requests
  time out and late or duplicate responses are ignored by request_id.
- Every received chunk is hash-verified before storage or delivery.

## 4. Discovery

Mechanisms, each independently enableable and each requiring a two-node
proof test to be listed as available:

1. Connected-peer exchange (existing BitTorrent connections).
2. DHT BEP 44 mutable items: announcer Ed25519 key, salt = chunk hash or
   workspace id, target = SHA-1(pubkey || salt), signed sequence number,
   value (under 1000 bytes, bencoded) containing peer locator and expiry;
   hourly republish; stale or bad-signature items rejected.
3. Trackers: chunk announced as info_hash = chunk_hash[0:20]; workspace
   (32-byte) IDs announced over HTTP/HTTPS trackers only (BEP 15 announce
   is fixed at 20 bytes and BEP 41 does not change that).
4. PEX chunk messages CHUNKS_ADDED / CHUNKS_DROPPED carrying chunk hashes.
5. Local catalog (persistent chunk-to-xorb and chunk-to-peer index).
6. Bloom filters as a pre-filter only; a bloom miss never proves absence
   for fetch decisions.
7. Local Peer Discovery (BEP 14 style multicast).
8. XET multicast announcements.
9. Gossip with fanout, interval, seen-set deduplication.
10. Controlled flooding with TTL and priority threshold.

Query batching and concurrency come from
`discovery.xet_chunk_query_batch_size` and
`discovery.xet_chunk_query_max_concurrent`; no hard-coded slice limits.

## 5. Folder synchronization semantics

- File identity is the v2 file hash of its chunk manifest.
- Deletes are tombstones carrying a version vector; renames are
  delete + add; per-file versions are monotonic.
- Simultaneous divergent edits create a conflict: the strategy winner is
  written to the path, the loser is preserved under `.xet/conflicts/`.
  Three-way merge requires a stored common base; without a base it
  degrades to a preserved conflict copy, never silent last-write-wins.
- Modes: `designated` (elected source with term and failover; non-source
  updates rejected), `best_effort` (all nodes contribute),
  `broadcast` (at-least-once gossip/flood delivery, idempotent apply),
  `consensus` (Raft-committed updates; Byzantine voting only with real
  Ed25519 verification and `n >= 3f + 1`, quorum `2f + 1`).
- Authorization scopes: `strict_workspace_auth` (allowlist required for
  metadata and chunk serving) and `content_addressable_open` (chunks may
  be served by hash, metadata still authenticated). Scopes are enforced
  on every serve and fetch path.

## 6. CAS / Hub compatibility

The HF/OpenXet-facing stack (CAS client, CAS server, Hub API, Git LFS,
git-xet) follows the published HF Xet specification and CAS API contract,
with versions pinned in `dev/xet-conformance.lock.json`. Where the spec
and stock clients differ, observed client behavior (as documented by the
OpenXet wire-contract research) wins and the deviation is recorded in the
claim registry.

## 7. Error handling

Parsers must bound all counts and sizes before allocation, reject bad
magic/versions, and never serve unverified bytes. Network handlers return
typed errors; chunk fetch retries with backoff across peers; consensus
modes fail closed when quorum requirements cannot be met.
