"""Unit tests for inbound TCP server helper utilities."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.peer.inbound_protocol_classifier import InboundProtocolKind
from ccbt.peer.peer import Handshake, ParsedInboundPlainHandshake
from ccbt.peer.tcp_server import (
    IncomingPeerServer,
    _MSEInboundSessionResolver,
    _ReplayableStreamReader,
)
from ccbt.protocols.bittorrent_v2 import PROTOCOL_STRING_LEN

pytestmark = [pytest.mark.unit, pytest.mark.peer]


def _build_stream_reader(payload: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(payload)
    reader.feed_eof()
    return reader


def _build_bittorrent_handshake(info_hash: bytes, peer_id: bytes) -> bytes:
    return b"\x13BitTorrent protocol" + b"\x00" * 8 + info_hash + peer_id


@pytest.mark.asyncio
async def test_replayable_stream_reader_readexactly_prefers_buffer() -> None:
    source = _build_stream_reader(b"payload-from-source")
    replayable = _ReplayableStreamReader(source)
    replayable.unread(b"prefix")

    assert await replayable.readexactly(3) == b"pre"
    assert await replayable.readexactly(2) == b"fi"
    assert await replayable.readexactly(3) == b"xpa"
    assert await replayable.readexactly(3) == b"ylo"
    assert await replayable.readexactly(6) == b"ad-fro"


@pytest.mark.asyncio
async def test_replayable_stream_reader_unread_replays_bytes() -> None:
    source = _build_stream_reader(b"abcdef")
    replayable = _ReplayableStreamReader(source)

    first_chunk = await replayable.readexactly(4)
    assert first_chunk == b"abcd"

    replayable.unread(first_chunk)

    assert await replayable.readexactly(6) == b"abcdef"
    assert replayable.at_eof()


@pytest.mark.asyncio
async def test_replayable_stream_reader_read_uses_buffer_then_source() -> None:
    source = _build_stream_reader(b"wxyz")
    replayable = _ReplayableStreamReader(source)
    replayable.unread(b"123")

    assert await replayable.read(2) == b"12"
    assert await replayable.read(5) == b"3wxyz"


def test_mse_inbound_session_resolver_returns_single_session() -> None:
    """Resolver returns session and info hash only when exactly one torrent is active."""
    info_hash = b"\x01" * 20
    session = SimpleNamespace(info=SimpleNamespace(info_hash=info_hash))
    session_manager = SimpleNamespace(torrents={info_hash: session})

    resolved = _MSEInboundSessionResolver.resolve_single_session(session_manager)

    assert resolved is not None
    resolved_session, resolved_info_hash = resolved
    assert resolved_session is session
    assert resolved_info_hash == info_hash


def test_mse_inbound_session_resolver_rejects_multiple_sessions() -> None:
    """Resolver declines ambiguous routing when multiple torrents are active."""
    session = SimpleNamespace(info=SimpleNamespace(info_hash=b"\x01" * 20))
    other_session = SimpleNamespace(info=SimpleNamespace(info_hash=b"\x02" * 20))
    session_manager = SimpleNamespace(
        torrents={b"\x01" * 20: session, b"\x02" * 20: other_session}
    )

    assert _MSEInboundSessionResolver.resolve_single_session(session_manager) is None


def _sample_parsed_handshake(info_hash: bytes) -> ParsedInboundPlainHandshake:
    return ParsedInboundPlainHandshake(
        protocol_len=PROTOCOL_STRING_LEN,
        protocol=Handshake.PROTOCOL_STRING,
        reserved_bytes=b"\x00" * 8,
        info_hash_v1=info_hash,
        info_hash_v2=None,
        peer_id=b"-CC0101-testpeer---",
    )


def test_inbound_unknown_info_hash_metrics_increment() -> None:
    """Unknown inbound hash counter uses 16-char hex prefix keys."""
    sm = SimpleNamespace(torrents={}, lock=asyncio.Lock())
    srv = IncomingPeerServer(sm, config=MagicMock())
    ph = _sample_parsed_handshake(b"\xcd" * 20)
    assert srv.get_inbound_unknown_info_hash_metrics() == {}
    srv._record_inbound_unknown_info_hash(ph)
    assert srv.get_inbound_unknown_info_hash_metrics() == {"cd" * 8: 1}
    srv._record_inbound_unknown_info_hash(ph)
    assert srv.get_inbound_unknown_info_hash_metrics() == {"cd" * 8: 2}


def test_unknown_inbound_hash_warning_sampling() -> None:
    """WARNING path samples every N occurrences per hash prefix (storm control)."""
    sm = SimpleNamespace(torrents={}, lock=asyncio.Lock())
    srv = IncomingPeerServer(sm, config=MagicMock())
    key = "a" * 16
    srv._unknown_inbound_hash_warning_every_n = 4
    for n in range(1, 10):
        srv._inbound_unknown_hash_counts[key] = n
        emit = srv._should_emit_unknown_inbound_hash_warning(key)
        assert emit == (n == 1 or n % 4 == 0), n


def test_inbound_unknown_hash_warning_interval_reads_network_config() -> None:
    """Sample interval comes from network.inbound_unknown_hash_warning_sample_interval."""
    sm = SimpleNamespace(torrents={}, lock=asyncio.Lock())
    cfg = SimpleNamespace(
        network=SimpleNamespace(inbound_unknown_hash_warning_sample_interval=9),
    )
    srv = IncomingPeerServer(sm, config=cfg)
    assert srv._unknown_inbound_hash_warning_every_n == 9


def test_probation_inflight_per_hash_cap() -> None:
    """At most _max_probation_inflight_per_hash concurrent probation slots per hash."""
    sm = SimpleNamespace(torrents={}, lock=asyncio.Lock())
    srv = IncomingPeerServer(sm, config=MagicMock())
    ih = b"\xee" * 20
    cap = srv._max_probation_inflight_per_hash
    for _ in range(cap):
        assert srv._reserve_probation_slot_for_hash(ih) is True
    assert srv._reserve_probation_slot_for_hash(ih) is False
    srv._release_probation_slot_for_hash(ih)
    assert srv._reserve_probation_slot_for_hash(ih) is True


def test_mse_inbound_session_resolver_resolves_by_info_hash() -> None:
    """Resolver returns the requested session when a target info hash is provided."""
    info_hash_a = b"\x01" * 20
    info_hash_b = b"\x02" * 20
    session_a = SimpleNamespace(info=SimpleNamespace(info_hash=info_hash_a))
    session_b = SimpleNamespace(info=SimpleNamespace(info_hash=info_hash_b))
    session_manager = SimpleNamespace(
        torrents={info_hash_a: session_a, info_hash_b: session_b}
    )

    resolved = _MSEInboundSessionResolver.resolve_single_session(
        session_manager, info_hash=info_hash_b
    )

    assert resolved is not None
    resolved_session, resolved_info_hash = resolved
    assert resolved_session is session_b
    assert resolved_info_hash == info_hash_b


@pytest.mark.asyncio
async def test_inbound_mse_connection_routes_to_accept_incoming_encrypted() -> None:
    """MSE inbound handler hands decrypted payload to peer-manager encrypted acceptance."""
    info_hash = b"\x11" * 20
    accept_incoming_encrypted = AsyncMock()
    respond_from_peer = SimpleNamespace(
        success=True,
        decrypted_initial_data=_build_bittorrent_handshake(
            info_hash,
            b"\x22" * 20,
        ),
    )
    mse = SimpleNamespace(
        respond_as_receiver_with_initial_data=AsyncMock(return_value=respond_from_peer)
    )
    peer_manager = SimpleNamespace(
        _create_mse_handshake=MagicMock(return_value=mse),
        accept_incoming_encrypted=accept_incoming_encrypted,
    )
    session = SimpleNamespace(
        info=SimpleNamespace(info_hash=info_hash),
        download_manager=SimpleNamespace(peer_manager=peer_manager),
    )
    session_manager = SimpleNamespace(torrents={info_hash: session})
    config = SimpleNamespace(
        network=SimpleNamespace(handshake_timeout=0.25),
    )

    server = IncomingPeerServer(session_manager, config=config)
    server._running = True
    server._allow_inbound_admission = lambda *args, **kwargs: True
    reader = _ReplayableStreamReader(_build_stream_reader(b"payload"))
    writer = MagicMock()
    writer.wait_closed = AsyncMock()

    await server._handle_inbound_mse_connection(
        reader,
        writer,
        "127.0.0.1",
        6881,
    )

    accept_incoming_encrypted.assert_awaited_once_with(
        reader,
        writer,
        respond_from_peer.decrypted_initial_data,
        "127.0.0.1",
        6881,
    )


@pytest.mark.asyncio
async def test_inbound_mse_connection_routes_to_resolved_session_for_multi_hash() -> (
    None
):
    """MSE inbound routing uses resolved hash to select the correct torrent session."""
    info_hash_one = b"\x11" * 20
    info_hash_two = b"\x22" * 20

    accept_from_one = AsyncMock()
    accept_from_two = AsyncMock()
    respond_from_peer = SimpleNamespace(
        success=True,
        decrypted_initial_data=_build_bittorrent_handshake(
            info_hash_two,
            b"\x33" * 20,
        ),
        resolved_info_hash=info_hash_two,
    )
    peer_manager_one = SimpleNamespace(
        _create_mse_handshake=MagicMock(
            return_value=SimpleNamespace(
                respond_as_receiver_with_initial_data=AsyncMock(
                    return_value=respond_from_peer
                )
            )
        ),
        accept_incoming_encrypted=accept_from_one,
    )
    peer_manager_two = SimpleNamespace(
        accept_incoming_encrypted=accept_from_two,
    )
    session_one = SimpleNamespace(
        info=SimpleNamespace(info_hash=info_hash_one),
        download_manager=SimpleNamespace(peer_manager=peer_manager_one),
    )
    session_two = SimpleNamespace(
        info=SimpleNamespace(info_hash=info_hash_two),
        download_manager=SimpleNamespace(peer_manager=peer_manager_two),
    )
    session_manager = SimpleNamespace(
        torrents={info_hash_one: session_one, info_hash_two: session_two}
    )
    config = SimpleNamespace(
        network=SimpleNamespace(handshake_timeout=0.25),
    )

    server = IncomingPeerServer(session_manager, config=config)
    server._running = True
    server._allow_inbound_admission = lambda *args, **kwargs: True
    reader = _ReplayableStreamReader(_build_stream_reader(b"payload"))
    writer = MagicMock()
    writer.wait_closed = AsyncMock()

    await server._handle_inbound_mse_connection(
        reader,
        writer,
        "127.0.0.1",
        6881,
    )

    accept_from_one.assert_not_awaited()
    accept_from_two.assert_awaited_once_with(
        reader,
        writer,
        respond_from_peer.decrypted_initial_data,
        "127.0.0.1",
        6881,
    )


@pytest.mark.asyncio
async def test_inbound_mse_connection_closes_when_session_ambiguous() -> None:
    """MSE inbound handler closes when session selection is ambiguous."""
    session_a = SimpleNamespace(info=SimpleNamespace(info_hash=b"\x11" * 20))
    session_b = SimpleNamespace(info=SimpleNamespace(info_hash=b"\x22" * 20))
    session_manager = SimpleNamespace(
        torrents={b"\x11" * 20: session_a, b"\x22" * 20: session_b}
    )
    server = IncomingPeerServer(
        session_manager,
        config=SimpleNamespace(network=SimpleNamespace(handshake_timeout=0.25)),
    )
    reader = _ReplayableStreamReader(_build_stream_reader(b"payload"))
    writer = MagicMock()
    writer.wait_closed = AsyncMock()

    await server._handle_inbound_mse_connection(
        reader,
        writer,
        "127.0.0.1",
        6881,
    )

    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_connection_rejects_plain_inbound_on_admission_denial() -> None:
    """Plaintext inbound admission denial prevents direct accept and closes the socket."""
    info_hash = b"\x44" * 20
    peer_id = b"\x55" * 20
    handshake = _build_bittorrent_handshake(info_hash, peer_id)

    accept_incoming = AsyncMock()
    session = SimpleNamespace(
        info=SimpleNamespace(info_hash=info_hash),
        download_manager=SimpleNamespace(
            peer_manager=SimpleNamespace(accept_incoming=accept_incoming)
        ),
    )
    session_manager = SimpleNamespace(
        get_session_for_info_hash=AsyncMock(return_value=session)
    )
    server = IncomingPeerServer(
        session_manager,
        config=SimpleNamespace(network=SimpleNamespace(handshake_timeout=0.2)),
    )
    reader = _build_stream_reader(handshake)
    writer = MagicMock()
    writer.get_extra_info = MagicMock(return_value=("127.0.0.1", 6881))
    writer.wait_closed = AsyncMock()

    server._allow_inbound_admission = lambda *args, **kwargs: False

    await server._handle_connection(reader, writer)

    accept_incoming.assert_not_awaited()
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
async def test_await_session_for_inbound_peer_rejects_on_admission_denial() -> None:
    """Probation replay must re-run admission and honor a denial decision."""
    info_hash = b"\x66" * 20
    peer_id = b"\x77" * 20
    parsed_handshake = SimpleNamespace(
        info_hash_v1=info_hash,
        peer_id=peer_id,
        reserved_bytes=b"\x00" * 8,
    )

    accept_incoming = AsyncMock()
    session = SimpleNamespace(
        info=SimpleNamespace(info_hash=info_hash),
        accept_incoming_peer=accept_incoming,
    )
    session_manager = SimpleNamespace(
        get_session_for_info_hash=AsyncMock(return_value=session)
    )
    server = IncomingPeerServer(
        session_manager,
        config=SimpleNamespace(network=SimpleNamespace(handshake_timeout=0.2)),
    )
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    reader = _build_stream_reader(b"")

    server._allow_inbound_admission = lambda *args, **kwargs: False

    await server._await_session_for_inbound_peer(
        reader,
        writer,
        parsed_handshake,
        "127.0.0.1",
        6881,
        0.0,
        InboundProtocolKind.BITTORRENT_PLAINTEXT,
    )

    accept_incoming.assert_not_awaited()
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()


def test_should_abort_inbound_when_session_manager_shutting_down() -> None:
    """Manager.stop() sets is_shutting_down before TCP stop; inbound waits must abort."""
    from ccbt.utils.shutdown import clear_shutdown

    clear_shutdown()
    sm = MagicMock()
    sm.is_shutting_down = MagicMock(return_value=True)
    sm.lock = asyncio.Lock()
    srv = IncomingPeerServer(sm, config=MagicMock())
    srv._running = True
    assert srv._should_abort_inbound_registration_wait() is True


def test_should_abort_inbound_when_global_shutdown() -> None:
    from ccbt.utils.shutdown import clear_shutdown, set_shutdown

    set_shutdown()
    try:
        sm = MagicMock()
        sm.is_shutting_down = MagicMock(return_value=False)
        sm.lock = asyncio.Lock()
        srv = IncomingPeerServer(sm, config=MagicMock())
        srv._running = True
        assert srv._should_abort_inbound_registration_wait() is True
    finally:
        clear_shutdown()


@pytest.mark.asyncio
async def test_await_session_for_inbound_peer_aborts_when_manager_shutting_down() -> (
    None
):
    from ccbt.utils.shutdown import clear_shutdown

    clear_shutdown()
    info_hash = b"\x66" * 20
    parsed_handshake = SimpleNamespace(
        info_hash_v1=info_hash,
        peer_id=b"\x77" * 20,
        reserved_bytes=b"\x00" * 8,
    )
    sm = MagicMock()
    sm.is_shutting_down = MagicMock(return_value=True)
    sm.get_session_for_info_hash = AsyncMock(return_value=None)
    sm.lock = asyncio.Lock()
    server = IncomingPeerServer(
        sm,
        config=SimpleNamespace(network=SimpleNamespace(handshake_timeout=60.0)),
    )
    server._running = True
    writer = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    reader = _build_stream_reader(b"")

    t0 = asyncio.get_event_loop().time()
    await server._await_session_for_inbound_peer(
        reader,
        writer,
        parsed_handshake,
        "127.0.0.1",
        6881,
        t0,
        InboundProtocolKind.BITTORRENT_PLAINTEXT,
    )
    assert asyncio.get_event_loop().time() - t0 < 1.0
    sm.get_session_for_info_hash.assert_not_awaited()
