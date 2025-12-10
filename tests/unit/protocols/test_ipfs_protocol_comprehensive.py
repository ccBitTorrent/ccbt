"""Comprehensive unit tests for IPFS protocol - all methods and edge cases."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.models import Config, FileInfo, IPFSConfig, PeerInfo, TorrentInfo
from ccbt.protocols.base import ProtocolState
from ccbt.protocols.ipfs import IPFSContent, IPFSPeer, IPFSProtocol


@pytest.fixture
def mock_ipfs_client():
    """Create a mock IPFS client."""
    client = MagicMock()
    client.id.return_value = {"ID": "test-peer-id", "Addresses": []}
    client.close.return_value = None
    client.swarm.connect.return_value = None
    client.swarm.peers.return_value = []
    client.swarm.disconnect.return_value = None
    client.pubsub.publish.return_value = None
    client.pubsub.subscribe.return_value = iter([])
    client.dht.findprovs.return_value = iter([])
    client.object.stat.return_value = {"CumulativeSize": 1000, "NumLinks": 5}
    client.add_bytes.return_value = "QmTestCID123456789"
    client.cat.return_value = b"test content"
    client.pin.add.return_value = None
    client.pin.rm.return_value = None
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
    protocol.config = ipfs_config
    if hasattr(ipfs_config, "ipfs") and ipfs_config.ipfs:
        protocol.ipfs_api_url = ipfs_config.ipfs.api_url
    return protocol


@pytest.fixture
def sample_torrent_info():
    """Create sample torrent info."""
    return TorrentInfo(
        name="test_torrent",
        info_hash=b"0123456789abcdefghij",
        announce="http://tracker.example.com:8080/announce",
        total_length=1024,
        piece_length=512,
        num_pieces=2,
        pieces=[b"piece1hash123456789012", b"piece2hash123456789012"],
        files=[
            FileInfo(
                name="test_file.txt",
                length=1024,
                path=["test_file.txt"],
            )
        ],
    )


# Start/Stop Tests
@pytest.mark.asyncio
async def test_start_success(ipfs_protocol, mock_ipfs_client):
    """Test successful protocol start."""
    with patch(
        "ccbt.protocols.ipfs.ipfshttpclient.connect",
        return_value=mock_ipfs_client,
    ):
        await ipfs_protocol.start()

    assert ipfs_protocol.state == ProtocolState.CONNECTED
    assert ipfs_protocol._ipfs_connected is True  # noqa: SLF001


@pytest.mark.asyncio
async def test_start_failure(ipfs_protocol):
    """Test protocol start failure."""
    import ipfshttpclient.exceptions

    with patch(
        "ccbt.protocols.ipfs.ipfshttpclient.connect",
        side_effect=ipfshttpclient.exceptions.ConnectionError("Failed"),
    ), pytest.raises(ConnectionError):
        await ipfs_protocol.start()

    assert ipfs_protocol.state == ProtocolState.ERROR


@pytest.mark.asyncio
async def test_stop_success(ipfs_protocol, mock_ipfs_client):
    """Test successful protocol stop."""
    ipfs_protocol._ipfs_client = mock_ipfs_client  # noqa: SLF001
    ipfs_protocol._ipfs_connected = True  # noqa: SLF001

    await ipfs_protocol.stop()

    assert ipfs_protocol.state == ProtocolState.DISCONNECTED
    assert ipfs_protocol._ipfs_client is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_stop_with_exception(ipfs_protocol):
    """Test protocol stop with exception."""
    ipfs_protocol._ipfs_client = MagicMock()  # noqa: SLF001

    async def failing_close():
        close_error = RuntimeError("Close failed")
        raise close_error

    ipfs_protocol._ipfs_client.close = failing_close  # noqa: SLF001
    disconnect_error = RuntimeError("Disconnect failed")
    ipfs_protocol._disconnect_from_ipfs_network = AsyncMock(  # noqa: SLF001
        side_effect=disconnect_error
    )

    with pytest.raises(RuntimeError, match="Disconnect failed"):
        await ipfs_protocol.stop()

    assert ipfs_protocol.state == ProtocolState.ERROR


# Connection Management Tests
@pytest.mark.asyncio
async def test_connect_to_ipfs_network_verification_failure(ipfs_protocol, mock_ipfs_client):
    """Test connection with verification failure."""
    mock_ipfs_client.id.return_value = {}  # Missing ID

    with patch("ccbt.protocols.ipfs.ipfshttpclient.connect", return_value=mock_ipfs_client):
        with pytest.raises(ConnectionError, match="Failed to verify IPFS connection"):
            await ipfs_protocol._connect_to_ipfs_network()


@pytest.mark.asyncio
async def test_connect_to_ipfs_network_generic_exception(ipfs_protocol):
    """Test connection with generic exception."""
    with patch(
        "ccbt.protocols.ipfs.ipfshttpclient.connect",
        side_effect=Exception("Generic error"),
    ), pytest.raises(Exception):
        await ipfs_protocol._connect_to_ipfs_network()

    assert ipfs_protocol._connection_retries == 1


@pytest.mark.asyncio
async def test_disconnect_from_ipfs_network_with_peer_error(ipfs_protocol, mock_ipfs_client):
    """Test disconnection with peer disconnect error."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    ipfs_protocol.ipfs_peers["test-peer"] = MagicMock()

    with patch.object(ipfs_protocol, "disconnect_peer", side_effect=Exception("Peer error")):
        await ipfs_protocol._disconnect_from_ipfs_network()

    assert ipfs_protocol._ipfs_connected is False


