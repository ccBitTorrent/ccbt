"""Integration tests for IPC server config endpoints.

Tests the new IPC server endpoints for per-torrent configuration:
- POST /api/v1/torrents/{info_hash}/options
- GET /api/v1/torrents/{info_hash}/options/{key}
- GET /api/v1/torrents/{info_hash}/config
- DELETE /api/v1/torrents/{info_hash}/options
- DELETE /api/v1/torrents/{info_hash}/options/{key}
- POST /api/v1/torrents/{info_hash}/checkpoint
"""

from __future__ import annotations

import aiohttp
import pytest
import pytest_asyncio

from ccbt.daemon.ipc_protocol import API_BASE_PATH, API_KEY_HEADER
from ccbt.daemon.ipc_server import IPCServer
from ccbt.session.session import AsyncSessionManager

pytestmark = [pytest.mark.integration, pytest.mark.daemon]


@pytest_asyncio.fixture(scope="function")
async def mock_session_manager(monkeypatch):
    """Create a mock session manager with lightweight initialization."""
    from unittest.mock import patch

    # Disable NAT auto port mapping to prevent 60s wait
    monkeypatch.setenv("CCBT_NAT_AUTO_MAP_PORTS", "0")
    # Disable DHT to prevent network initialization
    monkeypatch.setenv("CCBT_ENABLE_DHT", "0")

    session = AsyncSessionManager()

    # Patch config to disable heavy components
    session.config.network.enable_tcp = False
    session.config.network.enable_utp = False
    session.config.nat.auto_map_ports = False
    session.config.discovery.enable_dht = False
    session.config.network.listen_port = 0

    # Mock heavy initialization methods to prevent hangs
    session._make_nat_manager = lambda: None  # type: ignore[method-assign]
    session._make_tcp_server = lambda: None  # type: ignore[method-assign]

    # Mock DHT client start to avoid network initialization
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
    # Get actual port
    actual_port = server.port
    yield server, api_key, actual_port
    await server.stop()


@pytest.fixture
async def test_torrent(mock_session_manager):
    """Create a test torrent in the session manager."""
    from ccbt.session.session import AsyncTorrentSession

    torrent_data = {
        "name": "test_torrent",
        "info_hash": b"x" * 20,
        "pieces_info": {
            "num_pieces": 1,
            "piece_length": 16384,
            "piece_hashes": [b"x" * 20],
            "total_length": 16384,
        },
        "file_info": {"total_length": 16384},
    }

    info_hash_bytes = b"x" * 20
    info_hash_hex = (b"x" * 20).hex()

    # Create session
    session = AsyncTorrentSession(
        torrent_data, output_dir=".", session_manager=mock_session_manager
    )
    async with mock_session_manager.lock:
        mock_session_manager.torrents[info_hash_bytes] = session

    return info_hash_hex, session


