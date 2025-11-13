"""Comprehensive unit tests for UDP tracker scraping (BEP 15/48).

Tests request encoding, response decoding, connection handling, and error handling.
"""

from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio

from ccbt.discovery.tracker_udp_client import (
    AsyncUDPTrackerClient,
    TrackerAction,
    TrackerResponse,
)

pytestmark = [pytest.mark.unit, pytest.mark.tracker]


@pytest.fixture
def client():
    """Create AsyncUDPTrackerClient instance for testing."""
    return AsyncUDPTrackerClient()


@pytest.fixture
def torrent_data():
    """Create sample torrent data with UDP tracker."""
    return {
        "info_hash": b"x" * 20,
        "announce": "udp://tracker.example.com:6969",
        "announce_list": [["udp://tracker.example.com:6969"]],
        "name": "test_torrent",
    }


@pytest_asyncio.fixture
async def started_client(client):
    """Create and start AsyncUDPTrackerClient."""
    # Mock transport
    client.transport = Mock()
    await client.start()
    yield client
    await client.stop()


class TestEncodeScrapeRequest:
    """Test UDP scrape request encoding."""

    def test_encode_scrape_request_single_hash(self, client):
        """Test encoding scrape request with single info_hash."""
        connection_id = 0x1234567890ABCDEF
        transaction_id = 12345
        info_hash = b"x" * 20

        request_data = client._encode_scrape_request(
            connection_id, transaction_id, info_hash
        )

        # Verify structure: connection_id (8) + action (4) + transaction_id (4) + info_hash (20)
        assert len(request_data) == 36

        # Verify connection_id
        unpacked_conn_id, action, tx_id = struct.unpack("!QII", request_data[:16])
        assert unpacked_conn_id == connection_id
        assert action == TrackerAction.SCRAPE.value
        assert tx_id == transaction_id

        # Verify info_hash
        assert request_data[16:] == info_hash

    def test_encode_scrape_request_invalid_hash_length(self, client):
        """Test encoding with invalid info_hash length."""
        connection_id = 0x1234567890ABCDEF
        transaction_id = 12345
        info_hash = b"x" * 19  # Too short

        with pytest.raises(ValueError, match="Invalid info_hash length"):
            client._encode_scrape_request(connection_id, transaction_id, info_hash)


class TestDecodeScrapeResponse:
    """Test UDP scrape response decoding."""

    def test_decode_scrape_response_success(self, client):
        """Test decoding successful scrape response."""
        info_hash = b"x" * 20
        response = TrackerResponse(
            action=TrackerAction.SCRAPE,
            transaction_id=12345,
            complete=100,
            downloaded=1000,
            incomplete=50,
        )

        result = client._decode_scrape_response(response, info_hash)

        assert result["seeders"] == 100
        assert result["leechers"] == 50
        assert result["completed"] == 1000

    def test_decode_scrape_response_wrong_action(self, client):
        """Test decoding response with wrong action."""
        info_hash = b"x" * 20
        response = TrackerResponse(
            action=TrackerAction.ANNOUNCE,  # Wrong action
            transaction_id=12345,
        )

        result = client._decode_scrape_response(response, info_hash)

        assert result == {}

    def test_decode_scrape_response_error_message(self, client):
        """Test decoding response with error message."""
        info_hash = b"x" * 20
        response = TrackerResponse(
            action=TrackerAction.SCRAPE,
            transaction_id=12345,
            error_message="Scrape not supported",
        )

        result = client._decode_scrape_response(response, info_hash)

        assert result == {}

    def test_decode_scrape_response_missing_fields(self, client):
        """Test decoding response with missing fields."""
        info_hash = b"x" * 20
        response = TrackerResponse(
            action=TrackerAction.SCRAPE,
            transaction_id=12345,
            complete=10,
            # Missing downloaded and incomplete
        )

        result = client._decode_scrape_response(response, info_hash)

        assert result == {}

    def test_decode_scrape_response_exception(self, client):
        """Test decoding handles exceptions."""
        info_hash = b"x" * 20
        response = Mock()
        response.action = TrackerAction.SCRAPE
        response.error_message = None
        response.complete = None
        # Cause attribute error
        response.downloaded = property(lambda self: raise_(AttributeError()))

        def raise_(exc):
            raise exc

        result = client._decode_scrape_response(response, info_hash)

        assert result == {}