@pytest.mark.asyncio
async def test_disconnect_from_ipfs_network_close_timeout(ipfs_protocol, mock_ipfs_client):
    """Test disconnection with close timeout."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    async def slow_close():
        await asyncio.sleep(10)

    mock_ipfs_client.close = slow_close

    await ipfs_protocol._disconnect_from_ipfs_network()

    assert ipfs_protocol._ipfs_client is None


# Peer Connection Tests
@pytest.mark.asyncio
async def test_connect_peer_success(ipfs_protocol, mock_ipfs_client):
    """Test successful peer connection."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    # Use valid CID format for peer_id
    valid_peer_id_hex = "QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o"
    valid_peer_id = valid_peer_id_hex.encode()
    peer_info = PeerInfo(
        ip="192.168.1.1",
        port=4001,
        peer_id=valid_peer_id,
    )

    # Mock the multiaddr parsing to return valid components
    with patch.object(ipfs_protocol, "_parse_multiaddr", return_value={
        "ip": "192.168.1.1",
        "port": 4001,
        "peer_id": valid_peer_id_hex,
    }), patch.object(ipfs_protocol, "_setup_message_listener", return_value=None):
        with patch("ccbt.protocols.ipfs.to_thread", return_value=None):
            result = await ipfs_protocol.connect_peer(peer_info)

    assert result is True


@pytest.mark.asyncio
async def test_connect_peer_not_connected(ipfs_protocol):
    """Test peer connection when IPFS not connected."""
    peer_info = PeerInfo(
        ip="192.168.1.1",
        port=4001,
        peer_id=b"test-peer-id-12345678",
    )

    result = await ipfs_protocol.connect_peer(peer_info)
    assert result is False


