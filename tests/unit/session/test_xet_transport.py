"""Unit tests for XetTransport (G6)."""

from __future__ import annotations

import asyncio

import pytest

from ccbt.extensions.xet import XetExtension, XetMessageType
from ccbt.session.xet_transport import XetTransport
from ccbt.storage.xet_hashing import XetHasher

_HS = {
    "xet": {
        "supports_chunk_requests": True,
        "suite": XetHasher.SUITE,
    }
}


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_xet_extension_v2_wire() -> None:
    """Request/response carry request_id and verify hash."""
    ext = XetExtension()
    data = b"hello-xet-chunk" + b"\x00" * 64
    chunk_hash = XetHasher.compute_chunk_hash(data)
    store = {chunk_hash: data}
    ext.set_chunk_provider(lambda h: store.get(h))

    transport = XetTransport(extension=ext, send=None)
    assert transport.register_peer("p1", _HS)

    req_id, req = ext.encode_chunk_request_tracked("p1", chunk_hash)
    assert req[0] == XetMessageType.CHUNK_REQUEST
    resp = await transport.handle_message("p1", req)
    assert resp is not None
    assert resp[0] == XetMessageType.CHUNK_RESPONSE
    rid, rh, body = ext.decode_chunk_response(resp)
    assert rid == req_id
    assert rh == chunk_hash
    assert body == data


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_xet_transport_request_chunk_roundtrip() -> None:
    """Two-sided in-process transport: request_chunk awaits correlated response."""
    data = b"payload-" + b"x" * 100
    chunk_hash = XetHasher.compute_chunk_hash(data)
    provider_ext = XetExtension()
    provider_ext.set_chunk_provider(lambda h: data if h == chunk_hash else None)
    server = XetTransport(extension=provider_ext)
    server.register_peer("client", _HS)

    client_ext = XetExtension()
    client = XetTransport(extension=client_ext)

    async def client_send(_peer_id: str, msg: bytes) -> bool:
        reply = await server.handle_message("client", msg)
        if reply:
            await client.handle_message("server", reply)
        return True

    client.set_sender(client_send)
    client.register_peer("server", _HS)
    got = await client.request_chunk("server", chunk_hash, timeout=2.0)
    assert got == data
    assert client.metrics.responses_ok >= 1


@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_xet_transport_rejects_unauthorized() -> None:
    transport = XetTransport(auth_check=lambda _pid, _ws: False)
    assert not transport.register_peer("bad", _HS)