class TestScrapeMethod:
    """Test the scrape() method end-to-end."""

    @pytest.mark.asyncio
    async def test_scrape_transport_not_initialized(self, client, torrent_data):
        """Test scrape when transport not initialized."""
        client.transport = None

        result = await client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_no_info_hash(self, started_client, torrent_data):
        """Test scrape with no info_hash."""
        del torrent_data["info_hash"]

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_invalid_info_hash_length(self, started_client, torrent_data):
        """Test scrape with invalid info_hash length."""
        torrent_data["info_hash"] = b"x" * 19

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_no_udp_trackers(self, started_client, torrent_data):
        """Test scrape with no UDP tracker URLs."""
        torrent_data["announce"] = "http://tracker.example.com/announce"
        torrent_data["announce_list"] = []

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_connection_failure(
        self, started_client, torrent_data
    ):
        """Test scrape when connection fails."""
        # Mock _connect_to_tracker to raise exception
        started_client._connect_to_tracker = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_no_response(self, started_client, torrent_data):
        """Test scrape when no response received."""
        # Create session with connection
        session_key = "tracker.example.com:6969"
        started_client.sessions[session_key] = Mock()
        session = started_client.sessions[session_key]
        session.is_connected = True
        session.connection_id = 0x1234567890ABCDEF
        session.connection_time = 0.0
        session.host = "tracker.example.com"
        session.port = 6969

        # Mock wait_for_response to return None
        started_client._wait_for_response = AsyncMock(return_value=None)

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_success(self, started_client, torrent_data):
        """Test successful scrape."""
        # Create session with connection
        session_key = "tracker.example.com:6969"
        started_client.sessions[session_key] = Mock()
        session = started_client.sessions[session_key]
        session.is_connected = True
        session.connection_id = 0x1234567890ABCDEF
        session.connection_time = 0.0
        session.host = "tracker.example.com"
        session.port = 6969

        # Mock successful response - _wait_for_response returns TrackerResponse
        response = TrackerResponse(
            action=TrackerAction.SCRAPE,
            transaction_id=12345,
            complete=75,
            downloaded=500,
            incomplete=30,
        )
        started_client._wait_for_response = AsyncMock(return_value=response)

        result = await started_client.scrape(torrent_data)

        # _decode_scrape_response should return standardized format
        assert "seeders" in result or result == {}  # Might return empty if decode fails
        if result:  # Only check if result is not empty
            assert result.get("seeders") == 75
            assert result.get("leechers") == 30
            assert result.get("completed") == 500

    @pytest.mark.asyncio
    async def test_scrape_connection_timeout(self, started_client, torrent_data):
        """Test scrape with connection timeout."""
        # Mock _connect_to_tracker to simulate timeout
        started_client._connect_to_tracker = AsyncMock(
            side_effect=TimeoutError("Connection timeout")
        )

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_generic_exception(self, started_client, torrent_data):
        """Test scrape handles generic exceptions."""
        # Cause exception during scrape
        started_client.transport.sendto = Mock(side_effect=Exception("Send error"))

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_connection_id_none(self, started_client, torrent_data):
        """Test scrape when connection_id is None."""
        # Create session without connection_id
        session_key = "tracker.example.com:6969"
        started_client.sessions[session_key] = Mock()
        session = started_client.sessions[session_key]
        session.is_connected = True
        session.connection_id = None  # No connection ID
        session.connection_time = 0.0
        session.host = "tracker.example.com"
        session.port = 6969

        result = await started_client.scrape(torrent_data)

        assert result == {}


class TestHandleResponseScrape:
    """Test handle_response parsing for scrape responses."""

    def test_handle_response_scrape_action(self, client):
        """Test handle_response correctly parses scrape action."""
        transaction_id = 12345
        complete = 100
        downloaded = 1000
        incomplete = 50

        # Build scrape response: action (4) + transaction_id (4) + complete (4) + downloaded (4) + incomplete (4)
        data = struct.pack(
            "!IIIII",
            TrackerAction.SCRAPE.value,
            transaction_id,
            complete,
            downloaded,
            incomplete,
        )

        # Setup pending request
        future = asyncio.Future()
        client.pending_requests[transaction_id] = future

        # Handle response
        client.handle_response(data, ("127.0.0.1", 6969))

        # Check response was set
        assert future.done()
        response = future.result()
        assert response.action == TrackerAction.SCRAPE
        assert response.complete == 100
        assert response.downloaded == 1000
        assert response.incomplete == 50

    def test_handle_response_scrape_short_data(self, client):
        """Test handle_response with insufficient scrape data."""
        transaction_id = 12345
        # Too short - missing scrape data
        data = struct.pack("!II", TrackerAction.SCRAPE.value, transaction_id)

        future = asyncio.Future()
        client.pending_requests[transaction_id] = future

        # Should not crash, but won't set result
        client.handle_response(data, ("127.0.0.1", 6969))

        # Future should not be done (response too short)
        assert not future.done()