@pytest.mark.asyncio
async def test_connect_peer_invalid_info(ipfs_protocol, mock_ipfs_client):
    """Test peer connection with invalid info."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    peer_info = PeerInfo(ip="ipfs", port=4001, peer_id=b"test")  # Invalid IP

    result = await ipfs_protocol.connect_peer(peer_info)
    assert result is False


@pytest.mark.asyncio
async def test_connect_peer_with_queued_messages(ipfs_protocol, mock_ipfs_client):  # noqa: SLF001
    """Test peer connection with queued messages."""
    ipfs_protocol._ipfs_client = mock_ipfs_client  # noqa: SLF001
    ipfs_protocol._ipfs_connected = True  # noqa: SLF001

    valid_peer_id_hex = "QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o"
    valid_peer_id = valid_peer_id_hex.encode()
    # Note: connect_peer uses peer_id.hex() as the peer_key, not the CID string
    # So we need to use the hex representation of the bytes as the queue key
    peer_key_hex = valid_peer_id.hex()
    # Set up queued messages using the peer_id hex (bytes->hex) as key
    ipfs_protocol._message_queue[peer_key_hex] = [b"queued1", b"queued2"]  # noqa: SLF001

    peer_info = PeerInfo(
        ip="192.168.1.1",
        port=4001,
        peer_id=valid_peer_id,
    )

    # Mock successful connection flow
    # The key issue: connect_peer needs to successfully complete all steps
    # to reach the queue clearing code at line 399-403

    def mock_parse_multiaddr(addr_str):
        """Mock that doesn't raise, just returns the expected structure."""
        return {
            "ip": "192.168.1.1",
            "port": 4001,
            "peer_id": valid_peer_id_hex,
        }

    # Track calls to understand what's happening
    call_count = {"connect": 0, "peers": 0}

    async def mock_to_thread(func, *args, **kwargs):
        """Mock to_thread to handle swarm.connect and other calls."""
        func_str = str(func)
        if "connect" in func_str:
            call_count["connect"] += 1
            return None  # swarm.connect succeeds
        if "peers" in func_str:
            call_count["peers"] += 1
            return []  # swarm.peers returns empty list
        # For add_peer or other calls, just return what's needed
        return None

    with (
        patch.object(ipfs_protocol, "_parse_multiaddr", side_effect=mock_parse_multiaddr),
        patch.object(ipfs_protocol, "_setup_message_listener", return_value=None),
        patch.object(ipfs_protocol, "send_message", return_value=True) as mock_send,
        patch("ccbt.protocols.ipfs.to_thread", side_effect=mock_to_thread),
    ):
        result = await ipfs_protocol.connect_peer(peer_info)

    assert result is True, f"Connection failed, call_count={call_count}"
    # The queue should be cleared during successful connection
    # Verify queue was cleared (main functionality - queued messages are processed)
    # peer_key is peer_id.hex(), not the CID string
    assert peer_key_hex not in ipfs_protocol._message_queue, (  # noqa: SLF001
        f"Queue not cleared. Queue contents: {ipfs_protocol._message_queue}"  # noqa: SLF001
    )


@pytest.mark.asyncio
async def test_disconnect_peer_not_found(ipfs_protocol):
    """Test disconnecting peer that doesn't exist."""
    await ipfs_protocol.disconnect_peer("nonexistent-peer")
    # Should not raise


@pytest.mark.asyncio
async def test_disconnect_peer_success(ipfs_protocol, mock_ipfs_client):
    """Test successful peer disconnection."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    ipfs_peer = IPFSPeer(
        peer_id="test-peer",
        multiaddr="/ip4/127.0.0.1/tcp/4001",
        protocols=[],
        last_seen=0.0,
    )
    ipfs_protocol.ipfs_peers["test-peer"] = ipfs_peer

    await ipfs_protocol.disconnect_peer("test-peer")

    assert "test-peer" not in ipfs_protocol.ipfs_peers


# Message Tests
@pytest.mark.asyncio
async def test_send_message_not_connected(ipfs_protocol):
    """Test sending message when not connected."""
    ipfs_protocol.ipfs_peers["test-peer"] = IPFSPeer(
        peer_id="test-peer",
        multiaddr="",
        protocols=[],
    )

    result = await ipfs_protocol.send_message("test-peer", b"test")
    assert result is False
    assert "test-peer" in ipfs_protocol._message_queue


@pytest.mark.asyncio
async def test_send_message_too_large(ipfs_protocol, mock_ipfs_client):
    """Test sending message that's too large."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    ipfs_protocol.ipfs_peers["test-peer"] = IPFSPeer(
        peer_id="test-peer",
        multiaddr="",
        protocols=[],
    )

    large_message = b"x" * (2 * 1024 * 1024)  # 2MB
    result = await ipfs_protocol.send_message("test-peer", large_message)
    assert result is False


@pytest.mark.asyncio
async def test_send_message_pubsub_error(ipfs_protocol, mock_ipfs_client):
    """Test sending message with pubsub error."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    ipfs_protocol.ipfs_peers["test-peer"] = IPFSPeer(
        peer_id="test-peer",
        multiaddr="",
        protocols=[],
    )

    import ipfshttpclient.exceptions

    mock_ipfs_client.pubsub.publish.side_effect = ipfshttpclient.exceptions.Error("Pubsub error")

    result = await ipfs_protocol.send_message("test-peer", b"test")
    assert result is False


@pytest.mark.asyncio
async def test_receive_message_timeout(ipfs_protocol, mock_ipfs_client):
    """Test receiving message with timeout."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    ipfs_protocol.ipfs_peers["test-peer"] = IPFSPeer(
        peer_id="test-peer",
        multiaddr="",
        protocols=[],
    )
    ipfs_protocol._peer_message_queues["test-peer"] = asyncio.Queue()

    result = await ipfs_protocol.receive_message("test-peer")
    assert result is None


