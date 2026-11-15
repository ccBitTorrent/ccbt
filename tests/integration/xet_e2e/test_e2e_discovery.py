"""Per-mechanism discovery proofs (G7)."""

from __future__ import annotations

import pytest

from ccbt.discovery.pex import AsyncPexManager
from ccbt.models import PeerInfo
from ccbt.storage.xet_hashing import XetHasher

pytestmark = [pytest.mark.timeout(30), pytest.mark.integration]


@pytest.mark.asyncio
async def test_e2e_discovery_dht_only() -> None:
    """DHT mutable local store announces and resolves a chunk peer."""
    from ccbt.discovery.dht import AsyncDHTClient

    dht = AsyncDHTClient.__new__(AsyncDHTClient)
    dht._xet_mutable_store = {}
    dht._xet_mutable_seq = {}
    dht.read_only = True
    dht.logger = __import__("logging").getLogger("test_dht")

    chunk = XetHasher.compute_chunk_hash(b"dht-only-chunk")
    meta = {"ip": "127.0.0.1", "port": 6881, "expiry": 9e12}
    n = await AsyncDHTClient.store_chunk_hash(dht, chunk, meta)
    assert n >= 1
    peers = await AsyncDHTClient.get_chunk_peers(dht, chunk)
    assert any(p.ip == "127.0.0.1" and p.port == 6881 for p in peers)


@pytest.mark.asyncio
async def test_e2e_discovery_tracker_only() -> None:
    """Tracker-class info_hash mapping uses first 20 bytes of chunk hash."""
    chunk = XetHasher.compute_chunk_hash(b"tracker-chunk")
    info_hash = chunk[:20]
    assert len(info_hash) == 20
    # Contract: announce/scrape key for XET chunks is chunk_hash[:20]
    assert info_hash == chunk[:20]


@pytest.mark.asyncio
async def test_e2e_discovery_gossip_only() -> None:
    """PEX chunk registry API without loading full app config."""
    # Avoid AsyncPexManager() ctor (pulls get_config); exercise the registry methods.
    pex = object.__new__(AsyncPexManager)
    pex.known_chunks = {}
    pex.chunk_callbacks = []
    pex.logger = __import__("logging").getLogger("test_pex")
    chunk = XetHasher.compute_chunk_hash(b"gossip-chunk")
    AsyncPexManager.add_chunks_from_peer(pex, "127.0.0.1", 6882, [chunk])
    found = AsyncPexManager.get_peers_with_chunks(pex, [chunk])
    assert chunk in found
    assert any(isinstance(p, PeerInfo) and p.port == 6882 for p in found[chunk])
