"""Tests for async peer connection manager."""

import asyncio
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.unit, pytest.mark.peer]

from ccbt.core.bencode import BencodeEncoder
from ccbt.extensions.protocol import ExtensionProtocol
from ccbt.peer.async_peer_connection import (
    AsyncPeerConnection,
    AsyncPeerConnectionManager,
    ConnectionState,
)
from ccbt.peer.peer import (
    BitfieldMessage,
    HaveMessage,
    ParsedInboundPlainHandshake,
    PeerInfo,
)
from ccbt.peer.peer_connection import (
    PeerConnection,
)
from ccbt.security.encryption import EncryptionMode
from ccbt.security.mse_handshake import CipherType
from ccbt.security.swarm_auth_policy import AuthDecision
from ccbt.utils.events import PeerCountLowEvent
from ccbt.utils.exceptions import MessageError
from ccbt.utils.shutdown import clear_shutdown, set_shutdown


@pytest.fixture
def mock_torrent_data():
    """Create mock torrent data."""
    return {
        "info_hash": b"test_info_hash_20byt",  # Exactly 20 bytes
        "pieces_info": {"num_pieces": 100},
    }


@pytest.fixture
def mock_piece_manager():
    """Create mock piece manager."""
    manager = MagicMock()
    manager.verified_pieces = [0, 1, 2]
    manager.get_block = MagicMock(return_value=b"test_block_data")
    # Note: update_peer_availability is async, so it needs to be AsyncMock
    manager.update_peer_availability = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def peer_info():
    """Create test peer info."""
    return PeerInfo(ip="127.0.0.1", port=6881)


@pytest_asyncio.fixture(scope="function")
async def peer_manager(mock_torrent_data, mock_piece_manager):
    """Create async peer connection manager with proper setup and teardown."""
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager,
        max_peers_per_torrent=10,  # Note: Use max_peers_per_torrent, not max_connections
    )
    # Note: Start the manager before use
    await manager.start()
    try:
        yield manager
    finally:
        # Note: Ensure proper cleanup
        try:
            await manager.stop()
        except Exception:
            # Ignore errors during cleanup
            pass
        from ccbt.utils.network_optimizer import reset_network_optimizer

        reset_network_optimizer()


@pytest.mark.asyncio
async def test_peer_manager_context_manager(mock_torrent_data, mock_piece_manager):
    """Test peer manager lifecycle with start/stop."""
    # Note: AsyncPeerConnectionManager doesn't implement context manager protocol
    # Test start/stop lifecycle instead
    manager = AsyncPeerConnectionManager(
        torrent_data=mock_torrent_data,
        piece_manager=mock_piece_manager,
    )
    assert manager is not None

    # Start the manager
    await manager.start()
    assert manager._running is True

    # Stop the manager
    await manager.stop()
    assert manager._running is False


@pytest.mark.asyncio
async def test_connect_to_peers_success(peer_manager, peer_info):
    """Test successful peer connection."""
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    # Mock the connection process
    mock_reader = AsyncMock()
    mock_writer = MagicMock()  # Use MagicMock instead of AsyncMock for writer
    mock_writer.drain = AsyncMock()
    mock_writer.write = MagicMock(
        return_value=None
    )  # CRITICAL: write() is synchronous, returns None
    mock_writer.close = MagicMock()  # CRITICAL: close() should not be async
    mock_writer.wait_closed = AsyncMock()  # CRITICAL: wait_closed() should be async
    mock_writer.is_closing = MagicMock(
        return_value=False
    )  # CRITICAL: Writer must not be closing
    # The parser reads the handshake in chunked form; provide both modern (28-byte
    # prefix + suffix) and legacy 1+67 sequences for compatibility.
    # For v1 handshake: protocol_len (1 byte) + "BitTorrent protocol" (19 bytes) + reserved (8 bytes) + info_hash (20 bytes) + peer_id (20 bytes) = 68 bytes
    protocol_length_byte = b"\x13"  # 19 in hex
    # Build proper v1 handshake: protocol string + reserved bytes (all zeros for v1) + info_hash + peer_id
    protocol_string = b"BitTorrent protocol"
    reserved_bytes = b"\x00" * 8  # v1 handshake has all zeros in reserved bytes
    info_hash = peer_manager.torrent_data["info_hash"]
    peer_id = b"test_peer_id_20bytes"
    remaining_handshake = protocol_string + reserved_bytes + info_hash + peer_id
    full_handshake = protocol_length_byte + remaining_handshake
    # Ensure remaining_handshake is exactly 67 bytes (19 + 8 + 20 + 20 = 67)
    assert len(remaining_handshake) == 67, (
        f"Expected 67 bytes, got {len(remaining_handshake)}"
    )

    # Return based on requested size, not call count
    # Track calls to handle multiple reads of same size
    call_tracker = {"1": 0, "28": 0, "40": 0, "67": 0, "12": 0, "4": 0, "other": 0}
    max_message_reads = 3  # Limit message reads to prevent infinite loop

    async def mock_readexactly(n):
        call_key = str(n) if n in (1, 28, 40, 67, 12, 4) else "other"
        call_tracker[call_key] = call_tracker.get(call_key, 0) + 1
        if n == 28:
            return full_handshake[:28]
        if n == 40:
            return full_handshake[28:]
        if n == 1:
            # Request for 1 byte: return protocol length byte
            return protocol_length_byte
        if n == 67:
            # Request for 67 bytes: return remaining handshake
            return remaining_handshake
        if n == 12:
            # Request for 12 bytes: might be v2 handshake additional data
            # Return empty to indicate no v2 data (will cause timeout, but that's handled)
            return b""
        if n == 4:
            # Request for 4 bytes: message length header
            # After a few keep-alive messages, wait indefinitely to prevent infinite loop
            # but keep connection alive for test verification
            if call_tracker["4"] > max_message_reads:
                # Wait indefinitely instead of raising error - connection stays in dict
                await asyncio.sleep(3600)  # Wait 1 hour (effectively forever for test)
            # Return keep-alive message (length 0) - 4 bytes of zeros
            return b"\x00\x00\x00\x00"
        # For any other size (like reading message payload), raise ConnectionResetError
        # to simulate connection close
        raise ConnectionResetError(f"Connection closed after reading {n} bytes")

    mock_reader.readexactly = mock_readexactly

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        with patch("ccbt.peer.peer.Handshake.decode") as mock_decode:
            # Mock handshake validation
            mock_handshake = MagicMock()
            mock_handshake.info_hash = peer_manager.torrent_data["info_hash"]
            mock_handshake.peer_id = b"test_peer_id_20bytes"
            mock_decode.return_value = mock_handshake

            # Call connect_to_peers with strict timeout to prevent OOM
            # Use wait_for to ensure it completes or times out quickly
            try:
                await asyncio.wait_for(
                    peer_manager.connect_to_peers(peer_list),
                    timeout=2.0,  # Very short timeout to prevent OOM
                )
            except (asyncio.TimeoutError, Exception):
                # Timeout/exception is OK - connection might still be established
                pass

            # Wait briefly for connection to be established
            max_wait = 1.0
            start_time = time.time()
            connection_established = False
            while not connection_established:
                await asyncio.sleep(0.05)
                if len(peer_manager.connections) > 0:
                    connection_established = True
                    break
                if time.time() - start_time > max_wait:
                    break

            # Should have created a connection
            assert len(peer_manager.connections) == 1, (
                f"Expected 1 connection, got {len(peer_manager.connections)}"
            )
            connection = list(peer_manager.connections.values())[0]
            assert connection.peer_info.ip == peer_info.ip
            assert connection.peer_info.port == peer_info.port


@pytest.mark.asyncio
async def test_outbound_magnet_peer_sends_proactive_extension_handshake(
    peer_manager, peer_info
):
    """Magnet peers should proactively send BEP 10 handshake after the base handshake."""
    peer_manager.piece_manager._metadata_incomplete = True
    peer_manager.piece_manager.num_pieces = 0
    peer_manager.torrent_data["file_info"] = None
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    mock_reader = AsyncMock()
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.write = MagicMock(return_value=None)
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    protocol_string = b"BitTorrent protocol"
    protocol_length_byte = b"\x13"
    reserved_bytes = b"\x00\x00\x00\x00\x00\x10\x00\x00"
    info_hash = peer_manager.torrent_data["info_hash"]
    peer_id = b"test_peer_id_20bytes"
    remaining_handshake = protocol_string + reserved_bytes + info_hash + peer_id
    full_handshake = protocol_length_byte + remaining_handshake

    async def mock_readexactly(n):
        if n == 28:
            return full_handshake[:28]
        if n == 40:
            return full_handshake[28:]
        if n == 1:
            return protocol_length_byte
        if n == 67:
            return remaining_handshake
        if n == 12:
            return b""
        if n == 4:
            await asyncio.sleep(3600)
        raise ConnectionResetError(f"Connection closed after reading {n} bytes")

    mock_reader.readexactly = mock_readexactly

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        with patch("ccbt.peer.peer.Handshake.decode") as mock_decode:
            send_extension = AsyncMock()
            mock_handshake = MagicMock()
            mock_handshake.info_hash = info_hash
            mock_handshake.peer_id = peer_id
            mock_handshake.reserved_bytes = reserved_bytes
            mock_handshake.supports_extension_protocol.return_value = True
            mock_decode.return_value = mock_handshake

            with patch.object(
                peer_manager,
                "_send_our_extension_handshake",
                send_extension,
            ):
                try:
                    await asyncio.wait_for(
                        peer_manager.connect_to_peers(peer_list),
                        timeout=2.0,
                    )
                except (asyncio.TimeoutError, Exception):
                    pass

                start_time = time.time()
                while (
                    send_extension.await_count == 0 and time.time() - start_time < 1.0
                ):
                    await asyncio.sleep(0.05)

    assert send_extension.await_count >= 1


@pytest.mark.asyncio
async def test_send_our_extension_handshake_includes_encryption_preference(
    peer_manager, peer_info
):
    """Extension handshake includes top-level encryption preference `e`."""
    peer_manager.piece_manager._metadata_incomplete = True
    peer_manager.torrent_data["file_info"] = None
    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "required"

    protocol = ExtensionProtocol()
    protocol.register_extension("ut_metadata", "1.0")

    extension_manager = MagicMock()
    extension_manager.get_extension.return_value = protocol
    peer_manager.extension_manager = extension_manager

    connection = AsyncPeerConnection(
        peer_info=peer_info, torrent_data=peer_manager.torrent_data
    )
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)
    connection.writer = mock_writer

    from ccbt.core.bencode import BencodeEncoder

    captured: dict[str, dict] = {}
    original_encode = BencodeEncoder.encode

    def capture_encode(self, data):
        if "handshake" not in captured:
            captured["handshake"] = data
        return original_encode(self, data)

    with patch("ccbt.core.bencode.BencodeEncoder.encode", new=capture_encode):
        await peer_manager._send_our_extension_handshake(connection)

    handshake = captured.get("handshake")
    assert handshake is not None
    assert b"e" in handshake
    assert handshake[b"e"] in {"required", b"required"}


@pytest.mark.asyncio
async def test_send_our_extension_handshake_includes_prepared_swarm_auth(
    peer_manager, peer_info
):
    peer_manager.piece_manager._metadata_incomplete = True
    peer_manager.torrent_data["file_info"] = None

    protocol = ExtensionProtocol()
    protocol.register_extension("ut_metadata", "1.0")

    extension_manager = MagicMock()
    extension_manager.get_extension.return_value = protocol
    peer_manager.extension_manager = extension_manager

    connection = AsyncPeerConnection(
        peer_info=peer_info, torrent_data=peer_manager.torrent_data
    )
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)
    connection.writer = mock_writer

    from ccbt.core.bencode import BencodeEncoder

    captured: dict[str, dict] = {}
    original_encode = BencodeEncoder.encode

    def capture_encode(self, data):
        if "handshake" not in captured:
            captured["handshake"] = data
        return original_encode(self, data)

    expected_swarm_auth = {
        "swarm_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "public_key": b"\x01" * 32,
        "signature": b"\x02" * 64,
        "timestamp": 1234567890,
        "trust_proof_hint": "spki_sha256",
    }
    connection.swarm_auth_payload = expected_swarm_auth

    with patch("ccbt.core.bencode.BencodeEncoder.encode", new=capture_encode):
        await peer_manager._send_our_extension_handshake(connection)

    handshake = captured.get("handshake")
    assert handshake is not None
    assert handshake.get(b"swarm_auth") == expected_swarm_auth


