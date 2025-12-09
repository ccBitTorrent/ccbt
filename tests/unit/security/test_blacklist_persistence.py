"""Tests for blacklist persistence functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from ccbt.security.security_manager import BlacklistEntry, SecurityManager


class TestBlacklistPersistence:
    """Tests for blacklist persistence."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def security_manager(self):
        """Create security manager instance."""
        return SecurityManager()

    @pytest.mark.asyncio
    async def test_save_blacklist(self, security_manager, temp_dir):
        """Test saving blacklist to file."""
        blacklist_file = temp_dir / "blacklist.json"

        # Add some IPs to blacklist
        security_manager.add_to_blacklist("192.168.1.1", "Test 1")
        security_manager.add_to_blacklist("192.168.1.2", "Test 2", expires_in=3600)

        # Save blacklist
        await security_manager.save_blacklist(blacklist_file)

        # Verify file exists
        assert blacklist_file.exists()

        # Verify file content
        with open(blacklist_file) as f:
            data = json.load(f)

        assert data["version"] == 1
        assert len(data["entries"]) == 2
        assert data["metadata"]["count"] == 2

        # Check IPs
        ips = [entry["ip"] for entry in data["entries"]]
        assert "192.168.1.1" in ips
        assert "192.168.1.2" in ips

    @pytest.mark.asyncio
    async def test_save_blacklist_atomic_write(self, security_manager, temp_dir):
        """Test atomic write pattern (temp file + rename)."""
        blacklist_file = temp_dir / "blacklist.json"
        temp_file = blacklist_file.with_suffix(".tmp")

        security_manager.add_to_blacklist("192.168.1.1", "Test")

        # Save should create temp file then rename
        await security_manager.save_blacklist(blacklist_file)

        # Temp file should not exist
        assert not temp_file.exists()
        # Final file should exist
        assert blacklist_file.exists()

    @pytest.mark.asyncio
    async def test_load_blacklist(self, security_manager, temp_dir):
        """Test loading blacklist from file."""
        blacklist_file = temp_dir / "blacklist.json"

        # Create test blacklist file
        data = {
            "version": 1,
            "entries": [
                {
                    "ip": "192.168.1.1",
                    "reason": "Test 1",
                    "added_at": 1000.0,
                    "expires_at": None,
                    "source": "manual",
                },
                {
                    "ip": "192.168.1.2",
                    "reason": "Test 2",
                    "added_at": 1000.0,
                    "expires_at": None,
                    "source": "auto",
                },
            ],
            "metadata": {"last_updated": 1000.0, "count": 2},
        }

        with open(blacklist_file, "w") as f:
            json.dump(data, f)

        # Load blacklist
        await security_manager.load_blacklist(blacklist_file)

        # Verify IPs are loaded
        assert "192.168.1.1" in security_manager.blacklist_entries
        assert "192.168.1.2" in security_manager.blacklist_entries
        assert len(security_manager.blacklist_entries) == 2

    @pytest.mark.asyncio
    async def test_load_blacklist_missing_file(self, security_manager, temp_dir):
        """Test loading from non-existent file."""
        blacklist_file = temp_dir / "nonexistent.json"

        # Should not raise error
        await security_manager.load_blacklist(blacklist_file)

        # Blacklist should be empty
        assert len(security_manager.blacklist_entries) == 0

    @pytest.mark.asyncio
    async def test_load_blacklist_invalid_json(self, security_manager, temp_dir):
        """Test loading invalid JSON file."""
        blacklist_file = temp_dir / "blacklist.json"

        # Create invalid JSON
        with open(blacklist_file, "w") as f:
            f.write("invalid json content")

        # Should not raise error, just log warning
        await security_manager.load_blacklist(blacklist_file)

        # Blacklist should be empty
        assert len(security_manager.blacklist_entries) == 0

    @pytest.mark.asyncio
    async def test_load_blacklist_invalid_ip(self, security_manager, temp_dir):
        """Test loading blacklist with invalid IP addresses."""
        blacklist_file = temp_dir / "blacklist.json"

        # Create blacklist file with invalid IP
        data = {
            "version": 1,
            "entries": [
                {"ip": "invalid.ip", "reason": "Test", "added_at": 1000.0},
                {"ip": "192.168.1.1", "reason": "Test", "added_at": 1000.0},
            ],
            "metadata": {"last_updated": 1000.0, "count": 2},
        }

        with open(blacklist_file, "w") as f:
            json.dump(data, f)

        # Load blacklist
        await security_manager.load_blacklist(blacklist_file)

        # Only valid IP should be loaded
        assert "192.168.1.1" in security_manager.blacklist_entries
        assert "invalid.ip" not in security_manager.blacklist_entries
        assert len(security_manager.blacklist_entries) == 1

    @pytest.mark.asyncio
    async def test_load_blacklist_legacy_format(self, security_manager, temp_dir):
        """Test loading legacy format (just list of IPs)."""
        blacklist_file = temp_dir / "blacklist.json"

        # Create legacy format file
        data = {"ips": ["192.168.1.1", "192.168.1.2"]}

        with open(blacklist_file, "w") as f:
            json.dump(data, f)

        # Load blacklist
        await security_manager.load_blacklist(blacklist_file)

        # IPs should be loaded
        assert "192.168.1.1" in security_manager.blacklist_entries
        assert "192.168.1.2" in security_manager.blacklist_entries

    def test_blacklist_entry_is_expired(self):
        """Test BlacklistEntry expiration logic."""
        import time

        # Permanent entry
        entry1 = BlacklistEntry(
            ip="192.168.1.1", reason="Test", added_at=time.time(), expires_at=None
        )
        assert not entry1.is_expired()

        # Expired entry
        entry2 = BlacklistEntry(
            ip="192.168.1.2",
            reason="Test",
            added_at=time.time() - 1000,
            expires_at=time.time() - 100,
        )
        assert entry2.is_expired()

        # Not expired entry
        entry3 = BlacklistEntry(
            ip="192.168.1.3",
            reason="Test",
            added_at=time.time(),
            expires_at=time.time() + 3600,
        )
        assert not entry3.is_expired()

    @pytest.mark.asyncio
    async def test_save_load_roundtrip(self, security_manager, temp_dir):
        """Test save and load roundtrip."""
        blacklist_file = temp_dir / "blacklist.json"

        # Add IPs with different sources
        security_manager.add_to_blacklist("192.168.1.1", "Test 1", source="manual")
        security_manager.add_to_blacklist(
            "192.168.1.2", "Test 2", expires_in=3600, source="auto"
        )

        # Save
        await security_manager.save_blacklist(blacklist_file)

        # Create new manager and load
        new_manager = SecurityManager()
        await new_manager.load_blacklist(blacklist_file)

        # Verify entries
        assert len(new_manager.blacklist_entries) == 2
        assert "192.168.1.1" in new_manager.blacklist_entries
        assert "192.168.1.2" in new_manager.blacklist_entries

        # Verify entry details
        entry1 = new_manager.blacklist_entries["192.168.1.1"]
        assert entry1.reason == "Test 1"
        assert entry1.source == "manual"
        assert entry1.expires_at is None

        entry2 = new_manager.blacklist_entries["192.168.1.2"]
        assert entry2.reason == "Test 2"
        assert entry2.source == "auto"
        assert entry2.expires_at is not None









