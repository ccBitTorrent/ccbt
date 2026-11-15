# BEP XET: Xet Protocol Extension for Content-Defined Chunking and Deduplication

**Status: supported.** The big-bang release gate (G9) in
`dev/xet-claim-registry.yaml` has passed and all claims are `supported`.
Normative behaviour lives in
[xet-native-spec.md](xet-native-spec.md). Codec migration is recorded in
[xet/adr-001-one-codec.md](xet/adr-001-one-codec.md).

## Overview

BEP XET adds content-defined chunking (CDC), cross-torrent deduplication, and
a peer-to-peer content-addressable store to BitTorrent via a BEP 10 extension,
with an optional Hugging Face / OpenXet-compatible CAS and Hub stack in the
same process.

## Suite identity

- Suite: `xet-blake3-gearhash-lz4:v2`
- Chunking: Gearhash CDC, target **65536**, min 8192, max 131072
- Hashing: keyed BLAKE3 only (no SHA-256 identity)
- Formats: upstream xorb + MDB shard + reconstruction terms

Legacy (`legacy-v1`) stores are import-only via `ccbt xet migrate-legacy`.

## Native wire (BEP 10)

Extension name `xet`. Chunk request/response carry a 32-bit `request_id`.
Folder sync, bloom, gossip, and Raft/Byzantine messages use the type codes in
the native spec. Byte exchange is owned by `XetTransport`;
`ccbt.protocols.xet.XetProtocol` is a discovery coordinator only.

## Discovery

Each mechanism is independently enableable. LPD, gossip, multicast, and
controlled flooding default to **off** until a two-node proof exists for that
mechanism. DHT chunk announce uses BEP 44 **mutable** items
(`sha1(pubkey + salt)` with `salt = chunk_hash`).

## Folder sync

Modes: `best_effort`, `designated`, `broadcast`, `consensus`. Conflicts never
silently overwrite: losers are preserved under `.xet/conflicts/`. Consensus
requires real Raft RPCs over the XET extension or Byzantine Ed25519 votes with
`n >= 3f+1`.

## HF / OpenXet stack

- `ccbt cas serve` — CAS HTTP server (OpenXet route contract)
- `ccbt hub serve` — Hub + Git LFS API subset
- `git-xet` — Git LFS custom transfer agent
- `CasHttpClient` — CAS HTTP client

## Claim registry

Authoritative claim status: `dev/xet-claim-registry.yaml`. CI runs
`dev/scripts/check_xet_claims.py`. Releases use `--release` and refuse to
ship while any claim is not `supported`.
The generated matrix is [xet-support-matrix.md](xet-support-matrix.md)
(`python dev/scripts/generate_xet_support_matrix.py`).


## Quick start

```bash
# Enable XET in config (target size must be 65536)
ccbt xet enable
ccbt xet status

# Optional local CAS / Hub
ccbt cas serve
ccbt hub serve

# Migrate a legacy workspace (leaves data untouched on failure)
ccbt xet migrate-legacy /path/to/workspace
```

See also: [getting-started.md](getting-started.md), [btbt-cli.md](btbt-cli.md),
[configuration.md](configuration.md).
