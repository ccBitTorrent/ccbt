"""Unit tests for IPFS protocol connection management."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.models import Config, IPFSConfig
from ccbt.protocols.ipfs import IPFSProtocol


@pytest.fixture
def mock_ipfs_client():
    """Create a mock IPFS client."""
    client = MagicMock()
    client.id.return_value = {"ID": "test-peer-id", "Addresses": []}
    client.close.return_value = None
    return client


@pytest.fixture
def ipfs_config():
    """Create IPFS configuration."""
    config = Config()
    config.ipfs = IPFSConfig(
        api_url="http://127.0.0.1:5001",
        enable_pinning=False,
        connection_timeout=30,
    )
    return config


@pytest.fixture
def ipfs_protocol(ipfs_config):
    """Create IPFS protocol instance."""
    protocol = IPFSProtocol()
    # Set config manually if needed
    protocol.config = ipfs_config
    if hasattr(ipfs_config, "ipfs") and ipfs_config.ipfs:
        protocol.ipfs_api_url = ipfs_config.ipfs.api_url
    return protocol


@pytest.mark.asyncio
async def test_connect_to_ipfs_network_success(ipfs_protocol, mock_ipfs_client):
    """Test successful connection to IPFS network."""
    with patch("ccbt.protocols.ipfs.ipfshttpclient.connect", return_value=mock_ipfs_client):
        await ipfs_protocol._connect_to_ipfs_network()

    assert ipfs_protocol._ipfs_connected is True
    assert ipfs_protocol._ipfs_client is not None
    assert ipfs_protocol._connection_retries == 0


@pytest.mark.asyncio
async def test_connect_to_ipfs_network_connection_error(ipfs_protocol):
    """Test connection error handling."""
    import ipfshttpclient.exceptions

    with patch(
        "ccbt.protocols.ipfs.ipfshttpclient.connect",
        side_effect=ipfshttpclient.exceptions.ConnectionError("Connection failed"),
    ):
        with pytest.raises(ConnectionError):
            await ipfs_protocol._connect_to_ipfs_network()

    assert ipfs_protocol._ipfs_connected is False
    assert ipfs_protocol._connection_retries == 1


@pytest.mark.asyncio
async def test_connect_to_ipfs_network_timeout_error(ipfs_protocol):
    """Test timeout error handling."""
    import ipfshttpclient.exceptions

    with patch(
        "ccbt.protocols.ipfs.ipfshttpclient.connect",
        side_effect=ipfshttpclient.exceptions.TimeoutError("Timeout"),
    ):
        with pytest.raises(TimeoutError):
            await ipfs_protocol._connect_to_ipfs_network()

    assert ipfs_protocol._ipfs_connected is False
    assert ipfs_protocol._connection_retries == 1


@pytest.mark.asyncio
async def test_disconnect_from_ipfs_network(ipfs_protocol, mock_ipfs_client):
    """Test disconnection from IPFS network."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    ipfs_protocol.ipfs_peers["test-peer"] = MagicMock()

    await ipfs_protocol._disconnect_from_ipfs_network()

    assert ipfs_protocol._ipfs_connected is False
    assert ipfs_protocol._ipfs_client is None
    assert len(ipfs_protocol.ipfs_peers) == 0
    mock_ipfs_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_check_ipfs_connection_healthy(ipfs_protocol, mock_ipfs_client):
    """Test IPFS connection health check when healthy."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    result = await ipfs_protocol._check_ipfs_connection()

    assert result is True
    mock_ipfs_client.id.assert_called_once()


@pytest.mark.asyncio
async def test_check_ipfs_connection_unhealthy(ipfs_protocol, mock_ipfs_client):
    """Test IPFS connection health check when unhealthy."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    mock_ipfs_client.id.side_effect = Exception("Connection failed")

    result = await ipfs_protocol._check_ipfs_connection()

    assert result is False
    assert ipfs_protocol._ipfs_connected is False