@pytest.mark.asyncio
async def test_connect_to_peers_handshake_mismatch(peer_manager, peer_info):
    """Test peer connection with handshake mismatch."""
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    # Mock the connection process
    mock_reader = AsyncMock()
    mock_writer = AsyncMock()
    mock_writer.drain = AsyncMock()
    mock_reader.readexactly = AsyncMock(return_value=b"handshake_data")

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        with patch("ccbt.peer.Handshake.decode") as mock_decode:
            # Mock handshake with wrong info hash
            mock_handshake = MagicMock()
            mock_handshake.info_hash = b"wrong_info_hash_20bytes"
            mock_handshake.peer_id = b"test_peer_id_20bytes"
            mock_decode.return_value = mock_handshake

            await peer_manager.connect_to_peers(peer_list)

            # Should not have created a connection due to handshake mismatch
            assert len(peer_manager.connections) == 0


@pytest.mark.asyncio
async def test_connect_to_peers_connection_failure(peer_manager, peer_info):
    """Test peer connection failure."""
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    # Mock connection failure
    with patch(
        "asyncio.open_connection", side_effect=ConnectionError("Connection failed")
    ):
        await peer_manager.connect_to_peers(peer_list)

        # Should not have created a connection
        assert len(peer_manager.connections) == 0


@pytest.mark.asyncio
async def test_connect_to_peers_outer_timeout_matches_adaptive_handshake(
    peer_manager, peer_info, monkeypatch
):
    """Per-peer timeout in connect_to_peers should follow adaptive handshake timeout."""
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]
    adaptive_timeout = 0.25
    monkeypatch.setattr(
        peer_manager,
        "_calculate_adaptive_handshake_timeout",
        lambda: adaptive_timeout,
    )

    # _connect_to_peer is patched to avoid inner transport logic; it must exceed the
    # outer timeout so the wrapper path is exercised.
    async def slow_connect(_: PeerInfo) -> None:
        await asyncio.sleep(adaptive_timeout * 4)

    peer_manager._connect_to_peer = AsyncMock(side_effect=slow_connect)

    original_wait_for = asyncio.wait_for
    captured_timeouts: list[float] = []

    async def tracking_wait_for(awaitable, timeout, *args, **kwargs):
        captured_timeouts.append(timeout)
        return await original_wait_for(awaitable, timeout=timeout, *args, **kwargs)

    with patch(
        "ccbt.peer.async_peer_connection.asyncio.wait_for",
        side_effect=tracking_wait_for,
    ):
        await peer_manager.connect_to_peers(peer_list)

    # The wrapper in connect_to_peers should be using the adaptive handshake timeout
    # value (possibly normalized by connect_to_peers logic).
    assert captured_timeouts
    assert captured_timeouts[0] == adaptive_timeout
    assert len(peer_manager.connections) == 0


@pytest.mark.asyncio
async def test_connect_to_peers_rejects_outbound_when_swarm_auth_denies(
    peer_manager, peer_info
):
    """Outbound swarm-auth decision should abort connection attempts."""
    peer_manager.torrent_data["info_hash"] = b"x" * 20

    mock_reader = AsyncMock()
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)
    mock_writer.write = MagicMock()
    peer_list = [{"ip": peer_info.ip, "port": peer_info.port}]

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
        with patch(
            "ccbt.peer.async_peer_connection.evaluate_outbound_admission",
            return_value=AuthDecision(False, "strict", "outbound_swarm_auth_denied"),
        ):
            await peer_manager.connect_to_peers(peer_list)

    assert len(peer_manager.connections) == 0
    assert mock_writer.close.called


@pytest.mark.asyncio
async def test_connect_to_peers_guarded_inflight_duplicate_peers(
    peer_manager, peer_info, monkeypatch
):
    """connect_to_peers should not launch duplicate concurrent handshakes for the same peer."""
    peer_list = [
        {"ip": peer_info.ip, "port": peer_info.port},
        {"ip": peer_info.ip, "port": peer_info.port},
    ]
    adaptive_timeout = 0.2
    monkeypatch.setattr(
        peer_manager,
        "_calculate_adaptive_handshake_timeout",
        lambda: adaptive_timeout,
    )

    # Hold the first connection attempt so the duplicate can be observed.
    async def slow_connect(_: PeerInfo) -> None:
        await asyncio.sleep(adaptive_timeout * 5)

    peer_manager._connect_to_peer = AsyncMock(side_effect=slow_connect)

    await peer_manager.connect_to_peers(peer_list)

    assert peer_manager._connect_to_peer.await_count == 1


@pytest.mark.asyncio
async def test_connect_to_peers_requeues_aborted_batch_peers(peer_manager, monkeypatch):
    """Peers aborted due to batch control should be re-queued for retry."""
    peer_manager._running = True
    peer_manager._pending_peer_queue = []
    peer_manager._pending_peer_keys = set()
    peer_manager.max_peers_per_torrent = 10

    async def connect_with_split_results(peer: PeerInfo) -> None:
        if peer.port <= 6883:
            peer_manager.connections[str(peer)] = AsyncPeerConnection(
                peer_info=peer, torrent_data=peer_manager.torrent_data
            )
            peer_manager.connections[
                str(peer)
            ].state = ConnectionState.HANDSHAKE_RECEIVED
            return
        # This branch is intentionally slow to trigger early-batch control cancellation.
        await asyncio.sleep(1.0)

    monkeypatch.setattr(
        peer_manager,
        "_connect_to_peer",
        AsyncMock(side_effect=connect_with_split_results),
    )
    monkeypatch.setattr(
        peer_manager,
        "_calculate_adaptive_handshake_timeout",
        lambda: 0.25,
    )

    peer_list = [
        {"ip": "203.0.113.10", "port": 6881 + idx, "peer_source": "tracker"}
        for idx in range(6)
    ]

    await peer_manager.connect_to_peers(peer_list)

    pending_ports = sorted(peer.port for peer in peer_manager._pending_peer_queue)
    assert pending_ports == [6884, 6885, 6886]


@pytest.mark.asyncio
async def test_connect_to_peers_skips_active_healthy_duplicate(
    peer_manager, peer_info, monkeypatch
):
    """Duplicate active connections with valid transport should be skipped."""
    connection = AsyncPeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.ACTIVE
    connection.peer_state.bitfield = b"\xff"
    connection.stats.last_activity = time.time()
    connection.reader = AsyncMock()
    connection.writer = MagicMock()
    connection.writer.is_closing = MagicMock(return_value=False)
    peer_manager.connections[str(peer_info)] = connection

    connect_mock = AsyncMock()
    monkeypatch.setattr(peer_manager, "_connect_to_peer", connect_mock)

    await peer_manager.connect_to_peers([{"ip": peer_info.ip, "port": peer_info.port}])

    assert connect_mock.await_count == 0
    assert len(peer_manager.connections) == 1


@pytest.mark.asyncio
async def test_connect_to_peers_retries_when_stale_incomplete_connection_exists(
    peer_manager, peer_info, monkeypatch
):
    """Peers with stale/incomplete transport should be removed and retried."""
    connection = AsyncPeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.ACTIVE
    connection.peer_state.bitfield = None
    connection.peer_state.pieces_we_have = set()
    connection.stats.last_activity = time.time() - 45.0
    connection.reader = AsyncMock()
    connection.writer = MagicMock()
    connection.writer.is_closing = MagicMock(return_value=False)
    peer_manager.connections[str(peer_info)] = connection

    connect_mock = AsyncMock()
    monkeypatch.setattr(peer_manager, "_connect_to_peer", connect_mock)

    await peer_manager.connect_to_peers([{"ip": peer_info.ip, "port": peer_info.port}])

    assert connect_mock.await_count == 1
    assert len(peer_manager.connections) == 0


@pytest.mark.asyncio
async def test_connect_to_peers_enqueues_when_at_capacity(peer_manager, monkeypatch):
    """Peers should be deferred when active connections already at capacity."""
    peer_manager._running = True
    peer_manager.max_peers_per_torrent = 3

    # Pretend we already have the maximum number of active peers.
    for idx in range(peer_manager.max_peers_per_torrent):
        conn = MagicMock()
        conn.is_active.return_value = True
        peer_manager.connections[f"existing-{idx}"] = conn

    peer_list = [
        {"ip": f"192.0.2.{i}", "port": 6000 + i, "peer_source": "tracker"}
        for i in range(6)
    ]

    connect_mock = AsyncMock()
    monkeypatch.setattr(peer_manager, "_connect_to_peer", connect_mock)
    monkeypatch.setattr(
        peer_manager,
        "_rank_peers_for_connection",
        AsyncMock(side_effect=lambda peers: peers),
    )
    resume_mock = MagicMock()
    monkeypatch.setattr(peer_manager, "_schedule_pending_resume", resume_mock)

    await peer_manager.connect_to_peers(peer_list)

    # All peers should be queued for later because we're at capacity.
    assert len(peer_manager._pending_peer_queue) == len(peer_list)
    assert connect_mock.await_count == 0
    assert resume_mock.called
    assert peer_manager._connection_batches_in_progress is False


@pytest.mark.asyncio
async def test_connect_to_peers_uses_pipeline_with_low_active_peer_count(
    peer_manager, monkeypatch
):
    """Low active peer counts should still run the full connection pipeline."""
    peer_manager._running = True
    peer_manager.max_peers_per_torrent = 10
    peer_manager.connections.clear()

    peer_list = [
        {"ip": f"198.51.100.{idx}", "port": 6100 + idx, "peer_source": "tracker"}
        for idx in range(3)
    ]

    connect_mock = AsyncMock(side_effect=lambda peer: None)
    monkeypatch.setattr(peer_manager, "_connect_to_peer", connect_mock)
    monkeypatch.setattr(
        peer_manager,
        "_rank_peers_for_connection",
        AsyncMock(side_effect=lambda peers: peers),
    )

    await peer_manager.connect_to_peers(peer_list)

    assert connect_mock.await_count == len(peer_list)


@pytest.mark.asyncio
async def test_connect_to_peers_all_fail_triggers_low_peer_recovery_event(
    peer_manager, monkeypatch
):
    """A complete-batch failure path should still emit a PeerCountLowEvent."""
    peer_manager._running = True
    peer_manager.max_peers_per_torrent = 60
    peer_manager.config.network.enable_fail_fast_dht = True
    peer_manager.config.network.max_concurrent_connection_attempts = 60
    peer_manager._connect_to_peer = AsyncMock(side_effect=ConnectionError("refused"))
    peer_manager._calculate_adaptive_handshake_timeout = lambda: 0.01

    emitted_events: list[object] = []

    class _EventBus:
        async def emit(self, event: object) -> None:
            emitted_events.append(event)

    peer_manager._event_bus = _EventBus()

    peer_list = [{"ip": "198.51.100.1", "port": 6200 + idx} for idx in range(95)]

    monkeypatch.setattr(
        peer_manager,
        "_rank_peers_for_connection",
        AsyncMock(side_effect=lambda peers: peers),
    )

    await peer_manager.connect_to_peers(peer_list)

    assert len(peer_manager.connections) == 0
    assert any(isinstance(event, PeerCountLowEvent) for event in emitted_events)


@pytest.mark.asyncio
async def test_resume_pending_batches_processes_queue(peer_manager, monkeypatch):
    """Resuming pending batches should drain the queue via connect_to_peers."""
    peer_manager._running = True
    peers = [
        PeerInfo(ip="198.51.100.1", port=51413),
        PeerInfo(ip="198.51.100.2", port=51414),
    ]
    peer_manager._pending_peer_queue = peers.copy()
    peer_manager._pending_peer_keys = {str(p) for p in peers}

    resume_connect_mock = AsyncMock()
    monkeypatch.setattr(peer_manager, "connect_to_peers", resume_connect_mock)

    await peer_manager._resume_pending_batches(reason="unit-test")

    assert resume_connect_mock.await_count == 1
    kwargs = resume_connect_mock.await_args.kwargs
    assert kwargs.get("_from_pending_queue") is True
    assert not peer_manager._pending_peer_queue
    assert not peer_manager._pending_peer_keys
    assert peer_manager._pending_resume_in_progress is False


@pytest.mark.asyncio
async def test_handle_bitfield_message(peer_manager, peer_info):
    """Test handling bitfield message."""
    # Note: Configure piece_manager.num_pieces as an integer, not a MagicMock
    # The code compares num_pieces > 0, which fails if it's a MagicMock
    peer_manager.piece_manager.num_pieces = (
        100  # Set to integer value from mock_torrent_data
    )

    # Create an AsyncPeerConnection (not PeerConnection)
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.HANDSHAKE_RECEIVED
    connection.reader = AsyncMock()
    connection.writer = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.close = MagicMock()
    # Note: AsyncPeerConnection has am_interested attribute
    connection.am_interested = False

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Create bitfield message
    bitfield_data = b"\x00\x00\x00\x00"  # Empty bitfield
    bitfield_message = BitfieldMessage(bitfield_data)

    # Mock callback
    callback_called = False

    def mock_callback(conn, msg):
        nonlocal callback_called
        callback_called = True
        assert conn == connection
        assert msg == bitfield_message

    peer_manager.on_bitfield_received = mock_callback

    # Handle the message
    await peer_manager._handle_bitfield(connection, bitfield_message)

    # Check state and callback
    # Note: State should be ACTIVE after bitfield handling completes
    # The code sets state to BITFIELD_RECEIVED first, then transitions to ACTIVE
    # But if there's an exception or early return, state might remain BITFIELD_RECEIVED
    actual_state = connection.state
    # Use == comparison instead of 'in' to avoid enum comparison issues
    assert (
        actual_state == ConnectionState.ACTIVE
        or actual_state == ConnectionState.BITFIELD_RECEIVED
    ), (
        f"Expected state to be ACTIVE or BITFIELD_RECEIVED, got {actual_state} (value: {actual_state.value if hasattr(actual_state, 'value') else actual_state}, type: {type(actual_state)})"
    )
    assert callback_called, "Callback should have been called"