class TestIPCServerConfigEndpoints:
    """Test IPC server config endpoints."""

    @pytest.mark.asyncio
    async def test_set_torrent_option_success(self, ipc_server, test_torrent):
        """Test POST /api/v1/torrents/{info_hash}/options successfully."""
        server, api_key, port = ipc_server
        info_hash_hex, _ = test_torrent

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/options"
        headers = {API_KEY_HEADER: api_key}
        payload = {"key": "piece_selection", "value": "sequential"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["success"] is True
                assert data["key"] == "piece_selection"
                assert data["value"] == "sequential"

    @pytest.mark.asyncio
    async def test_set_torrent_option_missing_key(self, ipc_server, test_torrent):
        """Test POST /api/v1/torrents/{info_hash}/options with missing key."""
        server, api_key, port = ipc_server
        info_hash_hex, _ = test_torrent

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/options"
        headers = {API_KEY_HEADER: api_key}
        payload = {"value": "sequential"}  # Missing key

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                assert resp.status == 400
                data = await resp.json()
                assert data["code"] == "MISSING_PARAMETER"

    @pytest.mark.asyncio
    async def test_set_torrent_option_torrent_not_found(self, ipc_server):
        """Test POST /api/v1/torrents/{info_hash}/options with non-existent torrent."""
        server, api_key, port = ipc_server
        info_hash_hex = "a" * 40

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/options"
        headers = {API_KEY_HEADER: api_key}
        payload = {"key": "piece_selection", "value": "sequential"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                assert resp.status == 400
                data = await resp.json()
                assert data["code"] == "SET_OPTION_FAILED"

    @pytest.mark.asyncio
    async def test_get_torrent_option_success(self, ipc_server, test_torrent):
        """Test GET /api/v1/torrents/{info_hash}/options/{key} successfully."""
        server, api_key, port = ipc_server
        info_hash_hex, session = test_torrent

        # Set option first
        session.options["piece_selection"] = "sequential"

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/options/piece_selection"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session_client:
            async with session_client.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["key"] == "piece_selection"
                assert data["value"] == "sequential"

    @pytest.mark.asyncio
    async def test_get_torrent_option_not_set(self, ipc_server, test_torrent):
        """Test GET /api/v1/torrents/{info_hash}/options/{key} for unset option."""
        server, api_key, port = ipc_server
        info_hash_hex, _ = test_torrent

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/options/nonexistent_key"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["key"] == "nonexistent_key"
                assert data["value"] is None

    @pytest.mark.asyncio
    async def test_get_torrent_option_torrent_not_found(self, ipc_server):
        """Test GET /api/v1/torrents/{info_hash}/options/{key} with non-existent torrent."""
        server, api_key, port = ipc_server
        info_hash_hex = "a" * 40

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/options/piece_selection"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 404
                data = await resp.json()
                assert data["code"] == "GET_OPTION_FAILED"

    @pytest.mark.asyncio
    async def test_get_torrent_config_success(self, ipc_server, test_torrent):
        """Test GET /api/v1/torrents/{info_hash}/config successfully."""
        server, api_key, port = ipc_server
        info_hash_hex, session = test_torrent

        # Set options and rate limits
        session.options["piece_selection"] = "sequential"
        session.options["streaming_mode"] = True

        info_hash_bytes = bytes.fromhex(info_hash_hex)
        server.session_manager._per_torrent_limits[info_hash_bytes] = {
            "down_kib": 100,
            "up_kib": 50,
        }

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/config"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session_client:
            async with session_client.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "options" in data
                assert "rate_limits" in data
                assert data["options"]["piece_selection"] == "sequential"
                assert data["options"]["streaming_mode"] is True
                assert data["rate_limits"]["down_kib"] == 100
                assert data["rate_limits"]["up_kib"] == 50

    @pytest.mark.asyncio
    async def test_get_torrent_config_empty(self, ipc_server, test_torrent):
        """Test GET /api/v1/torrents/{info_hash}/config for torrent with no options."""
        server, api_key, port = ipc_server
        info_hash_hex, _ = test_torrent

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/config"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["options"] == {}
                assert data["rate_limits"] == {}

    @pytest.mark.asyncio
    async def test_get_torrent_config_torrent_not_found(self, ipc_server):
        """Test GET /api/v1/torrents/{info_hash}/config with non-existent torrent."""
        server, api_key, port = ipc_server
        info_hash_hex = "a" * 40

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/config"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                assert resp.status == 404
                data = await resp.json()
                assert data["code"] == "GET_CONFIG_FAILED"

    @pytest.mark.asyncio
    async def test_reset_torrent_options_all_success(self, ipc_server, test_torrent):
        """Test DELETE /api/v1/torrents/{info_hash}/options successfully."""
        server, api_key, port = ipc_server
        info_hash_hex, session = test_torrent

        # Set options first
        session.options["piece_selection"] = "sequential"
        session.options["streaming_mode"] = True

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/options"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session_client:
            async with session_client.delete(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["success"] is True
                assert data["key"] is None

    @pytest.mark.asyncio
    async def test_reset_torrent_options_single_key_success(
        self, ipc_server, test_torrent
    ):
        """Test DELETE /api/v1/torrents/{info_hash}/options/{key} successfully."""
        server, api_key, port = ipc_server
        info_hash_hex, session = test_torrent

        # Set options first
        session.options["piece_selection"] = "sequential"
        session.options["streaming_mode"] = True

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/options/piece_selection"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session_client:
            async with session_client.delete(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["success"] is True
                assert data["key"] == "piece_selection"

    @pytest.mark.asyncio
    async def test_reset_torrent_options_torrent_not_found(self, ipc_server):
        """Test DELETE /api/v1/torrents/{info_hash}/options with non-existent torrent."""
        server, api_key, port = ipc_server
        info_hash_hex = "a" * 40

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/options"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as resp:
                assert resp.status == 400
                data = await resp.json()
                assert data["code"] == "RESET_OPTIONS_FAILED"

    @pytest.mark.asyncio
    async def test_save_torrent_checkpoint_success(self, ipc_server, test_torrent):
        """Test POST /api/v1/torrents/{info_hash}/checkpoint successfully."""
        server, api_key, port = ipc_server
        info_hash_hex, session = test_torrent

        # Mock checkpoint controller
        from unittest.mock import AsyncMock

        session.checkpoint_controller = AsyncMock()
        session.checkpoint_controller.save_checkpoint_state = AsyncMock()

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/checkpoint"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session_client:
            async with session_client.post(url, headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["success"] is True
                assert data["saved"] is True

    @pytest.mark.asyncio
    async def test_save_torrent_checkpoint_torrent_not_found(self, ipc_server):
        """Test POST /api/v1/torrents/{info_hash}/checkpoint with non-existent torrent."""
        server, api_key, port = ipc_server
        info_hash_hex = "a" * 40

        url = f"http://127.0.0.1:{port}{API_BASE_PATH}/torrents/{info_hash_hex}/checkpoint"
        headers = {API_KEY_HEADER: api_key}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as resp:
                assert resp.status == 400
                data = await resp.json()
                assert data["code"] == "SAVE_CHECKPOINT_FAILED"

    @pytest.mark.asyncio
    async def test_config_endpoints_require_auth(self, ipc_server, test_torrent):
        """Test that config endpoints require authentication."""
        server, api_key, port = ipc_server
        info_hash_hex, _ = test_torrent
        base_url = f"http://127.0.0.1:{port}{API_BASE_PATH}"

        endpoints = [
            ("POST", f"{base_url}/torrents/{info_hash_hex}/options", {"key": "test", "value": "test"}),
            ("GET", f"{base_url}/torrents/{info_hash_hex}/options/test", None),
            ("GET", f"{base_url}/torrents/{info_hash_hex}/config", None),
            ("DELETE", f"{base_url}/torrents/{info_hash_hex}/options", None),
            ("POST", f"{base_url}/torrents/{info_hash_hex}/checkpoint", None),
        ]

        async with aiohttp.ClientSession() as session:
            for method, url, payload in endpoints:
                # Without API key
                if method == "GET" or method == "DELETE":
                    async with session.request(method, url) as resp:
                        assert resp.status == 401
                else:
                    async with session.request(method, url, json=payload) as resp:
                        assert resp.status == 401

                # With invalid API key
                headers = {API_KEY_HEADER: "invalid-key"}
                if method == "GET" or method == "DELETE":
                    async with session.request(method, url, headers=headers) as resp:
                        assert resp.status == 401
                else:
                    async with session.request(
                        method, url, json=payload, headers=headers
                    ) as resp:
                        assert resp.status == 401