@pytest.mark.asyncio
async def test_check_ipfs_connection_not_connected(ipfs_protocol):
    """Test IPFS connection health check when not connected."""
    ipfs_protocol._ipfs_connected = False
    ipfs_protocol._ipfs_client = None

    result = await ipfs_protocol._check_ipfs_connection()

    assert result is False


@pytest.mark.asyncio
async def test_reconnect_ipfs_success(ipfs_protocol, mock_ipfs_client):
    """Test successful reconnection to IPFS."""
    ipfs_protocol._connection_retries = 1

    with patch("ccbt.protocols.ipfs.ipfshttpclient.connect", return_value=mock_ipfs_client):
        result = await ipfs_protocol._reconnect_ipfs()

    assert result is True
    assert ipfs_protocol._ipfs_connected is True
    assert ipfs_protocol._connection_retries == 0


@pytest.mark.asyncio
async def test_reconnect_ipfs_max_retries(ipfs_protocol):
    """Test reconnection failure after max retries."""
    ipfs_protocol._connection_retries = 3

    result = await ipfs_protocol._reconnect_ipfs()

    assert result is False


@pytest.mark.asyncio
async def test_parse_multiaddr_valid(ipfs_protocol):
    """Test parsing valid multiaddr."""
    # Use a valid CID format (base58 encoded, 46+ chars)
    multiaddr_str = "/ip4/127.0.0.1/tcp/4001/p2p/QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o"
    result = ipfs_protocol._parse_multiaddr(multiaddr_str)

    assert "ip" in result
    assert "port" in result
    assert result["ip"] == "127.0.0.1"
    assert result["port"] == 4001


@pytest.mark.asyncio
async def test_parse_multiaddr_invalid(ipfs_protocol):
    """Test parsing invalid multiaddr."""
    with pytest.raises(ValueError, match="Invalid multiaddr format"):
        ipfs_protocol._parse_multiaddr("invalid-address")


@pytest.mark.asyncio
async def test_validate_peer_info_valid(ipfs_protocol):
    """Test validation of valid peer info."""
    from ccbt.models import PeerInfo

    peer_info = PeerInfo(
        ip="192.168.1.1",
        port=4001,
        peer_id=b"test-peer-id-12345678",
    )

    result = ipfs_protocol._validate_peer_info(peer_info)
    assert result is True


@pytest.mark.asyncio
async def test_validate_peer_info_invalid(ipfs_protocol):
    """Test validation of invalid peer info."""
    from ccbt.models import PeerInfo

    # Missing peer_id (empty bytes)
    peer_info = PeerInfo(ip="192.168.1.1", port=4001, peer_id=b"")
    assert ipfs_protocol._validate_peer_info(peer_info) is False

    # Invalid IP (special "ipfs" marker)
    peer_info = PeerInfo(ip="ipfs", port=4001, peer_id=b"test-peer-id-12345678")
    assert ipfs_protocol._validate_peer_info(peer_info) is False

    # Port too high (but valid PeerInfo, so we bypass validation)
    # Note: PeerInfo validation limits port to 1-65535, so we test with a value that
    # passes PeerInfo validation but fails our custom validation
    # Actually, we can't test port=0 or 65536 because PeerInfo validates it
    # So we test missing peer_id and invalid IP instead


@pytest.mark.asyncio
async def test_validate_peer_id_valid(ipfs_protocol):
    """Test validation of valid peer ID."""
    peer_id = "QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o"
    assert ipfs_protocol._validate_peer_id(peer_id) is True


@pytest.mark.asyncio
async def test_validate_peer_id_invalid(ipfs_protocol):
    """Test validation of invalid peer ID."""
    # Empty
    assert ipfs_protocol._validate_peer_id("") is False

    # Too short
    assert ipfs_protocol._validate_peer_id("QmShort") is False

    # Invalid characters
    assert ipfs_protocol._validate_peer_id("QmInvalid!!!") is False