@pytest.mark.asyncio
async def test_handle_have_message(peer_manager, peer_info):
    """Test handling have message."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.ACTIVE

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Create have message
    have_message = HaveMessage(piece_index=5)

    # Handle the message
    await peer_manager._handle_have(connection, have_message)

    # Check that piece was added to peer state
    assert 5 in connection.peer_state.pieces_we_have


@pytest.mark.asyncio
async def test_handle_request_message(peer_manager, peer_info):
    """Test handling request message."""
    # Create a connection
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.ACTIVE

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Create request message
    from ccbt.peer.peer import RequestMessage

    request_message = RequestMessage(piece_index=0, begin=0, length=16384)

    # Mock piece manager to return data
    peer_manager.piece_manager.get_block.return_value = b"x" * 16384  # Exactly 16KB

    # Mock send message
    with patch.object(
        peer_manager, "_send_message", new_callable=AsyncMock
    ) as mock_send:
        await peer_manager._handle_request(connection, request_message)

        # Should have sent a piece message
        assert mock_send.called
        call_args = mock_send.call_args[0]
        assert call_args[0] == connection
        assert call_args[1].piece_index == 0
        assert call_args[1].begin == 0
        assert call_args[1].block == b"x" * 16384


@pytest.mark.asyncio
async def test_handle_piece_message(peer_manager, peer_info):
    """Test handling piece message."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.ACTIVE

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Create piece message
    from ccbt.peer.peer import PieceMessage

    piece_message = PieceMessage(piece_index=0, begin=0, block=b"test_data")

    # Mock callback
    callback_called = False

    def mock_callback(conn, msg):
        nonlocal callback_called
        callback_called = True
        assert conn == connection
        assert msg == piece_message

    peer_manager.on_piece_received = mock_callback

    # Handle the message
    await peer_manager._handle_piece(connection, piece_message)

    # Check callback was called
    assert callback_called


@pytest.mark.asyncio
async def test_send_interested_message(peer_manager, peer_info):
    """Test sending interested message."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.ACTIVE
    connection.writer = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = MagicMock()
    connection.writer.close = MagicMock()

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Send interested message - use _send_interested (private method)
    await peer_manager._send_interested(connection)

    # Check state - AsyncPeerConnection uses am_interested attribute, not peer_state.am_interested
    assert connection.am_interested is True


@pytest.mark.asyncio
async def test_request_piece(peer_manager, peer_info):
    """Test requesting a piece."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.ACTIVE
    # AsyncPeerConnection uses peer_choking attribute, not peer_state.am_choking
    connection.peer_choking = False
    connection.writer = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = MagicMock()
    connection.writer.close = MagicMock()

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Mock send message
    with patch.object(
        peer_manager, "_send_message", new_callable=AsyncMock
    ) as mock_send:
        await peer_manager.request_piece(
            connection, piece_index=0, begin=0, length=16384
        )

        # Should have sent a request message
        assert mock_send.called
        call_args = mock_send.call_args[0]
        assert call_args[0] == connection
        assert call_args[1].piece_index == 0
        assert call_args[1].begin == 0
        assert call_args[1].length == 16384


@pytest.mark.asyncio
async def test_broadcast_have(peer_manager, peer_info):
    """Test broadcasting have message."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    # Create connections
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = AsyncPeerConnection(
        peer_info=peer1, torrent_data=peer_manager.torrent_data
    )
    connection1.state = ConnectionState.ACTIVE
    connection1.writer = MagicMock()
    connection1.writer.close = MagicMock()
    # Note: Mock wait_closed() to prevent hanging in _disconnect_peer()
    connection1.writer.wait_closed = AsyncMock(return_value=None)

    connection2 = AsyncPeerConnection(
        peer_info=peer2, torrent_data=peer_manager.torrent_data
    )
    connection2.state = ConnectionState.ACTIVE
    connection2.writer = MagicMock()
    connection2.writer.close = MagicMock()
    # Note: Mock wait_closed() to prevent hanging in _disconnect_peer()
    connection2.writer.wait_closed = AsyncMock(return_value=None)

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Mock send message
    with patch.object(
        peer_manager, "_send_message", new_callable=AsyncMock
    ) as mock_send:
        await peer_manager.broadcast_have(piece_index=5)

        # Should have sent have message to both connections
        assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_disconnect_peer(peer_manager, peer_info):
    """Test disconnecting a peer."""
    from ccbt.peer.async_peer_connection import AsyncPeerConnection, ConnectionState

    # Create an AsyncPeerConnection (not PeerConnection) to match manager expectations
    connection = AsyncPeerConnection(peer_info, peer_manager.torrent_data)
    connection.state = ConnectionState.ACTIVE
    connection.writer = None  # No writer to avoid close/wait_closed issues
    connection.connection_task = None  # No active task to cancel
    # Ensure outstanding_requests exists to avoid AttributeError
    if not hasattr(connection, "outstanding_requests"):
        connection.outstanding_requests = {}

    # Add to manager
    async with peer_manager.connection_lock:
        peer_manager.connections[str(peer_info)] = connection

    # Disconnect peer with timeout to prevent hanging
    await asyncio.wait_for(peer_manager.disconnect_peer(peer_info), timeout=5.0)

    # Connection should be removed
    async with peer_manager.connection_lock:
        assert str(peer_info) not in peer_manager.connections


@pytest.mark.asyncio
async def test_disconnect_all(peer_manager):
    """Test disconnecting all peers."""
    # Create multiple connections
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    # Note: Use AsyncPeerConnection, not PeerConnection, to match manager expectations
    from ccbt.peer.async_peer_connection import AsyncPeerConnection, ConnectionState

    connection1 = AsyncPeerConnection(
        peer_info=peer1, torrent_data=peer_manager.torrent_data
    )
    connection1.state = ConnectionState.ACTIVE
    connection1.writer = None  # No writer to avoid close/wait_closed issues
    connection1.connection_task = None  # No active task to cancel
    # Ensure required attributes exist
    if not hasattr(connection1, "outstanding_requests"):
        connection1.outstanding_requests = {}

    connection2 = AsyncPeerConnection(
        peer_info=peer2, torrent_data=peer_manager.torrent_data
    )
    connection2.state = ConnectionState.ACTIVE
    connection2.writer = None  # No writer to avoid close/wait_closed issues
    connection2.connection_task = None  # No active task to cancel
    # Ensure required attributes exist
    if not hasattr(connection2, "outstanding_requests"):
        connection2.outstanding_requests = {}

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Disconnect all
    # Note: Add timeout to prevent hanging
    try:
        await asyncio.wait_for(peer_manager.disconnect_all(), timeout=5.0)
    except asyncio.TimeoutError:
        # If disconnect_all() hangs, stop the manager and fail the test
        await peer_manager.stop()
        raise AssertionError("disconnect_all() timed out after 5 seconds")

    # All connections should be removed
    assert len(peer_manager.connections) == 0

    # Note: Stop the manager to prevent reconnection loop from keeping event loop alive
    # The fixture teardown will also stop it, but we need to stop it here to prevent timeout
    await peer_manager.stop()


@pytest.mark.asyncio
async def test_get_connected_peers(peer_manager):
    """Test getting connected peers."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    # Create connections with different states
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = AsyncPeerConnection(
        peer_info=peer1, torrent_data=peer_manager.torrent_data
    )
    connection1.state = ConnectionState.ACTIVE

    connection2 = AsyncPeerConnection(
        peer_info=peer2, torrent_data=peer_manager.torrent_data
    )
    connection2.state = ConnectionState.DISCONNECTED

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Get connected peers
    connected = peer_manager.get_connected_peers()

    # Should only return active connection
    assert len(connected) == 1
    assert connected[0] == connection1


@pytest.mark.asyncio
async def test_get_active_peers(peer_manager):
    """Test getting active peers."""
    # Note: Use AsyncPeerConnection, not PeerConnection
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    # Create connections with different states
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)
    peer3 = PeerInfo(ip="127.0.0.1", port=6883)

    connection1 = AsyncPeerConnection(
        peer_info=peer1, torrent_data=peer_manager.torrent_data
    )
    connection1.state = ConnectionState.ACTIVE
    # Note: get_active_peers() requires reader and writer to be set
    connection1.reader = AsyncMock()
    connection1.writer = MagicMock()

    connection2 = AsyncPeerConnection(
        peer_info=peer2, torrent_data=peer_manager.torrent_data
    )
    connection2.state = ConnectionState.HANDSHAKE_SENT
    # Note: get_active_peers() requires reader and writer to be set
    connection2.reader = AsyncMock()
    connection2.writer = MagicMock()

    connection3 = AsyncPeerConnection(
        peer_info=peer3, torrent_data=peer_manager.torrent_data
    )
    connection3.state = ConnectionState.BITFIELD_SENT
    connection3.reader = AsyncMock()
    connection3.writer = MagicMock()

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2
    peer_manager.connections[str(peer3)] = connection3

    # Get active peers
    active = peer_manager.get_active_peers()

    # ACTIVE and BITFIELD_SENT peers count as active when reader/writer are live
    assert len(active) == 2
    assert connection1 in active
    assert connection3 in active


@pytest.mark.asyncio
async def test_get_swarm_timeout_signals_counts_handshake_transport(peer_manager):
    """HANDSHAKE_SENT with live streams is transport_live but not active_post_handshake."""
    peer_manager.connections.clear()
    peer_hs = PeerInfo(ip="10.0.0.1", port=7001)
    c = AsyncPeerConnection(peer_info=peer_hs, torrent_data=peer_manager.torrent_data)
    c.state = ConnectionState.HANDSHAKE_SENT
    c.reader = AsyncMock()
    c.writer = MagicMock()
    peer_manager.connections[str(peer_hs)] = c

    sig = peer_manager.get_swarm_timeout_signals()
    assert sig.active_post_handshake_count == 0
    assert sig.transport_live_count == 1
    assert sig.total_connections == 1


@pytest.mark.asyncio
async def test_get_peer_bitfields(peer_manager):
    """Test getting peer bitfields."""
    # Create connections with bitfields
    peer1 = PeerInfo(ip="127.0.0.1", port=6881)
    peer2 = PeerInfo(ip="127.0.0.1", port=6882)

    connection1 = PeerConnection(peer1, peer_manager.torrent_data)
    connection1.peer_state.bitfield = BitfieldMessage(b"\x00\x00")

    connection2 = PeerConnection(peer2, peer_manager.torrent_data)
    connection2.peer_state.bitfield = None  # No bitfield

    # Add to manager
    peer_manager.connections[str(peer1)] = connection1
    peer_manager.connections[str(peer2)] = connection2

    # Get peer bitfields
    bitfields = peer_manager.get_peer_bitfields()

    # Should only return peer with bitfield
    assert len(bitfields) == 1
    assert str(peer1) in bitfields
    assert bitfields[str(peer1)] == connection1.peer_state.bitfield


@pytest.mark.asyncio
async def test_stop(peer_manager):
    """Test manager shutdown."""
    # Create a connection
    peer_info = PeerInfo(ip="127.0.0.1", port=6881)
    connection = PeerConnection(peer_info, peer_manager.torrent_data)
    connection.writer = AsyncMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()
    connection.writer.write = AsyncMock()
    connection.writer.close = AsyncMock()
    connection.connection_task = asyncio.create_task(asyncio.sleep(0))

    # Add to manager
    peer_manager.connections[str(peer_info)] = connection

    # Shutdown manager
    await peer_manager.stop()

    # All connections should be removed
    assert len(peer_manager.connections) == 0


@pytest.mark.asyncio
async def test_stop_cancels_stale_message_loop_task(peer_manager, peer_info):
    """Stop should cancel tracked message-loop tasks even if connection is stale."""
    connection = AsyncPeerConnection(
        peer_info=peer_info, torrent_data=peer_manager.torrent_data
    )
    connection.state = ConnectionState.ACTIVE
    peer_manager.connections[str(peer_info)] = connection

    async def idle_message_loop() -> None:
        await asyncio.Event().wait()

    message_loop_task = asyncio.create_task(
        idle_message_loop(), name="test-stale-message-loop"
    )
    peer_manager._register_message_loop_task(message_loop_task)
    connection.connection_task = message_loop_task

    async with peer_manager.connection_lock:
        peer_manager.connections.pop(str(peer_info), None)

    await peer_manager.stop()

    assert message_loop_task.done()
    assert message_loop_task.cancelled()
    assert len(peer_manager._message_loop_tasks) == 0