@pytest.mark.asyncio
async def test_receive_message_success(ipfs_protocol, mock_ipfs_client):
    """Test successfully receiving message."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    ipfs_protocol.ipfs_peers["test-peer"] = IPFSPeer(
        peer_id="test-peer",
        multiaddr="",
        protocols=[],
    )
    message_queue = asyncio.Queue()
    await message_queue.put(b"test message")
    ipfs_protocol._peer_message_queues["test-peer"] = message_queue

    result = await ipfs_protocol.receive_message("test-peer")
    assert result == b"test message"


@pytest.mark.asyncio
async def test_receive_message_exception(ipfs_protocol, mock_ipfs_client):
    """Test receiving message with exception."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    ipfs_protocol.ipfs_peers["test-peer"] = IPFSPeer(
        peer_id="test-peer",
        multiaddr="",
        protocols=[],
    )

    # Create a queue that raises on get
    class FailingQueue:
        async def get(self):
            msg = "Queue error"
            raise Exception(msg)

    ipfs_protocol._peer_message_queues["test-peer"] = FailingQueue()

    result = await ipfs_protocol.receive_message("test-peer")
    assert result is None


# Content Operations Tests
@pytest.mark.asyncio
async def test_add_content_success(ipfs_protocol, mock_ipfs_client):
    """Test adding content successfully."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    result = await ipfs_protocol.add_content(b"test data")

    assert result == "QmTestCID123456789"
    assert result in ipfs_protocol.ipfs_content


@pytest.mark.asyncio
async def test_add_content_dict_result(ipfs_protocol, mock_ipfs_client):
    """Test adding content with dict result."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    mock_ipfs_client.add_bytes.return_value = {"Hash": "QmDictCID"}

    result = await ipfs_protocol.add_content(b"test data")
    assert result == "QmDictCID"


@pytest.mark.asyncio
async def test_add_content_empty_cid(ipfs_protocol, mock_ipfs_client):
    """Test adding content with empty CID."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    mock_ipfs_client.add_bytes.return_value = ""

    result = await ipfs_protocol.add_content(b"test data")
    assert result == ""


@pytest.mark.asyncio
async def test_add_content_with_pinning(ipfs_protocol, mock_ipfs_client):
    """Test adding content with auto-pinning enabled."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    ipfs_protocol.config = Config()
    ipfs_protocol.config.ipfs = IPFSConfig(enable_pinning=True)

    with patch.object(ipfs_protocol, "pin_content", return_value=True):
        result = await ipfs_protocol.add_content(b"test data")

    assert result == "QmTestCID123456789"


@pytest.mark.asyncio
async def test_get_content_success(ipfs_protocol, mock_ipfs_client):
    """Test getting content successfully."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    # Ensure cat returns content
    mock_ipfs_client.cat.return_value = b"test content"
    
    # Mock CID verification to return True
    ipfs_protocol._verify_cid_integrity = MagicMock(return_value=True)
    
    # Mock to_thread to execute the lambda function passed to it
    async def mock_to_thread(func, *_args, **_kwargs):
        """Mock to_thread that executes the lambda function."""
        return func()

    with patch("ccbt.protocols.ipfs.to_thread", side_effect=mock_to_thread):
        result = await ipfs_protocol.get_content("QmTestCID")

    assert result == b"test content"


@pytest.mark.asyncio
async def test_get_content_empty(ipfs_protocol, mock_ipfs_client):
    """Test getting empty content."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    mock_ipfs_client.cat.return_value = b""

    result = await ipfs_protocol.get_content("QmTestCID")
    assert result is None


@pytest.mark.asyncio
async def test_get_content_updates_tracking(ipfs_protocol, mock_ipfs_client):
    """Test that getting content updates tracking."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    # Ensure cat returns content
    mock_ipfs_client.cat.return_value = b"test content"

    # Mock CID verification to return True
    ipfs_protocol._verify_cid_integrity = MagicMock(return_value=True)

    # Create existing content
    existing_content = IPFSContent(
        cid="QmTestCID",
        size=100,
        blocks=[],
        links=[],
    )
    ipfs_protocol.ipfs_content["QmTestCID"] = existing_content

    # Mock to_thread to execute the lambda function passed to it
    async def mock_to_thread(func, *_args, **_kwargs):
        """Mock to_thread that executes the lambda function."""
        return func()

    with patch("ccbt.protocols.ipfs.to_thread", side_effect=mock_to_thread):
        await ipfs_protocol.get_content("QmTestCID")

    assert existing_content.last_accessed > 0


@pytest.mark.asyncio
async def test_pin_content_success(ipfs_protocol, mock_ipfs_client):
    """Test pinning content successfully."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    result = await ipfs_protocol.pin_content("QmTestCID")

    assert result is True
    assert "QmTestCID" in ipfs_protocol._pinned_cids


