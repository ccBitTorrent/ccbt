"""Unit tests for IPFS torrent conversion, piece-to-block, and DAG creation."""

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
    client.object.new.return_value = {"Hash": "QmRootCID123456"}
    client.object.patch.add_link.return_value = {"Hash": "QmPatchedCID123456"}
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
async def test_piece_to_block_basic(ipfs_protocol, mock_ipfs_client):
    """Test basic piece-to-block conversion."""
    piece_data = b"test piece data" * 32  # 448 bytes
    result = await ipfs_protocol._piece_to_block(piece_data, index=0, piece_length=512)
    
    assert "cid" in result
    assert result["data"] == piece_data
    assert result["size"] == len(piece_data)
    assert result["index"] == 0
    assert result["cid"]  # Should have a CID


@pytest.mark.asyncio
async def test_piece_to_block_variable_size(ipfs_protocol):
    """Test piece-to-block with variable piece sizes."""
    # Last piece may be smaller
    small_piece = b"small"
    result = await ipfs_protocol._piece_to_block(small_piece, index=1, piece_length=512)
    
    assert result["size"] == len(small_piece)
    assert result["size"] < 512


@pytest.mark.asyncio
async def test_piece_to_block_not_connected(ipfs_protocol):
    """Test piece-to-block when not connected."""
    ipfs_protocol._ipfs_connected = False
    ipfs_protocol._ipfs_client = None
    
    piece_data = b"test piece"
    result = await ipfs_protocol._piece_to_block(piece_data, index=0, piece_length=512)
    
    # Should fallback to hash-based CID
    assert "cid" in result
    assert result["data"] == piece_data


@pytest.mark.asyncio
async def test_create_dag_from_pieces_single(ipfs_protocol, mock_ipfs_client):
    """Test DAG creation from single piece."""
    pieces = [
        {
            "cid": "QmPiece1",
            "data": b"piece1 data",
            "size": 512,
            "index": 0,
        }
    ]
    
    mock_ipfs_client.add_bytes.return_value = "QmPiece1"
    mock_ipfs_client.object.new.return_value = {"Hash": "QmRoot"}
    mock_ipfs_client.object.patch.add_link.return_value = {"Hash": "QmRoot"}
    
    root_cid = await ipfs_protocol._create_ipfs_dag_from_pieces(pieces)
    
    assert root_cid
    assert mock_ipfs_client.object.new.called
    assert mock_ipfs_client.object.patch.add_link.called


@pytest.mark.asyncio
async def test_create_dag_from_pieces_multiple(ipfs_protocol, mock_ipfs_client):
    """Test DAG creation from multiple pieces."""
    pieces = [
        {"cid": "QmPiece1", "data": b"piece1", "size": 512, "index": 0},
        {"cid": "QmPiece2", "data": b"piece2", "size": 512, "index": 1},
    ]
    
    mock_ipfs_client.add_bytes.side_effect = ["QmPiece1", "QmPiece2"]
    mock_ipfs_client.object.new.return_value = {"Hash": "QmRoot"}
    mock_ipfs_client.object.patch.add_link.return_value = {"Hash": "QmRoot"}
    
    root_cid = await ipfs_protocol._create_ipfs_dag_from_pieces(pieces)
    
    assert root_cid
    # Should add links for each piece
    assert mock_ipfs_client.object.patch.add_link.call_count >= len(pieces)


@pytest.mark.asyncio
async def test_create_dag_from_pieces_large_file(ipfs_protocol, mock_ipfs_client):
    """Test DAG creation for large file (multiple nodes)."""
    # Create pieces that would exceed node size limit
    pieces = [
        {"cid": f"QmPiece{i}", "data": b"x" * 100000, "size": 100000, "index": i}
        for i in range(10)
    ]
    
    mock_ipfs_client.add_bytes.side_effect = [f"QmPiece{i}" for i in range(10)]
    mock_ipfs_client.object.new.return_value = {"Hash": "QmRoot"}
    mock_ipfs_client.object.patch.add_link.return_value = {"Hash": "QmRoot"}
    
    root_cid = await ipfs_protocol._create_ipfs_dag_from_pieces(pieces)
    
    assert root_cid


@pytest.mark.asyncio
async def test_create_dag_from_pieces_empty(ipfs_protocol):
    """Test DAG creation with empty pieces list."""
    with pytest.raises(ValueError):
        await ipfs_protocol._create_ipfs_dag_from_pieces([])


@pytest.mark.asyncio
async def test_create_dag_from_pieces_not_connected(ipfs_protocol):
    """Test DAG creation when not connected."""
    ipfs_protocol._ipfs_connected = False
    ipfs_protocol._ipfs_client = None
    
    pieces = [{"cid": "QmPiece1", "data": b"data", "size": 10, "index": 0}]
    
    with pytest.raises(ConnectionError):
        await ipfs_protocol._create_ipfs_dag_from_pieces(pieces)


@pytest.mark.asyncio
async def test_torrent_to_ipfs_basic(ipfs_protocol, sample_torrent_info, mock_ipfs_client):
    """Test basic torrent to IPFS conversion."""
    mock_ipfs_client.add_bytes.return_value = "QmMetadataCID"
    
    ipfs_content = await ipfs_protocol._torrent_to_ipfs(sample_torrent_info)
    
    assert ipfs_content.cid
    assert ipfs_content.size == sample_torrent_info.total_length
    assert len(ipfs_content.blocks) == sample_torrent_info.num_pieces


@pytest.mark.asyncio
async def test_torrent_to_ipfs_not_connected(ipfs_protocol, sample_torrent_info):
    """Test torrent conversion when not connected."""
    ipfs_protocol._ipfs_connected = False
    ipfs_protocol._ipfs_client = None
    
    ipfs_content = await ipfs_protocol._torrent_to_ipfs(sample_torrent_info)
    
    # Should create placeholder CID
    assert ipfs_content.cid
    assert ipfs_content.size == sample_torrent_info.total_length


@pytest.mark.asyncio
async def test_torrent_to_ipfs_with_pinning(ipfs_protocol, sample_torrent_info, mock_ipfs_client):
    """Test torrent conversion with auto-pinning enabled."""
    # Setup config with pinning enabled
    class MockConfig:
        class IPFS:
            enable_pinning = True
        ipfs = IPFS()
    
    ipfs_protocol.config = MockConfig()
    mock_ipfs_client.add_bytes.return_value = "QmMetadataCID"
    
    with patch.object(ipfs_protocol, "pin_content", new_callable=AsyncMock) as mock_pin:
        await ipfs_protocol._torrent_to_ipfs(sample_torrent_info)
        mock_pin.assert_called_once()


@pytest.mark.asyncio
async def test_torrent_to_ipfs_error_handling(ipfs_protocol, sample_torrent_info, mock_ipfs_client):
    """Test error handling in torrent conversion."""
    mock_ipfs_client.add_bytes.side_effect = Exception("IPFS error")
    
    # Should fallback to placeholder
    ipfs_content = await ipfs_protocol._torrent_to_ipfs(sample_torrent_info)
    
    assert ipfs_content.cid
    assert ipfs_content.size == sample_torrent_info.total_length