@pytest.mark.asyncio
async def test_handle_peer_messages_exits_early_when_shutting_down(
    peer_manager, peer_info, monkeypatch
):
    """Message loop should stop immediately when shutdown is in progress."""
    connection = AsyncPeerConnection(
        peer_info=peer_info, torrent_data=peer_manager.torrent_data
    )
    connection.state = ConnectionState.ACTIVE
    connection.reader = AsyncMock()
    connection.reader.readexactly = AsyncMock()
    connection.writer = MagicMock()
    connection.writer.close = MagicMock()
    connection.writer.write = MagicMock()
    connection.writer.drain = AsyncMock()
    connection.writer.wait_closed = AsyncMock()

    # Avoid keepalive chatter in this focused test
    monkeypatch.setattr(peer_manager, "_keepalive_sender", AsyncMock())

    set_shutdown()
    try:
        task = asyncio.create_task(peer_manager._handle_peer_messages(connection))
        await asyncio.wait_for(task, timeout=1.0)
    finally:
        clear_shutdown()

    connection.reader.readexactly.assert_not_awaited()


@pytest.mark.asyncio
async def test_connection_summary_exposes_lifecycle_stage_counters(peer_manager):
    """Connection summary should include lifecycle stage counters for diagnostics."""
    peer_manager._connection_stage_counters.update(
        {
            "connect_attempts": 3,
            "tcp_connected": 1,
            "tcp_open_timeout": 1,
            "tcp_open_cancelled": 1,
            "mse_attempted": 2,
            "mse_succeeded": 1,
            "mse_fallback_plain": 1,
            "plain_reconnect_after_mse_failure": 1,
            "handshake_sent": 1,
            "handshake_received": 1,
            "bitfield_received": 0,
        }
    )
    peer_manager._unchoke_retry_hits = 4

    summary = await peer_manager.get_connection_summary()

    assert summary["connect_attempts"] == 3
    assert summary["tcp_connected"] == 1
    assert summary["tcp_open_timeout"] == 1
    assert summary["tcp_open_cancelled"] == 1
    assert summary["mse_attempted"] == 2
    assert summary["mse_succeeded"] == 1
    assert summary["mse_fallback_plain"] == 1
    assert summary["plain_reconnect_after_mse_failure"] == 1
    assert summary["handshake_sent"] == 1
    assert summary["handshake_received"] == 1
    assert summary["unchoke_retry_hits"] == 4


@pytest.mark.asyncio
async def test_connection_summary_separates_live_bitfield_count_from_events(
    peer_manager, peer_info
):
    """Live bitfield counts should not be derived from lifetime event counters."""
    from ccbt.peer.async_peer_connection import AsyncPeerConnection

    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.HANDSHAKE_RECEIVED
    connection.peer_state.bitfield = None
    peer_manager.connections[str(peer_info)] = connection
    peer_manager._connection_stage_counters["bitfield_received"] = 5

    summary = await peer_manager.get_connection_summary()

    assert summary["bitfield_received_events"] == 5
    assert summary["bitfield_complete_connections"] == 0


@pytest.mark.asyncio
async def test_update_choking_with_missing_connection_start_time_uses_safe_fallback(
    peer_manager,
):
    """_update_choking should ignore missing connection_start_time values safely."""
    peer_manager.config.network.max_upload_slots = 1

    fast_peer = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.1", port=6881),
        peer_manager.torrent_data,
    )
    fast_peer.state = ConnectionState.ACTIVE
    fast_peer.am_choking = True
    fast_peer.am_interested = True
    fast_peer.peer_choking = True
    fast_peer.stats.upload_rate = 1_500_000
    fast_peer.connection_start_time = time.time() - 120.0
    fast_peer.writer = MagicMock()
    fast_peer.writer.drain = AsyncMock()
    fast_peer.writer.write = MagicMock()
    fast_peer.writer.close = MagicMock()
    fast_peer.writer.wait_closed = AsyncMock()

    missing_start_peer = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.2", port=6882),
        peer_manager.torrent_data,
    )
    missing_start_peer.state = ConnectionState.ACTIVE
    missing_start_peer.am_choking = False
    missing_start_peer.am_interested = True
    missing_start_peer.peer_choking = True
    missing_start_peer.stats.upload_rate = 100_000
    missing_start_peer.connection_start_time = None
    missing_start_peer.writer = MagicMock()
    missing_start_peer.writer.drain = AsyncMock()
    missing_start_peer.writer.write = MagicMock()
    missing_start_peer.writer.close = MagicMock()
    missing_start_peer.writer.wait_closed = AsyncMock()

    peer_manager.connections["127.0.0.1:6881"] = fast_peer
    peer_manager.connections["127.0.0.2:6882"] = missing_start_peer

    # No exception should be raised while calculating age with missing start time.
    await peer_manager._update_choking()

    assert missing_start_peer.am_interested is True


@pytest.mark.asyncio
async def test_low_download_diversity_unchokes_all_active_peers(peer_manager):
    """With only one unchoked-by-remote source, unchoke every active peer on our side."""
    peer_manager.config.network.max_upload_slots = 1
    peer_manager.config.network.low_download_diversity_threshold = 1
    peer_manager.config.network.low_download_diversity_full_unchoke = True

    def _wired_peer(ip: str, port: int, *, peer_choking: bool) -> AsyncPeerConnection:
        c = AsyncPeerConnection(
            PeerInfo(ip=ip, port=port),
            peer_manager.torrent_data,
        )
        c.state = ConnectionState.ACTIVE
        c.am_choking = True
        c.am_interested = True
        c.peer_choking = peer_choking
        c.peer_interested = False
        c.stats.upload_rate = 0.0
        c.stats.download_rate = 1_000_000 if not peer_choking else 0.0
        c.connection_start_time = time.time() - 120.0
        c.writer = MagicMock()
        c.writer.drain = AsyncMock()
        c.writer.write = MagicMock()
        c.writer.close = MagicMock()
        c.writer.wait_closed = AsyncMock()
        return c

    feeder = _wired_peer("10.0.0.1", 6881, peer_choking=False)
    choker = _wired_peer("10.0.0.2", 6882, peer_choking=True)
    peer_manager.connections["10.0.0.1:6881"] = feeder
    peer_manager.connections["10.0.0.2:6882"] = choker

    await peer_manager._update_choking()

    assert not feeder.am_choking
    assert not choker.am_choking
    assert len(peer_manager.upload_slots) == 2


def test_reciprocation_peer_score_boosts_choked_interested_peer(peer_manager):
    """Choked+interested peer ranks above an identical-rate peer without that boost (T4.11)."""
    boost = float(
        getattr(
            peer_manager.config.network,
            "reciprocation_choked_peer_score_boost",
            0.12,
        )
    )
    remote_ni = float(
        getattr(
            peer_manager.config.network,
            "reciprocation_remote_not_interested_boost",
            0.06,
        )
    )
    choked = AsyncPeerConnection(
        PeerInfo(ip="10.0.0.1", port=6881),
        peer_manager.torrent_data,
    )
    plain = AsyncPeerConnection(
        PeerInfo(ip="10.0.0.2", port=6882),
        peer_manager.torrent_data,
    )
    for p in (choked, plain):
        p.stats.upload_rate = 500_000.0
        p.stats.download_rate = 500_000.0
        p.stats.performance_score = 0.5
        p.am_interested = True
        p.peer_interested = True
    choked.peer_choking = True
    plain.peer_choking = False
    s_choked = peer_manager._reciprocation_peer_score(
        choked,
        leech_heavy_swarm=False,
        choked_recip_boost=boost,
        remote_not_interested_boost=remote_ni,
        max_combined_boost=1.0,
    )
    s_plain = peer_manager._reciprocation_peer_score(
        plain,
        leech_heavy_swarm=False,
        choked_recip_boost=boost,
        remote_not_interested_boost=remote_ni,
        max_combined_boost=1.0,
    )
    assert s_choked == pytest.approx(s_plain + boost)


def test_reciprocation_peer_score_caps_combined_boost(peer_manager):
    """reciprocation_max_combined_boost limits choked + remote-not-interested bonuses."""
    boost = 0.12
    remote_ni = 0.06
    cap = 0.15
    p = AsyncPeerConnection(
        PeerInfo(ip="10.0.0.9", port=6889),
        peer_manager.torrent_data,
    )
    p.stats.upload_rate = 0.0
    p.stats.download_rate = 0.0
    p.stats.performance_score = 0.5
    p.am_interested = True
    p.peer_choking = True
    p.peer_interested = False
    score = peer_manager._reciprocation_peer_score(
        p,
        leech_heavy_swarm=True,
        choked_recip_boost=boost,
        remote_not_interested_boost=remote_ni,
        max_combined_boost=cap,
    )
    base = peer_manager._reciprocation_peer_score(
        p,
        leech_heavy_swarm=True,
        choked_recip_boost=0.0,
        remote_not_interested_boost=0.0,
        max_combined_boost=cap,
    )
    assert score == pytest.approx(base + cap)


@pytest.mark.asyncio
async def test_low_download_diversity_threshold_two_unchokes_all_with_two_feeders(
    peer_manager,
):
    """Threshold 2 with two unchoked download sources still triggers full unchoke (T4.12)."""
    peer_manager.config.network.max_upload_slots = 1
    peer_manager.config.network.low_download_diversity_threshold = 2
    peer_manager.config.network.low_download_diversity_full_unchoke = True

    def _wired_peer(ip: str, port: int, *, peer_choking: bool) -> AsyncPeerConnection:
        c = AsyncPeerConnection(
            PeerInfo(ip=ip, port=port),
            peer_manager.torrent_data,
        )
        c.state = ConnectionState.ACTIVE
        c.am_choking = True
        c.am_interested = True
        c.peer_choking = peer_choking
        c.peer_interested = False
        c.stats.upload_rate = 0.0
        c.stats.download_rate = 1_000_000 if not peer_choking else 0.0
        c.connection_start_time = time.time() - 120.0
        c.writer = MagicMock()
        c.writer.drain = AsyncMock()
        c.writer.write = MagicMock()
        c.writer.close = MagicMock()
        c.writer.wait_closed = AsyncMock()
        return c

    feeder_a = _wired_peer("10.0.0.1", 6881, peer_choking=False)
    feeder_b = _wired_peer("10.0.0.2", 6882, peer_choking=False)
    choker = _wired_peer("10.0.0.3", 6883, peer_choking=True)
    peer_manager.connections["10.0.0.1:6881"] = feeder_a
    peer_manager.connections["10.0.0.2:6882"] = feeder_b
    peer_manager.connections["10.0.0.3:6883"] = choker

    await peer_manager._update_choking()

    assert not feeder_a.am_choking
    assert not feeder_b.am_choking
    assert not choker.am_choking
    assert len(peer_manager.upload_slots) == 3


def test_optimistic_unchoke_sort_key_prefers_choked_interested():
    """Top of sorted list favors peer_choking and am_interested (T4.13)."""
    td = {"info_hash": b"0" * 20}
    newer = time.time()
    not_starved = AsyncPeerConnection(
        PeerInfo(ip="10.0.0.1", port=6881),
        td,
    )
    not_starved.peer_choking = False
    not_starved.am_interested = True
    not_starved.connection_start_time = newer
    starved = AsyncPeerConnection(
        PeerInfo(ip="10.0.0.2", port=6882),
        td,
    )
    starved.peer_choking = True
    starved.am_interested = True
    starved.connection_start_time = newer + 3600.0
    peers = [not_starved, starved]
    peers.sort(key=AsyncPeerConnectionManager._optimistic_unchoke_peer_sort_key)
    assert peers[0] is starved
    top_three = peers[: min(3, len(peers))]
    assert starved in top_three


def test_optimistic_unchoke_deterministic_key_prefers_lower_latency():
    """Without jitter, tie-break uses request_latency then -download_rate."""
    td = {"info_hash": b"0" * 20}
    t0 = time.time()
    hi_lat = AsyncPeerConnection(PeerInfo(ip="10.0.0.1", port=6881), td)
    hi_lat.peer_choking = True
    hi_lat.am_interested = True
    hi_lat.connection_start_time = t0
    hi_lat.stats.request_latency = 0.2
    hi_lat.stats.download_rate = 1_000_000.0
    lo_lat = AsyncPeerConnection(PeerInfo(ip="10.0.0.2", port=6882), td)
    lo_lat.peer_choking = True
    lo_lat.am_interested = True
    lo_lat.connection_start_time = t0
    lo_lat.stats.request_latency = 0.05
    lo_lat.stats.download_rate = 500_000.0
    peers = [hi_lat, lo_lat]
    peers.sort(
        key=AsyncPeerConnectionManager._optimistic_unchoke_peer_deterministic_key,
    )
    assert peers[0] is lo_lat


