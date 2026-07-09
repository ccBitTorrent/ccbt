"""Unit tests for incoming peer admission guards."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.peer.inbound_protocol_classifier import InboundProtocolKind
from ccbt.session.incoming import IncomingPeerHandler

pytestmark = [pytest.mark.unit, pytest.mark.session]


def _build_session() -> object:
    return SimpleNamespace(
        logger=logging.getLogger("test-incoming-handler"),
        config=SimpleNamespace(network=SimpleNamespace(max_peers_per_torrent=100)),
    )


def _socket_writer() -> object:
    writer = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    writer.get_extra_info = MagicMock()
    return writer


def _handshake() -> object:
    return SimpleNamespace(
        info_hash_v1=b"\x11" * 20,
        peer_id=b"\x22" * 20,
        reserved_bytes=b"\x00" * 8,
    )


@pytest.mark.asyncio
async def test_accept_incoming_peer_denied_for_queued_candidate() -> None:
    queue = asyncio.Queue()
    session = _build_session()
    session.get_incoming_peer_queue = lambda: queue
    session.download_manager = None
    session.peer_manager = None
    handler = IncomingPeerHandler(session)
    handler._allow_inbound_admission = MagicMock(return_value=False)

    writer = _socket_writer()

    await handler.accept_incoming_peer(
        reader=SimpleNamespace(),
        writer=writer,
        handshake=_handshake(),
        peer_ip="127.0.0.1",
        peer_port=6881,
    )

    assert queue.empty()
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
async def test_accept_incoming_peer_denied_for_direct_candidate() -> None:
    queue = asyncio.Queue()
    session = _build_session()
    session.get_incoming_peer_queue = lambda: queue
    accept_incoming = AsyncMock()
    peer_manager = SimpleNamespace(accept_incoming=accept_incoming, connections=[])
    session.download_manager = SimpleNamespace(
        peer_manager=peer_manager,
    )
    session.peer_manager = None
    handler = IncomingPeerHandler(session)
    handler._allow_inbound_admission = MagicMock(return_value=False)

    writer = _socket_writer()

    await handler.accept_incoming_peer(
        reader=SimpleNamespace(),
        writer=writer,
        handshake=_handshake(),
        peer_ip="127.0.0.1",
        peer_port=6881,
    )

    accept_incoming.assert_not_awaited()
    assert queue.empty()
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_queue_processor_stops_on_admission_denial() -> None:
    queue = asyncio.Queue()
    session = _build_session()
    session.get_incoming_peer_queue = lambda: queue
    session.stopped = False
    session.name = "test"
    accept_incoming = AsyncMock()
    session.download_manager = None
    session.peer_manager = SimpleNamespace(accept_incoming=accept_incoming)

    session_info = SimpleNamespace(name="test", status="running")
    session.info = session_info

    writer = _socket_writer()
    handshake = _handshake()
    session.get_incoming_peer_queue().put_nowait(
        (
            SimpleNamespace(),
            writer,
            handshake,
            InboundProtocolKind.BITTORRENT_PLAINTEXT,
            "127.0.0.1",
            6881,
        )
    )

    handler = IncomingPeerHandler(session)

    def deny_and_stop(*args: object, **kwargs: object) -> bool:
        session.stopped = True
        return False

    handler._allow_inbound_admission = MagicMock(side_effect=deny_and_stop)

    await asyncio.wait_for(handler.run_queue_processor(), timeout=1)

    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()
    assert accept_incoming.await_count == 0
