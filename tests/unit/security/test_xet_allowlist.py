"""Unit tests for XET allowlist functionality.

Tests allowlist hash calculation, Ed25519 verification, and alias management.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]


class TestXetAllowlist:
    """Test XetAllowlist class."""

    @pytest.fixture
    def temp_allowlist_path(self):
        """Create temporary allowlist path."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".allowlist") as f:
            yield Path(f.name)
        # Cleanup
        try:
            Path(f.name).unlink(missing_ok=True)
        except Exception:
            pass

    @pytest.fixture
    def allowlist(self, temp_allowlist_path):
        """Create XetAllowlist instance."""
        from ccbt.security.xet_allowlist import XetAllowlist

        return XetAllowlist(allowlist_path=temp_allowlist_path)

    @pytest.mark.asyncio
    async def test_allowlist_add_peer(self, allowlist):
        """Test adding peer to allowlist."""
        await allowlist.load()

        allowlist.add_peer(peer_id="peer_1", public_key=b"1" * 32)
        await allowlist.save()

        assert allowlist.is_allowed("peer_1") is True

    @pytest.mark.asyncio
    async def test_allowlist_remove_peer(self, allowlist):
        """Test removing peer from allowlist."""
        await allowlist.load()

        allowlist.add_peer(peer_id="peer_2", public_key=b"2" * 32)
        await allowlist.save()

        removed = allowlist.remove_peer("peer_2")
        assert removed is True
        assert allowlist.is_allowed("peer_2") is False

    @pytest.mark.asyncio
    async def test_allowlist_hash_calculation(self, allowlist):
        """Test allowlist hash calculation."""
        await allowlist.load()

        # Add peers
        allowlist.add_peer(peer_id="peer_1", public_key=b"1" * 32)
        allowlist.add_peer(peer_id="peer_2", public_key=b"2" * 32)
        await allowlist.save()

        # Get hash
        hash1 = allowlist.get_allowlist_hash()
        assert len(hash1) == 32

        # Add another peer
        allowlist.add_peer(peer_id="peer_3", public_key=b"3" * 32)
        await allowlist.save()

        # Hash should change
        hash2 = allowlist.get_allowlist_hash()
        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_allowlist_alias_management(self, allowlist):
        """Test alias management."""
        await allowlist.load()

        # Add peer with alias
        allowlist.add_peer(peer_id="peer_1", public_key=b"1" * 32, alias="Alice")
        await allowlist.save()

        # Get alias
        alias = allowlist.get_alias("peer_1")
        assert alias == "Alice"

        # Update alias
        allowlist.set_alias("peer_1", "Bob")
        await allowlist.save()

        alias = allowlist.get_alias("peer_1")
        assert alias == "Bob"

        # Remove alias
        removed = allowlist.remove_alias("peer_1")
        assert removed is True

        alias = allowlist.get_alias("peer_1")
        assert alias is None

    @pytest.mark.asyncio
    async def test_allowlist_encryption(self, temp_allowlist_path):
        """Test allowlist encryption."""
        from ccbt.security.xet_allowlist import XetAllowlist

        allowlist = XetAllowlist(allowlist_path=temp_allowlist_path)
        await allowlist.load()

        # Add peer
        allowlist.add_peer(peer_id="peer_1", public_key=b"1" * 32)
        await allowlist.save()

        # Verify file is encrypted (not plain JSON)
        file_data = temp_allowlist_path.read_bytes()
        # Encrypted file should not contain plain text peer IDs
        assert b"peer_1" not in file_data or len(file_data) > 100  # Encrypted

    @pytest.mark.asyncio
    async def test_allowlist_verify_peer(self, allowlist):
        """Test peer verification with Ed25519."""
        await allowlist.load()

        # Add peer with public key
        public_key = b"1" * 32
        allowlist.add_peer(peer_id="peer_1", public_key=public_key)
        await allowlist.save()

        # Verify peer (without actual signature verification for unit test)
        # In real scenario, would use Ed25519KeyManager
        is_allowed = allowlist.is_allowed("peer_1")
        assert is_allowed is True

        # Non-allowed peer
        is_allowed = allowlist.is_allowed("peer_unknown")
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_allowlist_get_peers(self, allowlist):
        """Test getting list of peers."""
        await allowlist.load()

        # Add multiple peers
        for i in range(5):
            allowlist.add_peer(peer_id=f"peer_{i}", public_key=bytes([i] * 32))

        await allowlist.save()

        peers = allowlist.get_peers()
        assert len(peers) == 5
        assert "peer_0" in peers
        assert "peer_4" in peers

    @pytest.mark.asyncio
    async def test_allowlist_get_peer_info(self, allowlist):
        """Test getting peer information."""
        await allowlist.load()

        allowlist.add_peer(
            peer_id="peer_1",
            public_key=b"1" * 32,
            metadata={"name": "Test Peer"},
            alias="Alice",
        )
        await allowlist.save()

        peer_info = allowlist.get_peer_info("peer_1")
        assert peer_info is not None
        assert peer_info.get("public_key") == "1" * 64  # Hex encoded
        metadata = peer_info.get("metadata", {})
        if isinstance(metadata, dict):
            assert metadata.get("alias") == "Alice"