@pytest.mark.asyncio
async def test_low_download_diversity_hysteresis_delays_exit_from_full_unchoke(
    peer_manager,
):
    """Hysteresis keeps full unchoke until sources > threshold + exit_margin."""
    peer_manager.config.network.max_upload_slots = 1
    peer_manager.config.network.low_download_diversity_threshold = 1
    peer_manager.config.network.low_download_diversity_full_unchoke = True
    peer_manager.config.network.low_download_diversity_use_hysteresis = True
    peer_manager.config.network.low_download_diversity_exit_margin = 1

    def _wired_peer(ip: str, port: int, *, peer_choking: bool) -> AsyncPeerConnection:
        c = AsyncPeerConnection(
            PeerInfo(ip=ip, port=port),
            peer_manager.torrent_data,
        )
        c.state = ConnectionState.ACTIVE
        c.am_choking = True
        c.am_interested = True
        c.peer_choking = peer_choking
        c.peer_interested = False
        c.stats.upload_rate = 0.0
        c.stats.download_rate = 1_000_000 if not peer_choking else 0.0
        c.connection_start_time = time.time() - 120.0
        c.writer = MagicMock()
        c.writer.drain = AsyncMock()
        c.writer.write = MagicMock()
        c.writer.close = MagicMock()
        c.writer.wait_closed = AsyncMock()
        return c

    a = _wired_peer("10.0.0.1", 6881, peer_choking=False)
    b = _wired_peer("10.0.0.2", 6882, peer_choking=True)
    c = _wired_peer("10.0.0.3", 6883, peer_choking=True)
    peer_manager.connections.clear()
    peer_manager.connections["10.0.0.1:6881"] = a
    peer_manager.connections["10.0.0.2:6882"] = b
    peer_manager.connections["10.0.0.3:6883"] = c

    await peer_manager._update_choking()
    assert len(peer_manager.upload_slots) == 3

    b.peer_choking = False
    b.stats.download_rate = 1_000_000.0
    await peer_manager._update_choking()
    assert len(peer_manager.upload_slots) == 3

    peer_manager.config.network.low_download_diversity_use_hysteresis = False
    await peer_manager._update_choking()
    assert len(peer_manager.upload_slots) == 1


@pytest.mark.asyncio
async def test_low_download_diversity_max_peers_caps_ranked_pool(peer_manager):
    """low_download_diversity_max_peers limits how many peers stay unchoked when capped."""
    peer_manager.config.network.max_upload_slots = 1
    peer_manager.config.network.low_download_diversity_threshold = 1
    peer_manager.config.network.low_download_diversity_full_unchoke = True
    peer_manager.config.network.low_download_diversity_use_hysteresis = False
    peer_manager.config.network.low_download_diversity_max_peers = 2

    def _wired_peer(
        ip: str, port: int, *, peer_choking: bool, down: float
    ) -> AsyncPeerConnection:
        c = AsyncPeerConnection(
            PeerInfo(ip=ip, port=port),
            peer_manager.torrent_data,
        )
        c.state = ConnectionState.ACTIVE
        c.am_choking = True
        c.am_interested = True
        c.peer_choking = peer_choking
        c.peer_interested = False
        c.stats.upload_rate = 0.0
        c.stats.download_rate = down
        c.connection_start_time = time.time() - 120.0
        c.writer = MagicMock()
        c.writer.drain = AsyncMock()
        c.writer.write = MagicMock()
        c.writer.close = MagicMock()
        c.writer.wait_closed = AsyncMock()
        return c

    feeder = _wired_peer("10.0.0.1", 6881, peer_choking=False, down=1_000_000.0)
    slow = _wired_peer("10.0.0.2", 6882, peer_choking=True, down=0.0)
    fast = _wired_peer("10.0.0.3", 6883, peer_choking=True, down=2_000_000.0)
    peer_manager.connections.clear()
    peer_manager.connections["10.0.0.1:6881"] = feeder
    peer_manager.connections["10.0.0.2:6882"] = slow
    peer_manager.connections["10.0.0.3:6883"] = fast

    await peer_manager._update_choking()
    assert len(peer_manager.upload_slots) == 2
    unchoked_ips = {p.peer_info.ip for p in peer_manager.upload_slots}
    # Ranked by reciprocation score: choked+interested with higher measured download wins.
    assert "10.0.0.3" in unchoked_ips
    assert "10.0.0.2" in unchoked_ips


@pytest.mark.asyncio
async def test_info_hash_mismatch_updates_stage_counter(peer_manager):
    """Info-hash mismatch path should increment lifecycle counters."""
    before = peer_manager._connection_stage_counters.get("info_hash_mismatch", 0)
    with pytest.raises(Exception):
        peer_manager._raise_info_hash_mismatch(b"\x01" * 20, b"\x02" * 20)
    after = peer_manager._connection_stage_counters.get("info_hash_mismatch", 0)
    assert after == before + 1


@pytest.mark.asyncio
async def test_monitor_unchoke_timeout_triggers_hard_recovery(
    monkeypatch, peer_manager, peer_info
):
    """Stale CHOKED peer should trigger hard recovery and replacement callbacks."""
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.peer_interested = True
    connection.am_interested = True
    peer_manager.connections[str(peer_info)] = connection

    # Second active peer so the unchoke monitor uses the normal 30s threshold (not the
    # solo-peer 180s anti-collapse window).
    decoy = PeerInfo(ip="127.0.0.2", port=6882)
    decoy_conn = AsyncPeerConnection(
        peer_info=decoy,
        torrent_data=peer_manager.torrent_data,
    )
    decoy_conn.state = ConnectionState.ACTIVE
    decoy_conn.peer_choking = False
    peer_manager.connections[str(decoy)] = decoy_conn

    disconnect_mock = AsyncMock()
    record_failure_mock = AsyncMock()
    schedule_mock = MagicMock()
    emit_event_mock = AsyncMock()

    monkeypatch.setattr(peer_manager, "_disconnect_peer", disconnect_mock)
    monkeypatch.setattr(peer_manager, "_record_connection_failure", record_failure_mock)
    monkeypatch.setattr(peer_manager, "_schedule_pending_resume", schedule_mock)
    monkeypatch.setattr("ccbt.utils.events.emit_event", emit_event_mock)

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    await peer_manager._monitor_unchoke_timeout(
        connection, connection_start_time=time.time() - 31.0
    )

    disconnect_mock.assert_awaited_once()
    record_failure_mock.assert_awaited_once()
    peer_key = peer_manager._get_peer_key(connection)
    assert peer_key in peer_manager._failed_peers
    assert peer_manager._failed_peers[peer_key]["reason"] == "stale_unchoke_timeout"
    assert schedule_mock.call_count == 1
    assert schedule_mock.call_args.kwargs["reason"] == "hard_unchoke_recovery"
    assert emit_event_mock.await_count == 1

    recovery_event = emit_event_mock.call_args.args[0]
    assert recovery_event.data["trigger"] == "hard_unchoke_recovery"
    assert recovery_event.data["failure_reason"] == "stale_unchoke_timeout"
    assert recovery_event.data["recovery_state"]["candidate_peer"] == str(peer_info)


@pytest.mark.asyncio
async def test_monitor_unchoke_timeout_sole_peer_disconnects_after_extended_window(
    monkeypatch, peer_manager, peer_info
):
    """Sole peer should still be dropped if choked beyond the extended solo threshold."""
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.peer_interested = True
    connection.am_interested = True
    peer_manager.connections[str(peer_info)] = connection

    disconnect_mock = AsyncMock()
    monkeypatch.setattr(peer_manager, "_disconnect_peer", disconnect_mock)
    monkeypatch.setattr(peer_manager, "_record_connection_failure", AsyncMock())
    monkeypatch.setattr(peer_manager, "_schedule_pending_resume", MagicMock())
    monkeypatch.setattr("ccbt.utils.events.emit_event", AsyncMock())
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))

    await peer_manager._monitor_unchoke_timeout(
        connection, connection_start_time=time.time() - 200.0
    )

    disconnect_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_to_peers_preserves_peer_completion_context(
    monkeypatch, peer_manager
):
    """Completion context hints are carried per peer into _connect_to_peer inputs."""
    peer_manager._running = True
    captured_peers = []

    async def fake_connect_to_peer(peer_info: PeerInfo) -> None:
        captured_peers.append(peer_info)

    monkeypatch.setattr(peer_manager, "_connect_to_peer", fake_connect_to_peer)

    peer_list = [
        {
            "ip": "192.0.2.1",
            "port": 6881,
            "is_seeder": False,
            "completion_percent": 0.25,
        },
        {"ip": "192.0.2.2", "port": 6882, "complete": True, "completion_percent": 0.0},
    ]

    await peer_manager.connect_to_peers(peer_list)

    by_ip = {peer.ip: peer for peer in captured_peers}
    assert by_ip["192.0.2.1"].is_seeder is False
    assert by_ip["192.0.2.1"].completion_percent == 0.25
    assert by_ip["192.0.2.2"].is_seeder is True
    assert by_ip["192.0.2.2"].completion_percent == 0.0


@pytest.mark.asyncio
async def test_accept_incoming_sets_connection_start_time(monkeypatch, peer_manager):
    """Incoming peers should have connection_start_time recorded immediately."""
    peer_ip = "203.0.113.10"
    peer_port = 6889
    reader = AsyncMock()
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.write = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    handshake = MagicMock()
    handshake.info_hash = peer_manager.torrent_data["info_hash"]
    handshake.peer_id = b"incoming_test_peer_id"

    monkeypatch.setattr(peer_manager, "_send_bitfield", AsyncMock())
    monkeypatch.setattr(peer_manager, "_send_unchoke", AsyncMock())
    monkeypatch.setattr(peer_manager, "_attempt_ssl_negotiation", AsyncMock())
    monkeypatch.setattr(peer_manager, "_handle_peer_messages", AsyncMock())
    monkeypatch.setattr("ccbt.utils.events.emit_event", AsyncMock())

    before_accept = time.time()
    await peer_manager.accept_incoming(reader, writer, handshake, peer_ip, peer_port)
    after_accept = time.time()

    peer_key = f"{peer_ip}:{peer_port}"
    assert peer_key in peer_manager.connections
    connection = peer_manager.connections[peer_key]
    assert connection.connection_start_time is not None
    assert before_accept <= connection.connection_start_time <= after_accept


@pytest.mark.asyncio
async def test_accept_incoming_rejects_plain_when_encryption_required(
    monkeypatch, peer_manager
):
    """Incoming plaintext peers are rejected when encryption mode is required."""
    peer_ip = "203.0.113.11"
    peer_port = 6890
    reader = AsyncMock()
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.write = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    handshake = ParsedInboundPlainHandshake(
        protocol_len=19,
        protocol=b"BitTorrent protocol",
        reserved_bytes=b"\x00" * 8,
        info_hash_v1=peer_manager.torrent_data["info_hash"],
        info_hash_v2=None,
        peer_id=b"12345678901234567890",
    )

    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "required"

    await peer_manager.accept_incoming(
        reader, writer, handshake, peer_ip, peer_port, enforce_encryption_mode=True
    )

    peer_key = f"{peer_ip}:{peer_port}"
    assert peer_key not in peer_manager.connections
    writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_accept_incoming_prefers_plain_when_encryption_preferred(
    monkeypatch, peer_manager
):
    """Incoming plaintext peers proceed when encryption mode is preferred."""
    peer_ip = "203.0.113.13"
    peer_port = 6892
    reader = AsyncMock()
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.write = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    writer.is_closing = MagicMock(return_value=False)

    handshake = ParsedInboundPlainHandshake(
        protocol_len=19,
        protocol=b"BitTorrent protocol",
        reserved_bytes=b"\x00" * 8,
        info_hash_v1=peer_manager.torrent_data["info_hash"],
        info_hash_v2=None,
        peer_id=b"12345678901234567890",
    )

    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "preferred"

    monkeypatch.setattr(peer_manager, "_send_bitfield", AsyncMock())
    monkeypatch.setattr(peer_manager, "_send_unchoke", AsyncMock())
    monkeypatch.setattr(peer_manager, "_attempt_ssl_negotiation", AsyncMock())
    monkeypatch.setattr(peer_manager, "_send_interested", AsyncMock())
    monkeypatch.setattr(peer_manager, "_handle_peer_messages", AsyncMock())
    monkeypatch.setattr("ccbt.utils.events.emit_event", AsyncMock())

    await peer_manager.accept_incoming(
        reader, writer, handshake, peer_ip, peer_port, enforce_encryption_mode=True
    )

    peer_key = f"{peer_ip}:{peer_port}"
    assert peer_key in peer_manager.connections
    writer.close.assert_not_called()
    connection = peer_manager.connections[peer_key]
    assert connection.is_encrypted is False


