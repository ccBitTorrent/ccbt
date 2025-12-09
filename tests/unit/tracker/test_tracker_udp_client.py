from __future__ import annotations

import asyncio
import socket
import struct
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.tracker]

from ccbt.discovery.tracker_udp_client import (
    AsyncUDPTrackerClient,
    TrackerAction,
    TrackerEvent,
    TrackerResponse,
    TrackerSession,
)


class TestTrackerEnums:
    """Test tracker enums."""

    def test_tracker_action_enum(self):
        """Test TrackerAction enum values."""
        assert TrackerAction.CONNECT.value == 0
        assert TrackerAction.ANNOUNCE.value == 1
        assert TrackerAction.SCRAPE.value == 2
        assert TrackerAction.ERROR.value == 3

    def test_tracker_event_enum(self):
        """Test TrackerEvent enum values."""
        assert TrackerEvent.NONE.value == 0
        assert TrackerEvent.COMPLETED.value == 1
        assert TrackerEvent.STARTED.value == 2
        assert TrackerEvent.STOPPED.value == 3


class TestTrackerResponse:
    """Test TrackerResponse dataclass."""

    def test_connect_response(self):
        """Test CONNECT response."""
        response = TrackerResponse(
            action=TrackerAction.CONNECT,
            transaction_id=12345,
            connection_id=0x1234567890ABCDEF,
        )
        assert response.action == TrackerAction.CONNECT
        assert response.connection_id == 0x1234567890ABCDEF

    def test_announce_response(self):
        """Test ANNOUNCE response."""
        response = TrackerResponse(
            action=TrackerAction.ANNOUNCE,
            transaction_id=12345,
            interval=1800,
            leechers=5,
            seeders=10,
            peers=[{"ip": "192.168.1.1", "port": 6881}],
        )
        assert response.interval == 1800
        assert response.leechers == 5
        assert response.seeders == 10
        assert len(response.peers) == 1

    def test_error_response(self):
        """Test ERROR response."""
        response = TrackerResponse(
            action=TrackerAction.ERROR,
            transaction_id=12345,
            error_message="Invalid request",
        )
        assert response.error_message == "Invalid request"


class TestTrackerSession:
    """Test TrackerSession dataclass."""

    def test_session_creation(self):
        """Test creating a tracker session."""
        session = TrackerSession(
            url="udp://tracker.example.com:6969",
            host="tracker.example.com",
            port=6969,
        )
        assert session.url == "udp://tracker.example.com:6969"
        assert session.host == "tracker.example.com"
        assert session.port == 6969
        assert not session.is_connected
        assert session.retry_count == 0


