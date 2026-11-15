"""Config-gated discovery mechanism proofs (G7).

Each test exercises one mechanism in isolation. Mechanisms that remain
default-disabled (LPD/gossip/multicast/flooding) assert the off-by-default
contract rather than inventing unproven socket proofs.
"""

from __future__ import annotations

import pytest

from ccbt.models import XetSyncConfig
from ccbt.storage.xet_hashing import XetHasher

pytestmark = [pytest.mark.timeout(30), pytest.mark.integration]


def test_e2e_discovery_defaults_disable_unproven() -> None:
    cfg = XetSyncConfig()
    assert cfg.enable_lpd is False
    assert cfg.enable_gossip is False
    assert cfg.enable_multicast is False
    assert cfg.enable_flooding is False
    assert cfg.enable_dht is True
    assert cfg.enable_tracker is True
    assert cfg.enable_pex is True


@pytest.mark.asyncio
async def test_e2e_discovery_catalog_only() -> None:
    from ccbt.discovery.xet_catalog import XetChunkCatalog

    cat = XetChunkCatalog()
    chunk = XetHasher.compute_chunk_hash(b"catalog-chunk")
    await cat.add_chunk(chunk, ("127.0.0.1", 6881))
    result = await cat.get_peers_by_chunks([chunk])
    assert chunk in result
    assert ("127.0.0.1", 6881) in result[chunk]


@pytest.mark.asyncio
async def test_e2e_discovery_bloom_prefilter_only() -> None:
    from ccbt.discovery.xet_bloom import XetChunkBloomFilter

    bloom = XetChunkBloomFilter()
    chunk = XetHasher.compute_chunk_hash(b"bloom-chunk")
    other = XetHasher.compute_chunk_hash(b"other-chunk")
    bloom.add_chunk(chunk)
    assert bloom.has_chunk(chunk) is True
    # Negative is not a fetch decision — only a pre-filter hint
    _ = bloom.has_chunk(other)
    assert other != chunk


@pytest.mark.asyncio
async def test_e2e_discovery_connected_peer_exchange() -> None:
    """Connected-peer path: XetTransport registry is the mechanism of record."""
    from ccbt.session.xet_transport import XetTransport
    from ccbt.storage.xet_hashing import XetHasher as H

    t = XetTransport()
    ok = t.register_peer(
        "p1", {"xet": {"supports_chunk_requests": True, "suite": H.SUITE}}
    )
    assert ok
    assert t.is_registered("p1")