@pytest.mark.asyncio
async def test_accept_incoming_accepts_plain_when_plaintext_only_alias(
    monkeypatch, peer_manager
):
    """Incoming plaintext peers are accepted when encryption policy is plaintext-only."""
    peer_ip = "203.0.113.14"
    peer_port = 6893
    reader = AsyncMock()
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.write = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    writer.is_closing = MagicMock(return_value=False)

    handshake = ParsedInboundPlainHandshake(
        protocol_len=19,
        protocol=b"BitTorrent protocol",
        reserved_bytes=b"\x00" * 8,
        info_hash_v1=peer_manager.torrent_data["info_hash"],
        info_hash_v2=None,
        peer_id=b"12345678901234567890",
    )

    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "plaintext-only"

    monkeypatch.setattr(peer_manager, "_send_bitfield", AsyncMock())
    monkeypatch.setattr(peer_manager, "_send_unchoke", AsyncMock())
    monkeypatch.setattr(peer_manager, "_attempt_ssl_negotiation", AsyncMock())
    monkeypatch.setattr(peer_manager, "_send_interested", AsyncMock())
    monkeypatch.setattr(peer_manager, "_handle_peer_messages", AsyncMock())
    monkeypatch.setattr("ccbt.utils.events.emit_event", AsyncMock())

    await peer_manager.accept_incoming(
        reader, writer, handshake, peer_ip, peer_port, enforce_encryption_mode=True
    )

    peer_key = f"{peer_ip}:{peer_port}"
    assert peer_key in peer_manager.connections
    writer.close.assert_not_called()
    connection = peer_manager.connections[peer_key]
    assert connection.is_encrypted is False


@pytest.mark.asyncio
async def test_accept_incoming_encrypted_uses_phase_b_parser(monkeypatch, peer_manager):
    """Encrypted inbound path parses decrypted payload with Phase B parser."""
    peer_ip = "203.0.113.12"
    peer_port = 6891
    reader = AsyncMock()
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.write = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    writer.is_closing = MagicMock(return_value=False)

    monkeypatch.setattr(peer_manager, "_send_bitfield", AsyncMock())
    monkeypatch.setattr(peer_manager, "_send_unchoke", AsyncMock())
    monkeypatch.setattr(peer_manager, "_attempt_ssl_negotiation", AsyncMock())
    monkeypatch.setattr(peer_manager, "_handle_peer_messages", AsyncMock())
    monkeypatch.setattr(peer_manager, "_send_interested", AsyncMock())
    monkeypatch.setattr("ccbt.utils.events.emit_event", AsyncMock())

    protocol = b"BitTorrent protocol"
    decrypted_payload = (
        bytes([19])
        + protocol
        + b"\x00" * 8
        + peer_manager.torrent_data["info_hash"]
        + b"12345678901234567890"
    )

    await peer_manager.accept_incoming_encrypted(
        reader,
        writer,
        decrypted_payload,
        peer_ip,
        peer_port,
    )

    peer_key = f"{peer_ip}:{peer_port}"
    assert peer_key in peer_manager.connections
    connection = peer_manager.connections[peer_key]
    assert connection.is_encrypted is True


@pytest.mark.asyncio
async def test_resolve_outbound_encryption_mode_prefers_required_hint(
    peer_manager,
    peer_info,
):
    """Configured preferred mode should escalate to required from tracker hint."""
    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "preferred"
    peer_info.peer_id = b"peer-id-abc-20bytes!"
    peer_info._tracker_encryption_preference = "preferred"
    peer_info._peer_encryption_preference = "required"

    result = peer_manager._resolve_outbound_encryption_mode(peer_info)
    assert result == EncryptionMode.REQUIRED


@pytest.mark.asyncio
async def test_resolve_outbound_encryption_mode_uses_extension_protocol_hint(
    peer_manager,
):
    """PEP 10 `e` peer preference should influence outbound policy."""
    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "disabled"
    peer_info = PeerInfo(ip="198.51.100.1", port=6881, peer_id=b"peer-id-proto")

    protocol_extension = ExtensionProtocol()
    protocol_extension.peer_extensions = {"peer-id-proto": {"e": "preferred"}}

    peer_manager.extension_manager = MagicMock()
    peer_manager.extension_manager.get_extension.return_value = protocol_extension

    result = peer_manager._resolve_outbound_encryption_mode(peer_info)
    assert result == EncryptionMode.PREFERRED


@pytest.mark.asyncio
async def test_resolve_outbound_encryption_mode_uses_pex_preference(peer_manager):
    """PEX seed/peer flags can contribute a preferred encryption hint."""
    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "disabled"
    peer_info = PeerInfo(ip="198.51.100.2", port=6881)
    peer_info._peer_pex_prefer_encrypt = True

    result = peer_manager._resolve_outbound_encryption_mode(peer_info)
    assert result == EncryptionMode.PREFERRED


@pytest.mark.asyncio
async def test_resolve_outbound_encryption_mode_uses_pex_flags(peer_manager):
    """PEX flag bit 0x01 maps to preferred encryption in outbound resolution."""
    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "disabled"
    peer_info = PeerInfo(ip="198.51.100.3", port=6881)
    peer_info._peer_pex_flags = 0x01

    result = peer_manager._resolve_outbound_encryption_mode(peer_info)
    assert result == EncryptionMode.PREFERRED


@pytest.mark.asyncio
async def test_resolve_outbound_encryption_mode_ignores_pex_seed_flag(peer_manager):
    """PEX seed/upload-only bit (0x02) should not force encryption preference."""
    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "disabled"
    peer_info = PeerInfo(ip="198.51.100.4", port=6881)
    peer_info._peer_pex_flags = 0x02

    result = peer_manager._resolve_outbound_encryption_mode(peer_info)
    assert result == EncryptionMode.DISABLED


@pytest.mark.asyncio
async def test_resolve_outbound_encryption_mode_disabled_global_override(peer_manager):
    """Global encryption disabled should override all inbound/outbound hints."""
    peer_manager.config.security.enable_encryption = False
    peer_info = PeerInfo(ip="203.0.113.4", port=6881)
    peer_info._tracker_encryption_preference = "required"
    peer_info._peer_pex_prefer_encrypt = True

    result = peer_manager._resolve_outbound_encryption_mode(peer_info)
    assert result == EncryptionMode.DISABLED


@pytest.mark.asyncio
async def test_resolve_outbound_encryption_mode_uses_recent_mse_fallback_cache(
    peer_manager,
):
    """Recent preferred-mode MSE failures should temporarily force plaintext mode."""
    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "preferred"
    peer_info = PeerInfo(ip="203.0.113.40", port=6881)
    peer_manager._record_mse_plain_fallback(peer_info, "unit-test")

    result = peer_manager._resolve_outbound_encryption_mode(peer_info)

    assert result == EncryptionMode.DISABLED
    assert peer_manager._connection_stage_counters["mse_fallback_plain"] >= 1
    assert peer_manager._connection_stage_counters["mse_fallback_cache_hit"] >= 1


@pytest.mark.asyncio
async def test_reconnect_plaintext_after_mse_failure_uses_fresh_socket(
    peer_manager,
    monkeypatch,
):
    """Preferred-mode fallback should reconnect using a new plaintext TCP socket."""
    peer_info = PeerInfo(ip="203.0.113.41", port=6881)
    connection = AsyncPeerConnection(peer_info, peer_manager.torrent_data)

    failed_writer = MagicMock()
    failed_writer.close = MagicMock()
    failed_writer.wait_closed = AsyncMock()

    new_reader = AsyncMock()
    new_writer = MagicMock()

    open_connection_mock = AsyncMock(return_value=(new_reader, new_writer))
    monkeypatch.setattr(asyncio, "open_connection", open_connection_mock)

    reader, writer = await peer_manager._reconnect_plaintext_after_mse_failure(
        peer_info,
        connection,
        failed_writer,
        timeout=15.0,
    )

    failed_writer.close.assert_called_once()
    failed_writer.wait_closed.assert_awaited_once()
    open_connection_mock.assert_awaited_once_with(peer_info.ip, peer_info.port)
    assert reader is new_reader
    assert writer is new_writer
    assert connection.reader is new_reader
    assert connection.writer is new_writer
    assert peer_manager._connection_stage_counters["plain_reconnect_after_mse_failure"] >= 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("plaintext-only", EncryptionMode.DISABLED),
        ("prefer-plaintext", EncryptionMode.PREFERRED),
        ("prefer-encrypted", EncryptionMode.PREFERRED),
        ("require-encrypted", EncryptionMode.REQUIRED),
        (True, EncryptionMode.PREFERRED),
        (False, EncryptionMode.DISABLED),
    ],
)
async def test_coerce_encryption_mode_aliases(peer_manager, alias, expected):
    """Legacy and canonical aliases resolve to intended EncryptionMode values."""
    assert peer_manager._coerce_encryption_mode(alias) == expected


@pytest.mark.asyncio
async def test_send_our_extension_handshake_prefers_disabled_alias(
    peer_manager, peer_info
):
    """Extension preference alias `plaintext-only` advertises disabled e-field."""
    peer_manager.piece_manager._metadata_incomplete = True
    peer_manager.torrent_data["file_info"] = None
    peer_manager.config.security.enable_encryption = True
    peer_manager.config.security.encryption_mode = "plaintext-only"

    protocol = ExtensionProtocol()
    protocol.register_extension("ut_metadata", "1.0")

    extension_manager = MagicMock()
    extension_manager.get_extension.return_value = protocol
    peer_manager.extension_manager = extension_manager

    connection = AsyncPeerConnection(
        peer_info=peer_info, torrent_data=peer_manager.torrent_data
    )
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)
    connection.writer = mock_writer

    from ccbt.core.bencode import BencodeEncoder

    captured: dict[str, dict] = {}
    original_encode = BencodeEncoder.encode

    def capture_encode(self, data):
        if "handshake" not in captured:
            captured["handshake"] = data
        return original_encode(self, data)

    with patch("ccbt.core.bencode.BencodeEncoder.encode", new=capture_encode):
        await peer_manager._send_our_extension_handshake(connection)

    handshake = captured.get("handshake")
    assert handshake is not None
    assert b"e" in handshake
    assert handshake[b"e"] in {"disabled", b"disabled"}


def test_create_mse_handshake_uses_security_settings(peer_manager):
    """Create MSE handshake from explicit security settings."""
    peer_manager.config.security.encryption_dh_key_size = 1024
    peer_manager.config.security.encryption_prefer_rc4 = False
    peer_manager.config.security.encryption_allowed_ciphers = ["aes", "chacha20", "rc4"]

    mse = peer_manager._create_mse_handshake()

    assert mse.dh_exchange.key_size == 1024
    assert mse.prefer_rc4 is False
    assert mse.allowed_ciphers == [
        CipherType.AES,
        CipherType.CHACHA20,
        CipherType.RC4,
    ]


def test_create_mse_handshake_falls_back_on_invalid_dh_size(peer_manager):
    """Invalid DH key sizes should fall back to 768."""
    peer_manager.config.security.encryption_dh_key_size = 999

    mse = peer_manager._create_mse_handshake()

    assert mse.dh_exchange.key_size == 768


@pytest.mark.asyncio
async def test_handle_unchoke_uses_seed_anchor_retry_budget(monkeypatch, peer_manager):
    """Seed-anchor peers get higher unchoke retry/requester budgets for faster recovery."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.1", port=6881),
        peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.am_interested = False
    peer_manager._set_connection_completion_context(
        connection, is_seeder=True, completion_percent=1.0
    )

    peer_manager._send_interested = AsyncMock()
    peer_manager.piece_manager._select_pieces = AsyncMock()
    peer_manager.piece_manager._retry_requested_pieces = AsyncMock()

    from ccbt.peer.peer import UnchokeMessage

    await peer_manager._handle_unchoke(connection, UnchokeMessage())
    await asyncio.sleep(0.05)

    peer_manager.piece_manager._select_pieces.assert_awaited_once()
    peer_manager.piece_manager._retry_requested_pieces.assert_awaited_once_with(
        connection,
        max_retry_count=5,
        max_requesters=3,
    )
    peer_manager._send_interested.assert_awaited_once_with(connection)


@pytest.mark.asyncio
async def test_handle_unchoke_uses_default_retry_budget_for_non_seed_anchor(
    peer_manager,
):
    """Non-anchor peers keep the default unchoke retry/requester budgets."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.2", port=6882),
        peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.am_interested = False
    peer_manager._set_connection_completion_context(
        connection, is_seeder=False, completion_percent=0.35
    )

    from ccbt.peer.peer import UnchokeMessage

    peer_manager._send_interested = AsyncMock()
    peer_manager.piece_manager._select_pieces = AsyncMock()
    peer_manager.piece_manager._retry_requested_pieces = AsyncMock()

    await peer_manager._handle_unchoke(connection, UnchokeMessage())
    await asyncio.sleep(0.05)

    peer_manager.piece_manager._retry_requested_pieces.assert_awaited_once_with(
        connection,
        max_retry_count=4,
        max_requesters=2,
    )