class TestAsyncUDPTrackerClientBasics:
    """Test basic UDP tracker client functionality."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = AsyncUDPTrackerClient()
        assert client.our_peer_id is not None
        assert len(client.our_peer_id) == 20
        assert client.sessions == {}
        assert client.transport is None

    def test_client_initialization_with_peer_id(self):
        """Test client initialization with custom peer ID."""
        peer_id = b"\x11" * 20
        client = AsyncUDPTrackerClient(peer_id=peer_id)
        assert client.our_peer_id == peer_id

    def test_get_transaction_id(self):
        """Test transaction ID generation."""
        client = AsyncUDPTrackerClient()
        id1 = client._get_transaction_id()
        id2 = client._get_transaction_id()
        assert id2 == (id1 + 1) % 65536

    def test_parse_udp_url(self):
        """Test UDP URL parsing."""
        client = AsyncUDPTrackerClient()
        host, port = client._parse_udp_url("udp://tracker.example.com:6969")
        assert host == "tracker.example.com"
        assert port == 6969

    def test_parse_udp_url_default_port(self):
        """Test UDP URL parsing with default port."""
        client = AsyncUDPTrackerClient()
        host, port = client._parse_udp_url("udp://tracker.example.com")
        assert host == "tracker.example.com"
        assert port == 80

    def test_extract_tracker_urls_single(self):
        """Test extracting single tracker URL."""
        client = AsyncUDPTrackerClient()
        torrent_data = {"announce": "udp://tracker.example.com:6969"}
        urls = client._extract_tracker_urls(torrent_data)
        assert len(urls) == 1
        assert urls[0] == "udp://tracker.example.com:6969"

    def test_extract_tracker_urls_announce_list(self):
        """Test extracting tracker URLs from announce_list."""
        client = AsyncUDPTrackerClient()
        torrent_data = {
            "announce_list": [
                ["udp://tracker1.example.com:6969"],
                ["udp://tracker2.example.com:6969", "http://tracker3.example.com"],
            ]
        }
        urls = client._extract_tracker_urls(torrent_data)
        assert len(urls) == 2
        assert "udp://tracker1.example.com:6969" in urls
        assert "udp://tracker2.example.com:6969" in urls

    def test_extract_tracker_urls_no_udp(self):
        """Test extracting tracker URLs with no UDP trackers."""
        client = AsyncUDPTrackerClient()
        torrent_data = {"announce": "http://tracker.example.com"}
        urls = client._extract_tracker_urls(torrent_data)
        assert len(urls) == 0

    def test_extract_tracker_urls_none(self):
        """Test extracting tracker URLs when none exist."""
        client = AsyncUDPTrackerClient()
        torrent_data = {}
        urls = client._extract_tracker_urls(torrent_data)
        assert len(urls) == 0


class TestAsyncUDPTrackerClientStartStop:
    """Test UDP tracker client start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the client."""
        client = AsyncUDPTrackerClient()
        await client.start()
        assert client.transport is not None
        assert client.socket is not None

        await client.stop()
        # Transport may be closing but not None immediately on Windows
        # The important thing is that stop() doesn't crash

    @pytest.mark.asyncio
    async def test_stop_cancels_pending_requests(self):
        """Test that stop cancels pending requests."""
        client = AsyncUDPTrackerClient()
        await client.start()

        # Create a pending request
        future = asyncio.Future()
        client.pending_requests[123] = future

        await client.stop()

        # Request should be cancelled
        assert future.cancelled()


class TestAsyncUDPTrackerClientConnection:
    """Test UDP tracker connection handling."""

    @pytest.mark.asyncio
    async def test_connect_without_transport(self):
        """Test connecting without transport raises error."""
        client = AsyncUDPTrackerClient()
        session = TrackerSession("udp://tracker.example.com:6969", "tracker.example.com", 6969)

        with pytest.raises(RuntimeError):
            await client._connect_to_tracker(session)

    @pytest.mark.asyncio
    async def test_connect_timeout(self):
        """Test connection timeout handling."""
        client = AsyncUDPTrackerClient()
        await client.start()

        # Use a non-existent tracker
        session = TrackerSession(
            url="udp://127.0.0.1:65535",
            host="127.0.0.1",
            port=65535,
        )

        # Should timeout and raise
        with pytest.raises(ConnectionError):
            await client._connect_to_tracker(session)

        await client.stop()

    @pytest.mark.asyncio
    async def test_connect_invalid_response(self):
        """Test connection with invalid response."""
        client = AsyncUDPTrackerClient()
        await client.start()

        session = TrackerSession(
            url="udp://127.0.0.1:65535",
            host="127.0.0.1",
            port=65535,
        )

        # Mock response handler to return invalid response
        original_handler = client.handle_response

        def mock_handler(data, addr):
            # Send invalid response (wrong action)
            invalid_data = struct.pack("!IIQ", TrackerAction.ERROR.value, 123, 0)
            original_handler(invalid_data, addr)

        client.handle_response = mock_handler

        with pytest.raises(ConnectionError):
            await client._connect_to_tracker(session)

        await client.stop()


class TestAsyncUDPTrackerClientAnnounce:
    """Test UDP tracker announce functionality."""

    @pytest.mark.asyncio
    async def test_announce_no_trackers(self):
        """Test announce with no UDP trackers."""
        client = AsyncUDPTrackerClient()
        torrent_data = {
            "announce": "http://tracker.example.com",
            "file_info": {"total_length": 1000},
        }
        result = await client.announce(torrent_data)
        assert result == []

    @pytest.mark.asyncio
    async def test_announce_connection_failure(self):
        """Test announce with connection failure."""
        client = AsyncUDPTrackerClient()
        await client.start()

        torrent_data = {
            "announce": "udp://127.0.0.1:65535",
            "info_hash": b"\x00" * 20,
            "file_info": {"total_length": 1000},
        }

        result = await client.announce(torrent_data)
        assert result == []

        await client.stop()

    @pytest.mark.asyncio
    async def test_announce_transport_not_initialized(self):
        """Test announce fails when transport not initialized."""
        client = AsyncUDPTrackerClient()
        torrent_data = {
            "announce": "udp://tracker.example.com:6969",
            "info_hash": b"\x00" * 20,
            "file_info": {"total_length": 1000},
        }

        # Should handle gracefully
        result = await client.announce(torrent_data)
        assert result == []

    @pytest.mark.asyncio
    async def test_send_announce_reconnect_on_timeout(self):
        """Test announce reconnects when connection times out."""
        client = AsyncUDPTrackerClient()
        await client.start()

        session = TrackerSession(
            url="udp://tracker.example.com:6969",
            host="tracker.example.com",
            port=6969,
        )
        session.is_connected = True
        session.connection_time = time.time() - 70  # Old connection

        torrent_data = {
            "info_hash": b"\x00" * 20,
            "file_info": {"total_length": 1000},
        }

        # Should attempt reconnect
        result = await client._send_announce(
            session,
            torrent_data,
            uploaded=0,
            downloaded=0,
            left=1000,
            event=TrackerEvent.STARTED,
        )

        # Should return empty list due to connection failure
        assert result == []

        await client.stop()


class TestAsyncUDPTrackerClientResponseHandling:
    """Test UDP tracker response handling."""

    def test_handle_response_connect(self):
        """Test handling CONNECT response."""
        client = AsyncUDPTrackerClient()
        transaction_id = 12345
        future = asyncio.Future()
        client.pending_requests[transaction_id] = future

        # Create CONNECT response
        connection_id = 0x1234567890ABCDEF
        response_data = struct.pack("!IIQ", TrackerAction.CONNECT.value, transaction_id, connection_id)

        client.handle_response(response_data, ("127.0.0.1", 6969))

        # Should complete future
        assert future.done()
        result = future.result()
        assert result.action == TrackerAction.CONNECT
        assert result.connection_id == connection_id

    def test_handle_response_announce(self):
        """Test handling ANNOUNCE response."""
        client = AsyncUDPTrackerClient()
        transaction_id = 12345
        future = asyncio.Future()
        client.pending_requests[transaction_id] = future

        # Create ANNOUNCE response with peers
        interval = 1800
        leechers = 5
        seeders = 10
        peer1 = socket.inet_aton("192.168.1.1") + struct.pack("!H", 6881)
        peer2 = socket.inet_aton("192.168.1.2") + struct.pack("!H", 6882)
        response_data = (
            struct.pack("!IIIII", TrackerAction.ANNOUNCE.value, transaction_id, interval, leechers, seeders)
            + peer1
            + peer2
        )

        client.handle_response(response_data, ("127.0.0.1", 6969))

        assert future.done()
        result = future.result()
        assert result.action == TrackerAction.ANNOUNCE
        assert result.interval == interval
        assert result.leechers == leechers
        assert result.seeders == seeders
        assert len(result.peers) == 2
        assert result.peers[0]["ip"] == "192.168.1.1"
        assert result.peers[0]["port"] == 6881

    def test_handle_response_error(self):
        """Test handling ERROR response."""
        client = AsyncUDPTrackerClient()
        transaction_id = 12345
        future = asyncio.Future()
        client.pending_requests[transaction_id] = future

        # Create ERROR response
        error_msg = b"Invalid request"
        response_data = struct.pack("!II", TrackerAction.ERROR.value, transaction_id) + error_msg

        client.handle_response(response_data, ("127.0.0.1", 6969))

        assert future.done()
        result = future.result()
        assert result.action == TrackerAction.ERROR
        assert "Invalid request" in result.error_message

    def test_handle_response_short_packet(self):
        """Test handling short response packet."""
        client = AsyncUDPTrackerClient()
        transaction_id = 12345
        future = asyncio.Future()
        client.pending_requests[transaction_id] = future

        # Send too short packet
        response_data = b"\x00\x00\x00"
        client.handle_response(response_data, ("127.0.0.1", 6969))

        # Should not complete future
        assert not future.done()

    def test_handle_response_unknown_transaction(self):
        """Test handling response for unknown transaction."""
        client = AsyncUDPTrackerClient()
        transaction_id = 99999

        # Create response for unknown transaction
        response_data = struct.pack("!IIQ", TrackerAction.CONNECT.value, transaction_id, 0x1234)

        # Should not crash
        client.handle_response(response_data, ("127.0.0.1", 6969))

    def test_handle_response_already_done(self):
        """Test handling response for already completed request."""
        client = AsyncUDPTrackerClient()
        transaction_id = 12345
        future = asyncio.Future()
        future.set_result(TrackerResponse(TrackerAction.CONNECT, transaction_id))
        client.pending_requests[transaction_id] = future

        # Send another response
        response_data = struct.pack("!IIQ", TrackerAction.CONNECT.value, transaction_id, 0x1234)
        client.handle_response(response_data, ("127.0.0.1", 6969))

        # Should not crash or modify result

    def test_handle_response_announce_short(self):
        """Test handling ANNOUNCE response that's too short."""
        client = AsyncUDPTrackerClient()
        transaction_id = 12345
        future = asyncio.Future()
        client.pending_requests[transaction_id] = future

        # Create too short ANNOUNCE response
        response_data = struct.pack("!II", TrackerAction.ANNOUNCE.value, transaction_id)

        client.handle_response(response_data, ("127.0.0.1", 6969))

        # Should not complete future
        assert not future.done()


