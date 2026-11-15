"""Native two-node XET chunk exchange harness (G6/G9)."""

from __future__ import annotations

import pytest

from ccbt.extensions.xet import XetExtension
from ccbt.session.xet_transport import XetTransport
from ccbt.storage.xet_hashing import XetHasher

pytestmark = [pytest.mark.timeout(30), pytest.mark.integration]

_HS = {"xet": {"supports_chunk_requests": True, "suite": XetHasher.SUITE}}


@pytest.mark.asyncio
async def test_e2e_chunk_exchange() -> None:
    """Loopback-style in-process two peers: hit, miss, and hash verify."""
    payload = b"e2e-chunk-" + bytes(range(256))
    chunk_hash = XetHasher.compute_chunk_hash(payload)
    missing = XetHasher.compute_chunk_hash(b"missing-payload")

    a_ext = XetExtension()
    a_ext.set_chunk_provider(lambda h: payload if h == chunk_hash else None)
    a = XetTransport(extension=a_ext)
    a.register_peer("b", _HS)

    b_ext = XetExtension()
    b = XetTransport(extension=b_ext)

    async def send_to_a(_pid: str, msg: bytes) -> bool:
        reply = await a.handle_message("b", msg)
        if reply:
            await b.handle_message("a", reply)
        return True

    b.set_sender(send_to_a)
    b.register_peer("a", _HS)

    hit = await b.request_chunk("a", chunk_hash, timeout=3.0)
    assert hit == payload

    miss = await b.request_chunk("a", missing, timeout=3.0)
    assert miss is None
    assert b.metrics.not_found >= 1 or b.metrics.responses_ok >= 1