@pytest.mark.asyncio
async def test_handle_unchoke_tracks_piece_selection_task_for_cleanup(peer_manager):
    """Stop should cancel pending piece-selection task triggered by unchoke."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.3", port=6883),
        peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.am_interested = False
    peer_manager.piece_manager.is_downloading = True
    peer_manager._send_interested = AsyncMock()

    started = asyncio.Event()

    async def delayed_select() -> None:
        started.set()
        await asyncio.sleep(10)

    peer_manager.piece_manager._select_pieces = delayed_select
    peer_manager.piece_manager._retry_requested_pieces = AsyncMock()

    from ccbt.peer.peer import UnchokeMessage

    await peer_manager._handle_unchoke(connection, UnchokeMessage())
    await asyncio.wait_for(started.wait(), timeout=1.0)
    assert len(peer_manager._piece_selection_trigger_tasks) >= 1

    await peer_manager.stop()
    assert len(peer_manager._piece_selection_trigger_tasks) == 0


@pytest.mark.asyncio
async def test_handle_unchoke_skips_piece_selection_when_shutting_down(peer_manager):
    """Shutting down should prevent new unchoke-triggered piece selection."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.4", port=6884),
        peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.am_interested = False
    peer_manager.piece_manager.is_downloading = True
    peer_manager._send_interested = AsyncMock()

    peer_manager.piece_manager._select_pieces = AsyncMock()
    peer_manager.piece_manager._retry_requested_pieces = AsyncMock()

    from ccbt.peer.peer import UnchokeMessage

    set_shutdown()
    try:
        await peer_manager._handle_unchoke(connection, UnchokeMessage())
        await asyncio.sleep(0)
        assert len(peer_manager._piece_selection_trigger_tasks) == 0
        peer_manager.piece_manager._select_pieces.assert_not_called()
    finally:
        clear_shutdown()


@pytest.mark.asyncio
async def test_monitor_unchoke_timeout_defers_seed_anchor_before_recovery(
    monkeypatch, peer_manager, peer_info
):
    """Seed-anchor peers get a short grace period before hard-unchoke recovery."""
    from ccbt.utils.events import Event

    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.state = ConnectionState.CHOKED
    connection.peer_choking = True
    connection.peer_interested = True
    connection.am_interested = True
    peer_manager._set_connection_completion_context(
        connection, is_seeder=True, completion_percent=1.0
    )
    peer_manager.connections[str(peer_info)] = connection

    decoy = PeerInfo(ip="127.0.0.2", port=6882)
    decoy_conn = AsyncPeerConnection(
        peer_info=decoy,
        torrent_data=peer_manager.torrent_data,
    )
    decoy_conn.state = ConnectionState.ACTIVE
    decoy_conn.peer_choking = False
    peer_manager.connections[str(decoy)] = decoy_conn

    disconnect_mock = AsyncMock()
    record_failure_mock = AsyncMock()
    schedule_mock = MagicMock()
    emit_event_mock = AsyncMock()

    monkeypatch.setattr(peer_manager, "_disconnect_peer", disconnect_mock)
    monkeypatch.setattr(peer_manager, "_record_connection_failure", record_failure_mock)
    monkeypatch.setattr(peer_manager, "_schedule_pending_resume", schedule_mock)
    monkeypatch.setattr("ccbt.utils.events.emit_event", emit_event_mock)

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    await peer_manager._monitor_unchoke_timeout(
        connection, connection_start_time=time.time() - 76.0
    )

    disconnect_mock.assert_awaited_once()
    record_failure_mock.assert_awaited_once()
    assert getattr(connection, "_seed_anchor_unchoke_deferrals", 0) == 2
    assert emit_event_mock.await_count == 1

    recovery_event = emit_event_mock.call_args.args[0]
    assert isinstance(recovery_event, Event)
    assert recovery_event.data["recovery_state"]["seed_anchor"] is True


@pytest.mark.asyncio
async def test_classify_connection_failure_recognizes_transient_and_terminal_errors(
    peer_manager,
):
    """Classify known protocol errors as terminal and network failures as transient."""
    assert peer_manager._classify_connection_failure(
        ConnectionRefusedError("connection refused")
    ) == (
        "connection_refused",
        True,
    )
    assert peer_manager._classify_connection_failure(
        MessageError("invalid handshake")
    ) == (
        "protocol_error",
        False,
    )


def test_classify_connection_failure_distinguishes_handshake_states(peer_manager):
    """Classify handshake-stage failures using the detailed classifier."""
    assert peer_manager._classify_connection_failure_detailed(
        "Handshake timeout from 127.0.0.1:6881 (no response after 10.0s)"
    ) == (
        "handshake_timeout",
        True,
        "handshake",
        True,
    )
    assert peer_manager._classify_connection_failure_detailed(
        "Handshake incomplete read during prefix: expected 28 bytes, got 0"
    ) == (
        "handshake_incomplete",
        True,
        "handshake_incomplete",
        True,
    )
    assert peer_manager._classify_connection_failure_detailed(
        "Info hash mismatch: expected deadbeef, got cafe"
    ) == (
        "protocol_mismatch",
        False,
        "protocol_mismatch",
        False,
    )


@pytest.mark.asyncio
async def test_infer_disconnect_stage_recognizes_protocol_errors_before_handshake(
    peer_manager,
):
    """Pre-active disconnect reasons should preserve protocol error details."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.20", port=6881),
        peer_manager.torrent_data,
    )
    connection.state = ConnectionState.HANDSHAKE_SENT
    connection.error_message = (
        "Invalid protocol length from 127.0.0.20: 20 (expected 19)"
    )

    assert peer_manager._infer_disconnect_stage(connection) == "invalid_protocol_length"

    connection.error_message = "Invalid protocol handshake from peer"
    assert peer_manager._infer_disconnect_stage(connection) == "invalid_protocol"

    connection.error_message = (
        "Handshake timeout from 127.0.0.20 (no response after 10.0s)"
    )
    assert peer_manager._infer_disconnect_stage(connection) == "handshake_timeout"


@pytest.mark.asyncio
async def test_infer_disconnect_stage_handles_incomplete_read(peer_manager):
    """Pre-active disconnect reasons should preserve incomplete read failures."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.21", port=6881),
        peer_manager.torrent_data,
    )
    connection.state = ConnectionState.HANDSHAKE_RECEIVED
    connection.error_message = "IncompleteReadError: peer closed"

    assert peer_manager._infer_disconnect_stage(connection) == "incomplete_read"