class TestAsyncUDPTrackerClientWaitForResponse:
    """Test waiting for tracker responses."""

    @pytest.mark.asyncio
    async def test_wait_for_response_timeout(self):
        """Test waiting for response times out."""
        client = AsyncUDPTrackerClient()
        transaction_id = 12345

        result = await client._wait_for_response(transaction_id, timeout=0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_wait_for_response_success(self):
        """Test waiting for response succeeds."""
        client = AsyncUDPTrackerClient()
        transaction_id = 12345

        # Set up response handler
        async def set_response():
            await asyncio.sleep(0.05)
            response = TrackerResponse(
                TrackerAction.CONNECT,
                transaction_id,
                connection_id=0x1234,
            )
            if transaction_id in client.pending_requests:
                client.pending_requests[transaction_id].set_result(response)

        task = asyncio.create_task(set_response())
        result = await client._wait_for_response(transaction_id, timeout=1.0)
        await task

        assert result is not None
        assert result.action == TrackerAction.CONNECT


class TestAsyncUDPTrackerClientCleanup:
    """Test UDP tracker client cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_sessions_old(self):
        """Test cleanup removes old sessions."""
        client = AsyncUDPTrackerClient()
        session = TrackerSession(
            url="udp://tracker.example.com:6969",
            host="tracker.example.com",
            port=6969,
        )
        session.last_announce = time.time() - 7200  # 2 hours ago
        client.sessions["tracker.example.com:6969"] = session

        await client._cleanup_sessions()
        assert len(client.sessions) == 0

    @pytest.mark.asyncio
    async def test_cleanup_sessions_max_retries(self):
        """Test cleanup removes sessions with max retries."""
        client = AsyncUDPTrackerClient()
        session = TrackerSession(
            url="udp://tracker.example.com:6969",
            host="tracker.example.com",
            port=6969,
        )
        session.retry_count = session.max_retries
        client.sessions["tracker.example.com:6969"] = session

        await client._cleanup_sessions()
        assert len(client.sessions) == 0

    @pytest.mark.asyncio
    async def test_cleanup_sessions_keeps_active(self):
        """Test cleanup keeps active sessions."""
        client = AsyncUDPTrackerClient()
        session = TrackerSession(
            url="udp://tracker.example.com:6969",
            host="tracker.example.com",
            port=6969,
        )
        session.last_announce = time.time() - 1800  # 30 minutes ago
        client.sessions["tracker.example.com:6969"] = session

        await client._cleanup_sessions()
        assert len(client.sessions) == 1


class TestAsyncUDPTrackerClientScrape:
    """Test UDP tracker scrape functionality."""

    @pytest.mark.asyncio
    async def test_scrape_no_info_hash(self):
        """Test scrape with no info hash."""
        client = AsyncUDPTrackerClient()
        torrent_data = {}
        result = await client.scrape(torrent_data)
        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_no_trackers(self):
        """Test scrape with no UDP trackers."""
        client = AsyncUDPTrackerClient()
        torrent_data = {"info_hash": b"\x00" * 20, "announce": "http://tracker.example.com"}
        result = await client.scrape(torrent_data)
        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_transport_not_initialized(self):
        """Test scrape fails when transport not initialized."""
        client = AsyncUDPTrackerClient()
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "announce": "udp://tracker.example.com:6969",
        }

        result = await client.scrape(torrent_data)
        assert result == {}

    def test_encode_scrape_request(self):
        """Test encoding scrape request."""
        client = AsyncUDPTrackerClient()
        connection_id = 0x41727101980  # Magic number
        transaction_id = 12345
        info_hash = b"\x00" * 20
        data = client._encode_scrape_request(connection_id, transaction_id, info_hash)
        assert len(data) == 36  # 8 (connection_id) + 4 (action) + 4 (transaction_id) + 20 (info_hash)
        conn_id, action, trans_id = struct.unpack("!QII", data[:16])
        assert conn_id == connection_id
        assert action == 2
        assert trans_id == transaction_id

    def test_decode_scrape_response(self):
        """Test decoding scrape response."""
        from ccbt.discovery.tracker_udp_client import TrackerAction, TrackerResponse

        client = AsyncUDPTrackerClient()
        # Scrape response: action(4) + transaction_id(4) + complete(4) + downloaded(4) + incomplete(4)
        complete = 10
        downloaded = 100
        incomplete = 5
        transaction_id = 12345
        info_hash = b"\x00" * 20

        response = TrackerResponse(
            action=TrackerAction.SCRAPE,
            transaction_id=transaction_id,
            complete=complete,
            downloaded=downloaded,
            incomplete=incomplete,
        )

        result = client._decode_scrape_response(response, info_hash)
        # _decode_scrape_response returns seeders, leechers, completed
        # where seeders=complete, leechers=incomplete, completed=downloaded
        assert result["seeders"] == complete
        assert result["leechers"] == incomplete
        assert result["completed"] == downloaded

    def test_decode_scrape_response_short(self):
        """Test decoding short scrape response."""
        from ccbt.discovery.tracker_udp_client import TrackerAction, TrackerResponse

        client = AsyncUDPTrackerClient()
        info_hash = b"\x00" * 20

        # Create a response with incomplete data
        response = TrackerResponse(
            action=TrackerAction.SCRAPE,
            transaction_id=12345,
            complete=None,
            downloaded=None,
            incomplete=None,
        )

        result = client._decode_scrape_response(response, info_hash)
        assert result == {}

    def test_decode_scrape_response_wrong_action(self):
        """Test decoding scrape response with wrong action."""
        from ccbt.discovery.tracker_udp_client import TrackerAction, TrackerResponse

        client = AsyncUDPTrackerClient()
        info_hash = b"\x00" * 20

        # Create response with wrong action
        response = TrackerResponse(
            action=TrackerAction.ERROR,
            transaction_id=12345,
            error_message="Test error",
        )

        result = client._decode_scrape_response(response, info_hash)
        assert result == {}


class TestAsyncUDPTrackerClientModuleFunctions:
    """Test AsyncUDPTrackerClient direct usage (singleton functions removed in refactoring)."""

    def test_create_client_directly(self):
        """Test creating AsyncUDPTrackerClient directly."""
        client = AsyncUDPTrackerClient()
        assert isinstance(client, AsyncUDPTrackerClient)
        assert client.our_peer_id is not None
        assert len(client.our_peer_id) == 20

    @pytest.mark.asyncio
    async def test_start_and_stop_client(self):
        """Test starting and stopping AsyncUDPTrackerClient."""
        client = AsyncUDPTrackerClient()
        await client.start()
        assert client.transport is not None
        await client.stop()
        # Should not crash if stop is called multiple times
        await client.stop()

    @pytest.mark.asyncio
    async def test_client_lifecycle(self):
        """Test full client lifecycle."""
        client = AsyncUDPTrackerClient()
        await client.start()
        assert client.transport is not None
        await client.stop()
        # Verify cleanup
        assert client.transport is None


    @pytest.mark.asyncio
    async def test_shutdown_udp_tracker(self):
        """Test stopping UDP tracker client (replaces removed shutdown_udp_tracker function)."""
        # Module-level functions (get_udp_tracker_client, init_udp_tracker, shutdown_udp_tracker)
        # were removed during refactoring. UDP tracker client is now managed through
        # session manager or used directly. This test verifies direct client usage.
        client = AsyncUDPTrackerClient()
        await client.start()
        assert client.transport is not None
        await client.stop()
        # Should not crash if called multiple times
        await client.stop()
        # Verify cleanup
        assert client.transport is None