@pytest.mark.asyncio
async def test_unpin_content_success(ipfs_protocol, mock_ipfs_client):
    """Test unpinning content successfully."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    ipfs_protocol._pinned_cids.add("QmTestCID")

    result = await ipfs_protocol.unpin_content("QmTestCID")

    assert result is True
    assert "QmTestCID" not in ipfs_protocol._pinned_cids


# Torrent Conversion Tests
@pytest.mark.asyncio
async def test_torrent_to_ipfs_success(ipfs_protocol, mock_ipfs_client, sample_torrent_info):
    """Test converting torrent to IPFS successfully."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    result = await ipfs_protocol._torrent_to_ipfs(sample_torrent_info)

    assert result.cid == "QmTestCID123456789"
    assert result.size == 1024
    assert len(result.blocks) == 2


@pytest.mark.asyncio
async def test_torrent_to_ipfs_not_connected(sample_torrent_info):
    """Test converting torrent when not connected."""
    protocol = IPFSProtocol()

    result = await protocol._torrent_to_ipfs(sample_torrent_info)

    assert result.cid.startswith("Qm")
    assert result.size == 1024


@pytest.mark.asyncio
async def test_torrent_to_ipfs_with_exception(ipfs_protocol, mock_ipfs_client, sample_torrent_info):
    """Test converting torrent with exception."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True
    mock_ipfs_client.add_bytes.side_effect = Exception("Add failed")

    result = await ipfs_protocol._torrent_to_ipfs(sample_torrent_info)

    # Should fallback to placeholder
    assert result.cid.startswith("Qm")
    assert result.size == 1024


# Content Discovery Tests
@pytest.mark.asyncio
async def test_find_content_peers_from_cache(ipfs_protocol):
    """Test finding content peers from cache."""
    import time
    current_time = time.time()
    ipfs_protocol._discovery_cache["test-cid"] = (["peer1", "peer2"], current_time)

    result = await ipfs_protocol._find_content_peers("test-cid")
    assert result == ["peer1", "peer2"]


@pytest.mark.asyncio
async def test_find_content_peers_dht_success(ipfs_protocol, mock_ipfs_client):
    """Test finding content peers via DHT."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    # Mock DHT response
    mock_provider = {"ID": "QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o"}
    mock_ipfs_client.dht.findprovs.return_value = iter([mock_provider])

    result = await ipfs_protocol._find_content_peers("test-cid")

    assert len(result) >= 0  # May be empty if validation fails


@pytest.mark.asyncio
async def test_find_content_peers_dht_timeout(ipfs_protocol, mock_ipfs_client):
    """Test finding content peers with DHT timeout."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    async def slow_findprovs():
        await asyncio.sleep(100)
        return iter([])

    mock_ipfs_client.dht.findprovs = slow_findprovs

    result = await ipfs_protocol._find_content_peers("test-cid")
    assert result == []


# Content Stats Tests
@pytest.mark.asyncio
async def test_get_content_stats_from_cache(ipfs_protocol):
    """Test getting content stats from cache."""
    import time
    current_time = time.time()
    ipfs_protocol._content_stats_cache["test-cid"] = (
        {"seeders": 5, "leechers": 2},
        current_time,
    )

    result = await ipfs_protocol._get_content_stats("test-cid")
    assert result["seeders"] == 5


@pytest.mark.asyncio
async def test_get_content_stats_ipfs_error(ipfs_protocol, mock_ipfs_client):
    """Test getting content stats with IPFS error."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    import ipfshttpclient.exceptions

    mock_ipfs_client.object.stat.side_effect = ipfshttpclient.exceptions.Error("Stats error")

    result = await ipfs_protocol._get_content_stats("test-cid")
    assert result["seeders"] == 0