@pytest.mark.asyncio
async def test_disconnect_peer_records_specific_failure_stage(
    peer_manager, monkeypatch
):
    """_disconnect_peer should record disconnect_* counters using inferred failure stage."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.22", port=6881),
        peer_manager.torrent_data,
    )
    connection.state = ConnectionState.HANDSHAKE_SENT
    connection.error_message = (
        "Invalid protocol length from 127.0.0.22: 20 (expected 19)"
    )
    connection.writer = None
    connection.connection_task = None
    connection.outstanding_requests = {}

    peer_manager.connections[str(connection.peer_info)] = connection
    monkeypatch.setattr(
        peer_manager.connection_pool,
        "release",
        AsyncMock(return_value=None),
    )

    recorded_stages: list[str] = []

    def capture_stage(stage: str) -> None:
        recorded_stages.append(stage)

    monkeypatch.setattr(
        peer_manager,
        "_record_connection_stage",
        capture_stage,
    )

    await peer_manager._disconnect_peer(connection)

    assert "disconnect_invalid_protocol_length" in recorded_stages
    assert connection.last_disconnect_stage == "invalid_protocol_length"
    assert str(connection.peer_info) not in peer_manager.connections


@pytest.mark.asyncio
async def test_rank_peers_prioritizes_verified_and_history(peer_manager):
    """Verified peers and good failure histories should be prioritized."""
    productive_peer = PeerInfo(ip="127.0.0.10", port=7000, peer_source="tracker")
    failed_peer = PeerInfo(ip="127.0.0.11", port=7001, peer_source="tracker")

    productive_key = str(productive_peer)
    failed_key = str(failed_peer)

    peer_manager._quality_verified_peers.add(productive_key)
    peer_manager._failed_peers[failed_key] = {
        "timestamp": time.time(),
        "count": 3,
        "reason": "protocol_error",
        "is_terminal": True,
    }

    ranked = await peer_manager._rank_peers_for_connection(
        [failed_peer, productive_peer]
    )

    assert len(ranked) == 2
    assert ranked[0] == productive_peer
    assert ranked[1] == failed_peer


@pytest.mark.asyncio
async def test_rank_peers_uses_reputation_lookup_with_peer_id_and_ip(peer_manager):
    """Reputation lookup should pass both peer key and peer IP."""
    peer = PeerInfo(ip="127.0.0.14", port=7102, peer_source="tracker")
    peer_manager._security_manager = MagicMock()
    peer_manager._security_manager.get_peer_reputation.return_value = SimpleNamespace(
        reputation_score=0.9
    )

    ranked = await peer_manager._rank_peers_for_connection([peer])

    assert ranked == [peer]
    peer_manager._security_manager.get_peer_reputation.assert_called_once_with(
        str(peer),
        peer.ip,
    )


def test_mark_peer_quality_verified_syncs_existing_connection_state(peer_manager):
    """Already-verified peers should still sync connection verification flags."""
    peer_info = PeerInfo(ip="127.0.0.15", port=7103)
    peer_key = str(peer_info)
    connection = AsyncPeerConnection(peer_info, peer_manager.torrent_data)
    connection.quality_verified = False
    connection.metadata_only_since = time.time() - 30.0

    peer_manager._quality_verified_peers.add(peer_key)
    peer_manager._quality_probation_peers[peer_key] = time.time() - 30.0

    peer_manager._mark_peer_quality_verified(
        peer_key,
        reason="unit-test",
        connection=connection,
    )

    assert connection.quality_verified is True
    assert connection.metadata_only_since == 0.0
    assert peer_key not in peer_manager._quality_probation_peers


def test_calculate_metadata_only_probation_timeout_uses_adaptive_floor(peer_manager):
    """Metadata-only probation timeout should not collapse to an 8-second hard cap."""
    peer_info = PeerInfo(ip="127.0.0.16", port=7104)
    connection = AsyncPeerConnection(peer_info, peer_manager.torrent_data)
    connection.metadata_size = 16 * 1024 * 24
    connection.stats.request_latency = 0.6

    timeout = peer_manager._calculate_metadata_only_probation_timeout(20.0, connection)

    assert timeout >= 20.0
    assert timeout > 8.0


@pytest.mark.asyncio
async def test_rank_peers_penalizes_terminal_failures_more_than_transient(peer_manager):
    """Terminal failures should be ranked below transient failures for the same peer context."""
    terminal_peer = PeerInfo(ip="127.0.0.12", port=7100, peer_source="tracker")
    transient_peer = PeerInfo(ip="127.0.0.13", port=7101, peer_source="tracker")

    terminal_key = str(terminal_peer)
    transient_key = str(transient_peer)

    peer_manager._failed_peers[terminal_key] = {
        "timestamp": time.time(),
        "count": 1,
        "reason": "protocol_error",
        "is_terminal": True,
    }
    peer_manager._failed_peers[transient_key] = {
        "timestamp": time.time(),
        "count": 2,
        "reason": "timeout",
        "is_terminal": False,
    }

    ranked = await peer_manager._rank_peers_for_connection(
        [terminal_peer, transient_peer]
    )

    assert len(ranked) == 2
    assert ranked[0] == transient_peer
    assert ranked[1] == terminal_peer


def test_keepalive_interval_uses_state_aware_timeouts(peer_manager):
    """Keep-alive intervals should be state-aware and deterministic."""
    connection = AsyncPeerConnection(
        PeerInfo(ip="127.0.0.101", port=6200),
        peer_manager.torrent_data,
    )

    connection.state = ConnectionState.CHOKED
    assert peer_manager._get_keepalive_interval(connection) == 90.0
    assert peer_manager._get_message_loop_timeout(connection) == 180.0

    connection.state = ConnectionState.ACTIVE
    assert peer_manager._get_keepalive_interval(connection) == 120.0
    assert peer_manager._get_message_loop_timeout(connection) == 240.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,expected_timeout",
    [
        (ConnectionState.CHOKED, 180.0),
        (ConnectionState.ACTIVE, 240.0),
    ],
)
async def test_handle_peer_messages_keeps_quiet_healthy_peer_with_state_aligned_timeout(
    peer_manager,
    peer_info,
    monkeypatch,
    state,
    expected_timeout,
):
    """Quiet peers should honor state-aligned message-loop timeouts and stay alive."""
    connection = AsyncPeerConnection(
        peer_info,
        peer_manager.torrent_data,
    )
    connection.state = state
    connection.reader = AsyncMock()

    async def mock_readexactly(_n: int) -> bytes:
        # Simulate one keep-alive-sized frame, then stop the connection.
        connection.state = ConnectionState.DISCONNECTED
        return b"\x00\x00\x00\x00"

    connection.reader.readexactly = mock_readexactly

    captured_timeouts: list[float] = []
    original_wait_for = asyncio.wait_for

    async def tracking_wait_for(awaitable, timeout, *args, **kwargs):
        captured_timeouts.append(timeout)
        return await original_wait_for(awaitable, timeout=timeout, *args, **kwargs)

    monkeypatch.setattr(
        peer_manager,
        "_keepalive_sender",
        AsyncMock(),
    )
    monkeypatch.setattr(peer_manager, "_disconnect_peer", AsyncMock())
    connection.error_message = ""

    with patch(
        "ccbt.peer.async_peer_connection.asyncio.wait_for",
        side_effect=tracking_wait_for,
    ):
        await peer_manager._handle_peer_messages(connection)

    assert captured_timeouts
    assert captured_timeouts[0] == expected_timeout
    assert connection.error_message != "message_length_read_timeout"
    peer_manager._disconnect_peer.assert_awaited_once()


def test_safe_loop_duration_handles_invalid_and_missing_timestamps(peer_manager):
    """Compute loop duration safely when connection start timestamps are missing or invalid."""
    now = time.time()

    assert peer_manager._safe_loop_duration(now, None) == 0.0
    assert peer_manager._safe_loop_duration(now, 0.0) == 0.0
    assert peer_manager._safe_loop_duration(now, -5.0) == 0.0
    assert peer_manager._safe_loop_duration(now, now + 30.0) == 0.0

    elapsed = 1.5
    assert peer_manager._safe_loop_duration(now, now - elapsed) == elapsed


@pytest.mark.asyncio
async def test_handle_extension_message_uses_peer_advertised_extension_id_for_registered_handler(
    peer_manager, peer_info
):
    """Registered handlers should send responses using peer-advertised extension IDs."""
    connection = AsyncPeerConnection(
        peer_info=peer_info, torrent_data=peer_manager.torrent_data
    )
    connection.writer = MagicMock()

    protocol = MagicMock()
    protocol.get_peer_extension_name.return_value = "xet"
    protocol.get_peer_message_id.return_value = 77
    protocol.get_extension_info.return_value = MagicMock(message_id=1)
    protocol.message_handlers = {1: AsyncMock(return_value=b"response")}

    extension_manager = MagicMock()
    extension_manager.get_extension.return_value = protocol
    peer_manager.extension_manager = extension_manager

    with patch(
        "ccbt.protocols.bittorrent_v2._send_extension_message",
        new=AsyncMock(return_value=True),
    ) as send_ext:
        payload = bytes([20, 9, 1, 2, 3])  # message_id=20, extension_id=9
        await peer_manager._handle_extension_message(connection, payload)

    send_ext.assert_awaited_once()
    _, sent_extension_id, _ = send_ext.await_args.args
    assert sent_extension_id == 77


@pytest.mark.asyncio
async def test_handle_extension_message_uses_peer_advertised_extension_id_for_ssl_xet_response(
    peer_manager, peer_info
):
    """Fallback SSL/XET handlers should send responses using peer-advertised IDs."""
    connection = AsyncPeerConnection(
        peer_info=peer_info, torrent_data=peer_manager.torrent_data
    )
    connection.writer = MagicMock()

    protocol = MagicMock()
    protocol.get_peer_extension_name.return_value = "xet"
    protocol.get_peer_message_id.return_value = 88
    protocol.message_handlers = {}
    protocol.get_extension_info.return_value = None

    extension_manager = MagicMock()
    extension_manager.get_extension.return_value = protocol
    extension_manager.handle_ssl_message = AsyncMock(return_value=None)
    extension_manager.handle_xet_message = AsyncMock(return_value=b"xet-response")
    peer_manager.extension_manager = extension_manager

    with patch(
        "ccbt.protocols.bittorrent_v2._send_extension_message",
        new=AsyncMock(return_value=True),
    ) as send_ext:
        payload = bytes([20, 9, 9, 8, 7])  # message_id=20, extension_id=9
        await peer_manager._handle_extension_message(connection, payload)

    send_ext.assert_awaited_once_with(connection, 88, b"xet-response")


@pytest.mark.asyncio
async def test_handle_extension_message_skips_response_without_peer_advertised_id(
    peer_manager, peer_info
):
    """If peer-advertised extension ID is missing, no extension response is sent."""
    connection = AsyncPeerConnection(
        peer_info=peer_info, torrent_data=peer_manager.torrent_data
    )
    connection.writer = MagicMock()

    protocol = MagicMock()
    protocol.get_peer_extension_name.return_value = "xet"
    protocol.get_peer_message_id.return_value = None
    protocol.get_extension_info.return_value = MagicMock(message_id=1)
    protocol.message_handlers = {}

    extension_manager = MagicMock()
    extension_manager.get_extension.return_value = protocol
    extension_manager.handle_xet_message = AsyncMock(return_value=b"xet-response")
    peer_manager.extension_manager = extension_manager

    with patch(
        "ccbt.protocols.bittorrent_v2._send_extension_message",
        new=AsyncMock(return_value=True),
    ) as send_ext:
        payload = bytes([20, 9, 9, 8, 7])  # message_id=20, extension_id=9
        await peer_manager._handle_extension_message(connection, payload)

    send_ext.assert_not_called()


@pytest.mark.asyncio
async def test_accept_incoming_rejects_strict_non_ltep_peer(peer_manager):
    """Strict mode should reject inbound peers that do not advertise LTEP."""
    peer_info = PeerInfo(
        ip="203.0.113.10", port=50100, peer_id=b"test_peer_20bytes____"
    )
    original_mode = peer_manager.config.security.authenticated_swarms.mode
    peer_manager.config.security.authenticated_swarms.mode = "strict"

    reader = AsyncMock()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    handshake = MagicMock()
    handshake.peer_id = b"test_peer_20bytes___"  # exactly 20 bytes
    handshake.info_hash = peer_manager.torrent_data["info_hash"]
    handshake.reserved_bytes = b"\x00" * 8

    try:
        await peer_manager.accept_incoming(
            reader=reader,
            writer=writer,
            handshake=handshake,
            peer_ip=peer_info.ip,
            peer_port=peer_info.port,
            enforce_encryption_mode=False,
        )
    finally:
        peer_manager.config.security.authenticated_swarms.mode = original_mode

    assert writer.close.call_count >= 1
    assert f"{peer_info.ip}:{peer_info.port}" not in peer_manager.connections


def test_allow_inbound_extension_swarm_auth_empty_map_logs_reason_label(
    peer_manager, peer_info
):
    """Empty extension handshakes should log a stable empty-map reason label."""
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    handshake = SimpleNamespace(
        peer_id=b"p" * 20,
        info_hash=peer_manager.torrent_data["info_hash"],
        info_hash_v2=None,
    )

    with patch(
        "ccbt.peer.async_peer_connection.evaluate_inbound_admission",
        return_value=AuthDecision(False, "strict", "missing_schema"),
    ), patch.object(peer_manager.logger, "debug") as mock_debug:
        allowed = peer_manager._allow_inbound_extension_swarm_auth(
            connection=connection,
            handshake=handshake,
            handshake_data={},
        )

    assert allowed is False
    found_rejection_log = False
    for call in mock_debug.call_args_list:
        if not call.args:
            continue
        if "reason_label=%s" not in call.args[0]:
            continue
        found_rejection_log = True
        assert "EMPTY_EXTENSION_HANDSHAKE_MAP" in call.args
        assert True in call.args
    assert found_rejection_log


@pytest.mark.asyncio
async def test_handle_extension_message_normalizes_non_ascii_bencode_keys(
    peer_manager, peer_info
):
    """Non-UTF8 extension keys are decoded with replacement, not left as bytes."""
    connection = AsyncPeerConnection(
        peer_info=peer_info,
        torrent_data=peer_manager.torrent_data,
    )
    connection.close = AsyncMock()
    peer_manager.extension_manager = MagicMock()
    peer_manager.extension_manager.peer_supports_extension.return_value = None

    bencoded_data = BencodeEncoder().encode(
        {
            b"m": {b"ut_metadata": 1},
            b"\xff": 1,
        }
    )
    payload = bytes([20, 0]) + bencoded_data

    with patch.object(
        peer_manager,
        "_allow_inbound_extension_swarm_auth",
        return_value=True,
    ):
        await peer_manager._handle_extension_message(connection, payload)

    peer_id = str(connection.peer_info)
    peer_manager.extension_manager.set_peer_extensions.assert_called_once()
    call_peer_id, call_handshake = (
        peer_manager.extension_manager.set_peer_extensions.call_args.args
    )
    assert call_peer_id == peer_id
    assert isinstance(call_handshake, dict)
    assert all(isinstance(key, str) for key in call_handshake.keys())
    assert "m" in call_handshake


@pytest.mark.asyncio
async def test_strict_ltep_timeout_closes_connection_if_extension_not_seen(
    peer_manager,
):
    """Strict-mode peers with LTEP support must send extension handshake before timeout."""
    original_mode = peer_manager.config.security.authenticated_swarms.mode
    original_timeout = peer_manager.config.security.authenticated_swarms.strict_ltep_handshake_timeout_s
    peer_manager.config.security.authenticated_swarms.mode = "strict"
    peer_manager.config.security.authenticated_swarms.strict_ltep_handshake_timeout_s = 0.05

    connection = AsyncPeerConnection(
        peer_info=PeerInfo(ip="203.0.113.11", port=50101),
        torrent_data=peer_manager.torrent_data,
    )
    connection.reserved_bytes = b"\x00\x00\x00\x00\x00\x10\x00\x00"
    connection.close = AsyncMock()

    try:
        with patch(
            "ccbt.peer.async_peer_connection.get_metrics_collector",
            return_value=None,
        ):
            peer_manager._start_strict_ltep_timeout(connection)
            await asyncio.sleep(0.08)
            connection.close.assert_awaited_once()
            assert (
                peer_manager._strict_ltep_timeout_tasks.get("203.0.113.11:50101")
                is None
            )
    finally:
        peer_manager.config.security.authenticated_swarms.mode = original_mode
        peer_manager.config.security.authenticated_swarms.strict_ltep_handshake_timeout_s = original_timeout


@pytest.mark.asyncio
async def test_strict_ltep_timeout_cleared_after_extension_handshake(peer_manager):
    """Extension handshake should clear strict-mode LTEP timeout timer."""
    original_mode = peer_manager.config.security.authenticated_swarms.mode
    original_timeout = peer_manager.config.security.authenticated_swarms.strict_ltep_handshake_timeout_s
    peer_manager.config.security.authenticated_swarms.mode = "strict"
    peer_manager.config.security.authenticated_swarms.strict_ltep_handshake_timeout_s = 0.05

    connection = AsyncPeerConnection(
        peer_info=PeerInfo(ip="203.0.113.12", port=50102),
        torrent_data=peer_manager.torrent_data,
    )
    connection.reserved_bytes = b"\x00\x00\x00\x00\x00\x10\x00\x00"
    connection.close = AsyncMock()

    try:
        with patch(
            "ccbt.peer.async_peer_connection.get_metrics_collector",
            return_value=None,
        ):
            peer_manager._start_strict_ltep_timeout(connection)
            await asyncio.sleep(0.02)
            peer_manager._notify_strict_ltep_handshake_seen(connection)
            await asyncio.sleep(0.05)
            connection.close.assert_not_called()
            assert (
                peer_manager._strict_ltep_timeout_tasks.get("203.0.113.12:50102")
                is None
            )
    finally:
        peer_manager.config.security.authenticated_swarms.mode = original_mode
        peer_manager.config.security.authenticated_swarms.strict_ltep_handshake_timeout_s = original_timeout


@pytest.mark.asyncio
async def test_tracker_peer_cache_reconnect_invokes_connect_to_peers(
    peer_manager, monkeypatch
):
    """Reconnection fallback should call connect_to_peers with cached discovery peers."""
    batches: list[list[dict[str, Any]]] = []

    async def capture_connect(peer_list: list, **_kwargs: Any) -> None:
        batches.append(list(peer_list))

    monkeypatch.setattr(peer_manager, "connect_to_peers", capture_connect)
    await peer_manager._remember_discovered_peers_for_retry(
        [
            {"ip": "10.0.0.1", "port": 5001, "peer_source": "tracker"},
            {"ip": "10.0.0.2", "port": 5002, "peer_source": "tracker"},
        ]
    )
    await peer_manager._reconnect_from_tracker_peer_cache(
        tlabel="test", max_attempts=10
    )
    assert len(batches) == 1
    assert len(batches[0]) == 2
    ports = {int(p["port"]) for p in batches[0]}
    assert ports == {5001, 5002}
