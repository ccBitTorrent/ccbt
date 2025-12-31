"""Integration tests for IPC server tracker statistics endpoint.

Tests the /api/v1/torrents/{info_hash}/trackers endpoint to ensure it correctly
retrieves and returns tracker statistics (seeds, peers, downloaders) from
TrackerSession and falls back to scrape cache when needed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration]

from ccbt.daemon.ipc_protocol import API_BASE_PATH, API_KEY_HEADER
from ccbt.daemon.ipc_server import IPCServer
from ccbt.discovery.tracker import AsyncTrackerClient, TrackerResponse, TrackerSession
from ccbt.models import ScrapeResult
from ccbt.session.session import AsyncSessionManager, AsyncTorrentSession


@pytest.fixture
async def mock_session_manager(monkeypatch):
    """Create a mock session manager with lightweight initialization."""
    # Disable NAT auto port mapping to prevent 60s wait
    monkeypatch.setenv("CCBT_NAT_AUTO_MAP_PORTS", "0")
    # Disable DHT to prevent network initialization
    monkeypatch.setenv("CCBT_ENABLE_DHT", "0")

    session = AsyncSessionManager()

    # Patch config to disable heavy components
    session.config.network.enable_tcp = False
    session.config.nat.auto_map_ports = False
    session.config.discovery.enable_dht = False

    # Mock heavy initialization methods to prevent hangs
    session._make_nat_manager = lambda: None  # type: ignore[method-assign]
    session._make_tcp_server = lambda: None  # type: ignore[method-assign]

    with patch.object(session, "_make_dht_client", return_value=None):
        await session.start()
        yield session
        await session.stop()


@pytest.fixture
async def ipc_server(mock_session_manager):
    """Create IPC server for testing."""
    api_key = "test-api-key-12345"
    server = IPCServer(
        session_manager=mock_session_manager,
        api_key=api_key,
        host="127.0.0.1",
        port=0,  # Use random port
    )
    await server.start()
    actual_port = server.port
    yield server, api_key, actual_port
    await server.stop()


@pytest.fixture
def sample_info_hash():
    """Sample info hash for testing."""
    return b"x" * 20


@pytest.fixture
def sample_info_hash_hex(sample_info_hash):
    """Sample info hash as hex string."""
    return sample_info_hash.hex()


@pytest.fixture
def mock_torrent_session(sample_info_hash):
    """Create a mock torrent session with tracker client."""
    session = MagicMock(spec=AsyncTorrentSession)
    session.torrent_data = {
        "name": "test_torrent",
        "info_hash": sample_info_hash,
        "announce": "http://tracker.example.com/announce",
        "announce_list": [["http://tracker.example.com/announce"]],
    }

    # Create tracker client with session
    tracker_client = AsyncTrackerClient()
    tracker_url = "http://tracker.example.com/announce"

    # Create tracker session with statistics
    tracker_session = TrackerSession(url=tracker_url)
    tracker_session.last_complete = 100  # 100 seeders
    tracker_session.last_incomplete = 50  # 50 leechers
    tracker_session.last_downloaded = 25  # 25 completed downloads
    tracker_session.last_announce = 1234567890.0
    tracker_session.failure_count = 0

    tracker_client.sessions[tracker_url] = tracker_session
    session.tracker = tracker_client

    return session


class TestIPCTrackerStatistics:
    """Test IPC server tracker statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_torrent_trackers_returns_statistics(
        self, ipc_server, mock_session_manager, mock_torrent_session, sample_info_hash, sample_info_hash_hex
    ):
        """Test that tracker statistics are returned from TrackerSession."""
        server, api_key, port = ipc_server

        # Add torrent session to manager
        async with mock_session_manager.lock:
            mock_session_manager.torrents[sample_info_hash] = mock_torrent_session

        # Make request
        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{sample_info_hash_hex}/trackers"
            headers = {API_KEY_HEADER: api_key}
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()

                # Verify response structure
                assert "trackers" in data
                assert "count" in data
                assert data["info_hash"] == sample_info_hash_hex

                # Verify tracker statistics
                assert len(data["trackers"]) > 0
                tracker = data["trackers"][0]
                assert tracker["url"] == "http://tracker.example.com/announce"
                assert tracker["seeds"] == 100
                assert tracker["peers"] == 50
                assert tracker["downloaders"] == 25
                assert tracker["status"] == "working"

    @pytest.mark.asyncio
    async def test_get_torrent_trackers_fallback_to_scrape_cache(
        self, ipc_server, mock_session_manager, sample_info_hash, sample_info_hash_hex
    ):
        """Test fallback to scrape cache when session statistics are unavailable."""
        server, api_key, port = ipc_server

        # Create torrent session without tracker statistics
        session = MagicMock(spec=AsyncTorrentSession)
        session.torrent_data = {
            "name": "test_torrent",
            "info_hash": sample_info_hash,
            "announce": "http://tracker.example.com/announce",
        }

        # Create tracker client with session but no statistics
        tracker_client = AsyncTrackerClient()
        tracker_url = "http://tracker.example.com/announce"
        tracker_session = TrackerSession(url=tracker_url)
        tracker_session.last_complete = None
        tracker_session.last_incomplete = None
        tracker_session.last_downloaded = None
        tracker_client.sessions[tracker_url] = tracker_session
        session.tracker = tracker_client

        # Add scrape result to cache
        scrape_result = ScrapeResult(
            info_hash=sample_info_hash,
            seeders=200,
            leechers=100,
            completed=50,
            last_scrape_time=1234567890.0,
            scrape_count=1,
        )
        async with mock_session_manager.scrape_cache_lock:
            mock_session_manager.scrape_cache[sample_info_hash] = scrape_result

        # Add torrent session to manager
        async with mock_session_manager.lock:
            mock_session_manager.torrents[sample_info_hash] = session

        # Make request
        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{sample_info_hash_hex}/trackers"
            headers = {API_KEY_HEADER: api_key}
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()

                # Verify fallback to scrape cache
                assert len(data["trackers"]) > 0
                tracker = data["trackers"][0]
                assert tracker["seeds"] == 200  # From scrape cache
                assert tracker["peers"] == 100  # From scrape cache
                assert tracker["downloaders"] == 50  # From scrape cache

    @pytest.mark.asyncio
    async def test_get_torrent_trackers_handles_missing_statistics(
        self, ipc_server, mock_session_manager, sample_info_hash, sample_info_hash_hex
    ):
        """Test that missing statistics return 0 values."""
        server, api_key, port = ipc_server

        # Create torrent session with tracker but no statistics
        session = MagicMock(spec=AsyncTorrentSession)
        session.torrent_data = {
            "name": "test_torrent",
            "info_hash": sample_info_hash,
            "announce": "http://tracker.example.com/announce",
        }

        tracker_client = AsyncTrackerClient()
        tracker_url = "http://tracker.example.com/announce"
        tracker_session = TrackerSession(url=tracker_url)
        tracker_session.last_complete = None
        tracker_session.last_incomplete = None
        tracker_session.last_downloaded = None
        tracker_client.sessions[tracker_url] = tracker_session
        session.tracker = tracker_client

        # No scrape cache entry
        async with mock_session_manager.lock:
            mock_session_manager.torrents[sample_info_hash] = session

        # Make request
        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{sample_info_hash_hex}/trackers"
            headers = {API_KEY_HEADER: api_key}
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()

                # Verify default values
                assert len(data["trackers"]) > 0
                tracker = data["trackers"][0]
                assert tracker["seeds"] == 0
                assert tracker["peers"] == 0
                assert tracker["downloaders"] == 0

    @pytest.mark.asyncio
    async def test_get_torrent_trackers_multiple_trackers(
        self, ipc_server, mock_session_manager, sample_info_hash, sample_info_hash_hex
    ):
        """Test endpoint handles multiple trackers with different statistics."""
        server, api_key, port = ipc_server

        # Create torrent session with multiple trackers
        session = MagicMock(spec=AsyncTorrentSession)
        session.torrent_data = {
            "name": "test_torrent",
            "info_hash": sample_info_hash,
            "announce": "http://tracker1.example.com/announce",
            "announce_list": [
                ["http://tracker1.example.com/announce"],
                ["http://tracker2.example.com/announce"],
            ],
        }

        tracker_client = AsyncTrackerClient()

        # Tracker 1 with statistics
        tracker1_url = "http://tracker1.example.com/announce"
        tracker1_session = TrackerSession(url=tracker1_url)
        tracker1_session.last_complete = 100
        tracker1_session.last_incomplete = 50
        tracker_client.sessions[tracker1_url] = tracker1_session

        # Tracker 2 with different statistics
        tracker2_url = "http://tracker2.example.com/announce"
        tracker2_session = TrackerSession(url=tracker2_url)
        tracker2_session.last_complete = 200
        tracker2_session.last_incomplete = 75
        tracker_client.sessions[tracker2_url] = tracker2_session

        session.tracker = tracker_client

        async with mock_session_manager.lock:
            mock_session_manager.torrents[sample_info_hash] = session

        # Make request
        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{sample_info_hash_hex}/trackers"
            headers = {API_KEY_HEADER: api_key}
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()

                # Verify both trackers are returned with their statistics
                assert data["count"] >= 2
                trackers = {t["url"]: t for t in data["trackers"]}
                assert "http://tracker1.example.com/announce" in trackers
                assert "http://tracker2.example.com/announce" in trackers

                assert trackers["http://tracker1.example.com/announce"]["seeds"] == 100
                assert trackers["http://tracker2.example.com/announce"]["seeds"] == 200

    @pytest.mark.asyncio
    async def test_get_torrent_trackers_invalid_info_hash(self, ipc_server):
        """Test endpoint handles invalid info hash format."""
        server, api_key, port = ipc_server

        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/invalid_hash/trackers"
            headers = {API_KEY_HEADER: api_key}
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 400
                data = await resp.json()
                assert data["code"] == "INVALID_INFO_HASH"

    @pytest.mark.asyncio
    async def test_get_torrent_trackers_torrent_not_found(self, ipc_server, sample_info_hash_hex):
        """Test endpoint handles torrent not found."""
        server, api_key, port = ipc_server

        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{sample_info_hash_hex}/trackers"
            headers = {API_KEY_HEADER: api_key}
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 404
                data = await resp.json()
                assert data["code"] == "TORRENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_torrent_trackers_tracker_status_working(
        self, ipc_server, mock_session_manager, mock_torrent_session, sample_info_hash, sample_info_hash_hex
    ):
        """Test tracker status is correctly set to 'working' when no failures."""
        server, api_key, port = ipc_server

        async with mock_session_manager.lock:
            mock_session_manager.torrents[sample_info_hash] = mock_torrent_session

        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{sample_info_hash_hex}/trackers"
            headers = {API_KEY_HEADER: api_key}
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()

                tracker = data["trackers"][0]
                assert tracker["status"] == "working"
                assert tracker["error"] is None

    @pytest.mark.asyncio
    async def test_get_torrent_trackers_tracker_status_error(
        self, ipc_server, mock_session_manager, sample_info_hash, sample_info_hash_hex
    ):
        """Test tracker status is correctly set to 'error' when failures exist."""
        server, api_key, port = ipc_server

        # Create session with tracker that has failures
        session = MagicMock(spec=AsyncTorrentSession)
        session.torrent_data = {
            "name": "test_torrent",
            "info_hash": sample_info_hash,
            "announce": "http://tracker.example.com/announce",
        }

        tracker_client = AsyncTrackerClient()
        tracker_url = "http://tracker.example.com/announce"
        tracker_session = TrackerSession(url=tracker_url)
        tracker_session.failure_count = 3  # Has failures
        tracker_session.last_complete = 100
        tracker_session.last_incomplete = 50
        tracker_client.sessions[tracker_url] = tracker_session
        session.tracker = tracker_client

        async with mock_session_manager.lock:
            mock_session_manager.torrents[sample_info_hash] = session

        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{sample_info_hash_hex}/trackers"
            headers = {API_KEY_HEADER: api_key}
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()

                tracker = data["trackers"][0]
                assert tracker["status"] == "error"
                assert "Failed 3 times" in tracker["error"]

