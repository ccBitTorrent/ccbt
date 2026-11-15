"""Two-node loopback TCP chunk exchange over length-prefixed XET payloads (G6)."""

from __future__ import annotations

import asyncio
import contextlib
import struct

import pytest

from ccbt.extensions.xet import XetExtension
from ccbt.session.xet_transport import XetTransport
from ccbt.storage.xet_hashing import XetHasher

pytestmark = [pytest.mark.timeout(30), pytest.mark.integration]

_HS = {"xet": {"supports_chunk_requests": True, "suite": XetHasher.SUITE}}


async def _read_frame(reader: asyncio.StreamReader) -> bytes:
    hdr = await reader.readexactly(4)
    (n,) = struct.unpack("!I", hdr)
    if n > 256 * 1024:
        msg = f"frame too large: {n}"
        raise ValueError(msg)
    return await reader.readexactly(n)


async def _write_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    writer.write(struct.pack("!I", len(payload)) + payload)
    await writer.drain()


@pytest.mark.asyncio
async def test_e2e_tcp_chunk_exchange_loopback() -> None:
    """Server owns chunk; client fetches over real TCP localhost sockets."""
    payload = b"tcp-e2e-" + bytes(range(128))
    chunk_hash = XetHasher.compute_chunk_hash(payload)

    server_ext = XetExtension()
    server_ext.set_chunk_provider(lambda h: payload if h == chunk_hash else None)
    server_transport = XetTransport(extension=server_ext)
    server_transport.register_peer("client", _HS)

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                msg = await _read_frame(reader)
                reply = await server_transport.handle_message("client", msg)
                if reply:
                    await _write_frame(writer, reply)
        except (asyncio.IncompleteReadError, ConnectionResetError, ConnectionError):
            pass
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    srv = await asyncio.start_server(handle, host="127.0.0.1", port=0)
    sockets = srv.sockets or []
    assert sockets
    port = sockets[0].getsockname()[1]

    client_transport = XetTransport(extension=XetExtension())
    reader, writer = await asyncio.open_connection("127.0.0.1", port)

    async def send(_peer_id: str, msg: bytes) -> bool:
        await _write_frame(writer, msg)
        reply = await asyncio.wait_for(_read_frame(reader), timeout=5.0)
        await client_transport.handle_message("server", reply)
        return True

    client_transport.set_sender(send)
    client_transport.register_peer("server", _HS)

    try:
        got = await client_transport.request_chunk("server", chunk_hash, timeout=5.0)
        assert got == payload
        assert client_transport.metrics.responses_ok >= 1
        missing = XetHasher.compute_chunk_hash(b"nope")
        miss = await client_transport.request_chunk("server", missing, timeout=5.0)
        assert miss is None
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
        srv.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(srv.wait_closed(), timeout=2.0)
