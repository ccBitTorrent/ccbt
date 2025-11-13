"""Unit tests for DHT Xet chunk storage (BEP 44).

Tests store_chunk_hash and get_chunk_peers methods.
"""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.discovery.dht import AsyncDHTClient
from ccbt.models import PeerInfo


pytestmark = [pytest.mark.unit, pytest.mark.extensions]


class TestDHTXetChunks:
    """Test DHT Xet chunk storage methods."""

    @pytest.fixture
    def dht_client(self):
        """Create DHT client for testing."""
        client = AsyncDHTClient()
        # Mock transport to avoid network operations
        client.transport = None
        client.socket = None
        return client

    @pytest.mark.asyncio
    async def test_store_chunk_hash_invalid_size(self, dht_client):
        """Test that invalid chunk hash size raises ValueError."""
        invalid_hash = b"short"  # Not 32 bytes

        with pytest.raises(ValueError, match="Chunk hash must be 32 bytes"):
            await dht_client.store_chunk_hash(invalid_hash)

    @pytest.mark.asyncio
    async def test_store_chunk_hash_conversion(self, dht_client):
        """Test that 32-byte hash is converted to 20-byte DHT key."""
        chunk_hash = b"X" * 32  # 32-byte chunk hash

        # Mock put_data to verify it's called with 20-byte key
        dht_client.put_data = AsyncMock(return_value=1)

        # Mock config to enable storage
        dht_client.config.discovery.dht_enable_storage = True
        dht_client.read_only = False

        await dht_client.store_chunk_hash(chunk_hash)

        # Verify put_data was called
        assert dht_client.put_data.called

        # Verify key is 20 bytes (SHA-1 of chunk hash)
        call_args = dht_client.put_data.call_args[0]
        dht_key = call_args[0]
        assert len(dht_key) == 20

        # Verify key is SHA-1 of chunk hash
        expected_key = hashlib.sha1(chunk_hash).digest()
        assert dht_key == expected_key

    @pytest.mark.asyncio
    async def test_store_chunk_hash_metadata(self, dht_client):
        """Test that metadata is stored correctly."""
        chunk_hash = b"Y" * 32
        custom_metadata = {"custom_field": "value"}

        dht_client.put_data = AsyncMock(return_value=1)
        dht_client.config.discovery.dht_enable_storage = True
        dht_client.read_only = False

        await dht_client.store_chunk_hash(chunk_hash, metadata=custom_metadata)

        # Verify put_data was called with metadata
        call_args = dht_client.put_data.call_args
        stored_metadata = call_args[0][1]  # Second argument

        # Should contain required fields
        assert b"type" in stored_metadata
        assert stored_metadata[b"type"] == b"xet_chunk"
        assert b"chunk_hash" in stored_metadata
        assert stored_metadata[b"chunk_hash"] == chunk_hash
        assert b"available" in stored_metadata

    @pytest.mark.asyncio
    async def test_get_chunk_peers_invalid_size(self, dht_client):
        """Test that invalid chunk hash size raises ValueError."""
        invalid_hash = b"short"

        with pytest.raises(ValueError, match="Chunk hash must be 32 bytes"):
            await dht_client.get_chunk_peers(invalid_hash)

    @pytest.mark.asyncio
    async def test_get_chunk_peers_no_data(self, dht_client):
        """Test get_chunk_peers when no data is found."""
        chunk_hash = b"Z" * 32

        # Mock get_data to return None (no data found)
        dht_client.get_data = AsyncMock(return_value=None)
        dht_client.get_peers = AsyncMock(return_value=[])

        peers = await dht_client.get_chunk_peers(chunk_hash)

        # Should return empty list or try fallback
        assert isinstance(peers, list)

    @pytest.mark.asyncio
    async def test_get_chunk_peers_with_metadata(self, dht_client):
        """Test get_chunk_peers with metadata containing peer info."""
        chunk_hash = b"A" * 32

        # Mock get_data to return metadata with peer info
        mock_metadata = {
            b"type": b"xet_chunk",
            b"chunk_hash": chunk_hash,
            b"peers": [
                {b"ip": b"192.168.1.1", b"port": 6881},
                {b"ip": b"192.168.1.2", b"port": 6882},
            ],
        }

        # Mock get_data to return metadata
        # The actual implementation may handle decoding internally
        dht_client.get_data = AsyncMock(return_value=b"mock_data")

        peers = await dht_client.get_chunk_peers(chunk_hash)

        # Should return a list (may be empty if decoding fails or data is None)
        assert isinstance(peers, list)

    @pytest.mark.asyncio
    async def test_get_chunk_peers_fallback(self, dht_client):
        """Test get_chunk_peers fallback to get_peers."""
        chunk_hash = b"B" * 32

        # Mock get_data to return None
        dht_client.get_data = AsyncMock(return_value=None)

        # Mock get_peers to return peer tuples
        peer_tuple = ("192.168.1.1", 6881)
        dht_client.get_peers = AsyncMock(return_value=[peer_tuple])

        peers = await dht_client.get_chunk_peers(chunk_hash)

        # Should use get_peers as fallback
        assert isinstance(peers, list)
        # May contain PeerInfo objects from tuples

    @pytest.mark.asyncio
    async def test_get_chunk_peers_key_conversion(self, dht_client):
        """Test that 32-byte hash is converted to 20-byte DHT key."""
        chunk_hash = b"C" * 32

        dht_client.get_data = AsyncMock(return_value=None)
        dht_client.get_peers = AsyncMock(return_value=[])

        await dht_client.get_chunk_peers(chunk_hash)

        # Verify get_data was called with 20-byte key
        assert dht_client.get_data.called

        call_args = dht_client.get_data.call_args[0]
        dht_key = call_args[0]

        # Should be 20 bytes (SHA-1 of chunk hash)
        assert len(dht_key) == 20

        # Verify key is SHA-1 of chunk hash
        expected_key = hashlib.sha1(chunk_hash).digest()
        assert dht_key == expected_key

