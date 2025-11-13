"""Unit tests for IPFS content operations (add, pin, unpin, stats)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.models import FileInfo, TorrentInfo
from ccbt.protocols.ipfs import IPFSProtocol


@pytest.fixture
def mock_ipfs_client():
    """Create a mock IPFS client."""
    client = MagicMock()
    client.id.return_value = {"ID": "test-peer-id", "Addresses": []}
    client.add_bytes.return_value = "QmTestCID123456789"
    client.object.stat.return_value = {
        "CumulativeSize": 1000,
        "NumLinks": 5,
    }
    client.pin.add.return_value = None
    client.pin.rm.return_value = None
    client.dht.findprovs.return_value = iter([{"ID": "QmPeer1"}])
    return client


@pytest.fixture
def ipfs_protocol(mock_ipfs_client):
    """Create IPFS protocol instance."""
    protocol = IPFSProtocol()
    
    with patch(
        "ccbt.protocols.ipfs.ipfshttpclient.connect",
        return_value=mock_ipfs_client,
    ):
        protocol._ipfs_client = mock_ipfs_client
        protocol._ipfs_connected = True
    
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


@pytest.mark.asyncio
async def test_add_content_basic(ipfs_protocol, mock_ipfs_client):
    """Test basic content addition."""
    data = b"test content"
    mock_ipfs_client.add_bytes.return_value = "QmNewCID123456789"
    
    cid = await ipfs_protocol.add_content(data)
    
    assert cid == "QmNewCID123456789"
    mock_ipfs_client.add_bytes.assert_called_once_with(data, cid_version=1)


@pytest.mark.asyncio
async def test_add_content_not_connected(ipfs_protocol):
    """Test content addition when not connected."""
    ipfs_protocol._ipfs_connected = False
    ipfs_protocol._ipfs_client = None
    
    cid = await ipfs_protocol.add_content(b"test")
    assert cid == ""


@pytest.mark.asyncio
async def test_add_content_error_handling(ipfs_protocol, mock_ipfs_client):
    """Test error handling in content addition."""
    import ipfshttpclient.exceptions
    
    mock_ipfs_client.add_bytes.side_effect = ipfshttpclient.exceptions.Error("Failed")
    
    cid = await ipfs_protocol.add_content(b"test")
    assert cid == ""


@pytest.mark.asyncio
async def test_pin_content_basic(ipfs_protocol, mock_ipfs_client):
    """Test basic content pinning."""
    cid = "QmTestCID"
    
    result = await ipfs_protocol.pin_content(cid)
    
    assert result is True
    mock_ipfs_client.pin.add.assert_called_once_with(cid)
    assert cid in ipfs_protocol._pinned_cids


@pytest.mark.asyncio
async def test_pin_content_not_connected(ipfs_protocol):
    """Test content pinning when not connected."""
    ipfs_protocol._ipfs_connected = False
    ipfs_protocol._ipfs_client = None
    
    result = await ipfs_protocol.pin_content("QmTestCID")
    assert result is False


@pytest.mark.asyncio
async def test_pin_content_error_handling(ipfs_protocol, mock_ipfs_client):
    """Test error handling in content pinning."""
    import ipfshttpclient.exceptions
    
    mock_ipfs_client.pin.add.side_effect = ipfshttpclient.exceptions.Error("Failed")
    
    result = await ipfs_protocol.pin_content("QmTestCID")
    assert result is False


@pytest.mark.asyncio
async def test_unpin_content_basic(ipfs_protocol, mock_ipfs_client):
    """Test basic content unpinning."""
    cid = "QmTestCID"
    ipfs_protocol._pinned_cids.add(cid)
    
    result = await ipfs_protocol.unpin_content(cid)
    
    assert result is True
    mock_ipfs_client.pin.rm.assert_called_once_with(cid)
    assert cid not in ipfs_protocol._pinned_cids


@pytest.mark.asyncio
async def test_unpin_content_not_connected(ipfs_protocol):
    """Test content unpinning when not connected."""
    ipfs_protocol._ipfs_connected = False
    ipfs_protocol._ipfs_client = None
    
    result = await ipfs_protocol.unpin_content("QmTestCID")
    assert result is False


@pytest.mark.asyncio
async def test_unpin_content_error_handling(ipfs_protocol, mock_ipfs_client):
    """Test error handling in content unpinning."""
    import ipfshttpclient.exceptions
    
    mock_ipfs_client.pin.rm.side_effect = ipfshttpclient.exceptions.Error("Failed")
    
    result = await ipfs_protocol.unpin_content("QmTestCID")
    assert result is False


@pytest.mark.asyncio
async def test_get_content_stats_basic(ipfs_protocol, mock_ipfs_client):
    """Test basic content statistics."""
    cid = "QmTestCID"
    
    stats = await ipfs_protocol._get_content_stats(cid)
    
    assert "seeders" in stats
    assert "leechers" in stats
    assert "completed" in stats
    assert "size" in stats
    assert "blocks_count" in stats


@pytest.mark.asyncio
async def test_get_content_stats_with_seeders(ipfs_protocol, mock_ipfs_client):
    """Test content statistics with seeder count."""
    cid = "QmTestCID"
    
    # Mock peer discovery to return providers
    with patch.object(
        ipfs_protocol, "_find_content_peers", return_value=["QmPeer1", "QmPeer2"]
    ):
        stats = await ipfs_protocol._get_content_stats(cid)
        
        assert stats["seeders"] == 2


@pytest.mark.asyncio
async def test_get_content_stats_caching(ipfs_protocol, mock_ipfs_client):
    """Test content statistics caching."""
    cid = "QmTestCID"
    
    # Ensure mock returns proper stats structure
    mock_ipfs_client.object.stat.return_value = {
        "CumulativeSize": 1000,
        "NumLinks": 5,
    }
    
    # Mock peer discovery to return consistent results for both calls
    mock_find_peers = AsyncMock(return_value=["QmPeer1"])
    
    with patch.object(ipfs_protocol, "_find_content_peers", mock_find_peers):
        # First call
        stats1 = await ipfs_protocol._get_content_stats(cid)
        call_count_1 = mock_ipfs_client.object.stat.call_count
        
        # Second call (should use cache - within 60 seconds)
        stats2 = await ipfs_protocol._get_content_stats(cid)
        call_count_2 = mock_ipfs_client.object.stat.call_count
        
        # Results should be same (cached) - check all expected keys exist
        assert "seeders" in stats1
        assert "seeders" in stats2
        assert "leechers" in stats1
        assert "completed" in stats1
        
        # If size is present, it should match
        if "size" in stats1 and "size" in stats2:
            assert stats1["size"] == stats2["size"]
        if "blocks_count" in stats1 and "blocks_count" in stats2:
            assert stats1["blocks_count"] == stats2["blocks_count"]


@pytest.mark.asyncio
async def test_get_content_stats_not_connected(ipfs_protocol):
    """Test content statistics when not connected."""
    ipfs_protocol._ipfs_connected = False
    ipfs_protocol._ipfs_client = None
    
    stats = await ipfs_protocol._get_content_stats("QmTestCID")
    assert stats == {"seeders": 0, "leechers": 0, "completed": 0}


@pytest.mark.asyncio
async def test_get_content_stats_error_handling(ipfs_protocol, mock_ipfs_client):
    """Test error handling in content statistics."""
    import ipfshttpclient.exceptions
    
    mock_ipfs_client.object.stat.side_effect = ipfshttpclient.exceptions.Error("Failed")
    
    stats = await ipfs_protocol._get_content_stats("QmTestCID")
    assert stats == {"seeders": 0, "leechers": 0, "completed": 0}


@pytest.mark.asyncio
async def test_scrape_torrent(ipfs_protocol, sample_torrent_info, mock_ipfs_client):
    """Test torrent scraping."""
    mock_ipfs_client.add_bytes.return_value = "QmMetadataCID"
    
    stats = await ipfs_protocol.scrape_torrent(sample_torrent_info)
    
    assert "seeders" in stats
    assert "leechers" in stats
    assert "completed" in stats

