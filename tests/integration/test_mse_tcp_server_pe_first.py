"""Integration tests for loopback MSE/PE inbound handling."""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ccbt.peer.peer import Handshake
from ccbt.peer.tcp_server import IncomingPeerServer
from ccbt.security.mse_handshake import MSEHandshake

pytestmark = [pytest.mark.integration, pytest.mark.peer, pytest.mark.security]

_MSE_INTEGRATION_TIMEOUT = 30.0 if os.environ.get("GITHUB_ACTIONS") == "true" else 5.0
_HANDSHAKE_TIMEOUT = 10.0 if os.environ.get("GITHUB_ACTIONS") == "true" else 1.0


def _build_handshake_payload(info_hash: bytes) -> bytes:
    """Build a standard BitTorrent handshake payload for a test peer."""
    peer_id = b"-CC0001-" + b"0" * 12
    handshake = Handshake(info_hash=info_hash, peer_id=peer_id)
    return handshake.encode()


def _build_session_manager(
    sessions: dict[bytes, AsyncMock],
) -> SimpleNamespace:
    """Build a simple session manager from a map of info-hash callbacks."""
    session_entries: dict[bytes, object] = {}
    for info_hash, accept_incoming_encrypted in sessions.items():
        session_entries[info_hash] = SimpleNamespace(
            info=SimpleNamespace(info_hash=info_hash),
            download_manager=SimpleNamespace(
                peer_manager=SimpleNamespace(
                    accept_incoming_encrypted=accept_incoming_encrypted
                )
            ),
        )
    return SimpleNamespace(torrents=session_entries)


async def _run_loopback_mse_handshake(
    info_hash: bytes,
    outbound_payload: bytes,
    port: int,
) -> None:
    """Run an outbound MSE handshake against an already-started loopback server."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        mse = MSEHandshake()
        result = await mse.initiate_as_initiator(
            reader,
            writer,
            info_hash,
            timeout=_MSE_INTEGRATION_TIMEOUT,
            initial_payload=outbound_payload,
        )
        assert result.success, result.error
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
async def test_tcp_server_routes_pe_initial_payload_to_single_session() -> None:
    """Incoming PE-first handshake is routed to the single matching session."""
    info_hash = b"\x11" * 20
    outbound_payload = _build_handshake_payload(info_hash)
    accept_incoming_encrypted = AsyncMock()

    async def _close_incoming_connection(
        _reader: object, writer: object, _initial_payload: bytes, _peer_ip: str, _peer_port: int
    ) -> None:
        writer.close()
        await writer.wait_closed()

    accept_incoming_encrypted.side_effect = _close_incoming_connection

    session_manager = _build_session_manager(
        {info_hash: accept_incoming_encrypted}
    )
    config = SimpleNamespace(
        network=SimpleNamespace(handshake_timeout=_HANDSHAKE_TIMEOUT),
    )

    server = IncomingPeerServer(session_manager, config=config)
    server._running = True

    tcp_server = await asyncio.start_server(
        server._handle_connection, "127.0.0.1", 0
    )
    try:
        await asyncio.sleep(0.05)
        port = tcp_server.sockets[0].getsockname()[1]
        await _run_loopback_mse_handshake(info_hash, outbound_payload, port)

        assert accept_incoming_encrypted.await_count == 1
        accepted = accept_incoming_encrypted.await_args.args
        assert accepted[2] == outbound_payload
        assert accepted[3] == "127.0.0.1"
        assert isinstance(accepted[4], int)
    finally:
        tcp_server.close()
        await tcp_server.wait_closed()


@pytest.mark.asyncio
async def test_tcp_server_resolves_multi_hash_for_pe_first_handshake() -> None:
    """Incoming PE-first handshake resolves to the matching session via candidate hashes."""
    target_info_hash = b"\x22" * 20
    ignored_info_hash = b"\x11" * 20
    outbound_payload = _build_handshake_payload(target_info_hash)

    accept_incoming_ignored = AsyncMock()
    accept_incoming_target = AsyncMock()

    async def _close_incoming_connection(
        _reader: object, writer: object, _initial_payload: bytes, _peer_ip: str, _peer_port: int
    ) -> None:
        writer.close()
        await writer.wait_closed()

    accept_incoming_ignored.side_effect = _close_incoming_connection
    accept_incoming_target.side_effect = _close_incoming_connection
    session_manager = _build_session_manager(
        {
            ignored_info_hash: accept_incoming_ignored,
            target_info_hash: accept_incoming_target,
        }
    )
    config = SimpleNamespace(
        network=SimpleNamespace(handshake_timeout=_HANDSHAKE_TIMEOUT),
    )

    server = IncomingPeerServer(session_manager, config=config)
    server._running = True

    tcp_server = await asyncio.start_server(
        server._handle_connection, "127.0.0.1", 0
    )
    try:
        await asyncio.sleep(0.05)
        port = tcp_server.sockets[0].getsockname()[1]
        await _run_loopback_mse_handshake(target_info_hash, outbound_payload, port)

        accept_incoming_ignored.assert_not_awaited()
        accept_incoming_target.assert_awaited_once()
        accepted = accept_incoming_target.await_args.args
        assert accepted[2] == outbound_payload
        assert accepted[3] == "127.0.0.1"
        assert isinstance(accepted[4], int)
    finally:
        tcp_server.close()
        await tcp_server.wait_closed()