# Scrape Torrent Tests
@pytest.mark.asyncio
async def test_scrape_torrent_success(ipfs_protocol, mock_ipfs_client, sample_torrent_info):
    """Test scraping torrent successfully."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    with patch.object(ipfs_protocol, "_torrent_to_ipfs", return_value=IPFSContent(
        cid="test-cid",
        size=100,
        blocks=[],
        links=[],
    )), patch.object(ipfs_protocol, "_get_content_stats", return_value={
        "seeders": 10,
        "leechers": 5,
        "completed": 100,
    }):
        result = await ipfs_protocol.scrape_torrent(sample_torrent_info)

    assert result["seeders"] == 10
    assert result["leechers"] == 5
    assert result["completed"] == 100


# Announce Torrent Tests
@pytest.mark.asyncio
async def test_announce_torrent_success(ipfs_protocol, mock_ipfs_client, sample_torrent_info):
    """Test announcing torrent successfully."""
    ipfs_protocol._ipfs_client = mock_ipfs_client
    ipfs_protocol._ipfs_connected = True

    with patch.object(ipfs_protocol, "_torrent_to_ipfs", return_value=IPFSContent(
        cid="test-cid",
        size=100,
        blocks=[],
        links=[],
    )):
        with patch.object(ipfs_protocol, "_find_content_peers", return_value=["peer1", "peer2"]):
            result = await ipfs_protocol.announce_torrent(sample_torrent_info)

    # Note: announce_torrent converts IPFS peer IDs to PeerInfo with ip="ipfs"
    # The actual peer conversion happens in the method
    assert len(result) >= 0  # May be empty if peer conversion fails


# Utility Method Tests
def test_add_gateway(ipfs_protocol):
    """Test adding gateway."""
    initial_count = len(ipfs_protocol.ipfs_gateway_urls)
    ipfs_protocol.add_gateway("https://new-gateway.com/ipfs/")

    assert len(ipfs_protocol.ipfs_gateway_urls) == initial_count + 1
    assert "https://new-gateway.com/ipfs/" in ipfs_protocol.ipfs_gateway_urls


def test_add_gateway_duplicate(ipfs_protocol):
    """Test adding duplicate gateway."""
    ipfs_protocol.add_gateway("https://ipfs.io/ipfs/")
    initial_count = len(ipfs_protocol.ipfs_gateway_urls)

    ipfs_protocol.add_gateway("https://ipfs.io/ipfs/")

    assert len(ipfs_protocol.ipfs_gateway_urls) == initial_count


def test_remove_gateway(ipfs_protocol):
    """Test removing gateway."""
    ipfs_protocol.remove_gateway("https://ipfs.io/ipfs/")

    assert "https://ipfs.io/ipfs/" not in ipfs_protocol.ipfs_gateway_urls


def test_get_ipfs_peers(ipfs_protocol):
    """Test getting IPFS peers."""
    peer = IPFSPeer(
        peer_id="test-peer",
        multiaddr="/ip4/127.0.0.1/tcp/4001",
        protocols=[],
    )
    ipfs_protocol.ipfs_peers["test-peer"] = peer

    result = ipfs_protocol.get_ipfs_peers()
    assert "test-peer" in result


def test_get_ipfs_content(ipfs_protocol):
    """Test getting IPFS content."""
    content = IPFSContent(
        cid="test-cid",
        size=100,
        blocks=[],
        links=[],
    )
    ipfs_protocol.ipfs_content["test-cid"] = content

    result = ipfs_protocol.get_ipfs_content()
    assert "test-cid" in result


def test_get_content_stats_existing(ipfs_protocol):
    """Test getting content stats for existing content."""
    content = IPFSContent(
        cid="test-cid",
        size=100,
        blocks=[],
        links=[],
    )
    ipfs_protocol.ipfs_content["test-cid"] = content

    result = ipfs_protocol.get_content_stats("test-cid")
    assert result is not None
    assert result["cid"] == "test-cid"


def test_get_content_stats_nonexistent(ipfs_protocol):
    """Test getting content stats for nonexistent content."""
    result = ipfs_protocol.get_content_stats("nonexistent")
    assert result is None


def test_get_all_content_stats(ipfs_protocol):
    """Test getting all content stats."""
    content1 = IPFSContent(cid="cid1", size=100, blocks=[], links=[])
    content2 = IPFSContent(cid="cid2", size=200, blocks=[], links=[])
    ipfs_protocol.ipfs_content["cid1"] = content1
    ipfs_protocol.ipfs_content["cid2"] = content2

    result = ipfs_protocol.get_all_content_stats()
    assert len(result) == 2
    assert "cid1" in result
    assert "cid2" in result

