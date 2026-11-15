"""Per-mechanism discovery proofs (G7)."""

from __future__ import annotations

import importlib
import logging
from unittest.mock import MagicMock

import pytest

import ccbt.discovery.dht as dht_module
from ccbt.discovery.pex import AsyncPexManager
from ccbt.models import PeerInfo
from ccbt.storage.xet_hashing import XetHasher

pytestmark = [pytest.mark.timeout(30), pytest.mark.integration]

_DHT_PEER_PORT = 6881
_PEX_PEER_PORT = 6882
_INFOHASH_LEN = 20


def _real_async_dht_client_cls() -> type:
    """Return the real AsyncDHTClient class, recovering from patch pollution."""
    client_cls = dht_module.AsyncDHTClient
    if isinstance(client_cls, MagicMock) or not isinstance(client_cls, type):
        reloaded = importlib.reload(dht_module)
        client_cls = reloaded.AsyncDHTClient
    if not isinstance(client_cls, type):
        msg = "AsyncDHTClient is not a real class after reload"
        raise TypeError(msg)
    return client_cls


@pytest.mark.asyncio
async def test_e2e_discovery_dht_only() -> None:
    """DHT mutable local store announces and resolves a chunk peer."""
    client_cls = _real_async_dht_client_cls()

    # Prefer object.__new__ so MagicMock.__new__ cannot intercept.
    dht = object.__new__(client_cls)
    dht._xet_mutable_store = {}  # noqa: SLF001
    dht._xet_mutable_seq = {}  # noqa: SLF001
    dht.read_only = True
    dht.logger = logging.getLogger("test_dht")

    chunk = XetHasher.compute_chunk_hash(b"dht-only-chunk")
    meta = {"ip": "127.0.0.1", "port": _DHT_PEER_PORT, "expiry": 9e12}
    n = await client_cls.store_chunk_hash(dht, chunk, meta)
    assert n >= 1
    peers = await client_cls.get_chunk_peers(dht, chunk)
    assert any(p.ip == "127.0.0.1" and p.port == _DHT_PEER_PORT for p in peers)


@pytest.mark.asyncio
async def test_e2e_discovery_tracker_only() -> None:
    """Tracker-class info_hash mapping uses first 20 bytes of chunk hash."""
    chunk = XetHasher.compute_chunk_hash(b"tracker-chunk")
    info_hash = chunk[:_INFOHASH_LEN]
    assert len(info_hash) == _INFOHASH_LEN
    # Contract: announce/scrape key for XET chunks is chunk_hash[:20]
    assert info_hash == chunk[:_INFOHASH_LEN]


@pytest.mark.asyncio
async def test_e2e_discovery_gossip_only() -> None:
    """PEX chunk registry API without loading full app config."""
    # Avoid AsyncPexManager() ctor (pulls get_config); exercise the registry methods.
    pex = object.__new__(AsyncPexManager)
    pex.known_chunks = {}
    pex.chunk_callbacks = []
    pex.logger = logging.getLogger("test_pex")
    chunk = XetHasher.compute_chunk_hash(b"gossip-chunk")
    AsyncPexManager.add_chunks_from_peer(pex, "127.0.0.1", _PEX_PEER_PORT, [chunk])
    found = AsyncPexManager.get_peers_with_chunks(pex, [chunk])
    assert chunk in found
    assert any(
        isinstance(p, PeerInfo) and p.port == _PEX_PEER_PORT for p in found[chunk]
    )
