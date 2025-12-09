"""Tests for blacklist updater functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.security.blacklist_updater import BlacklistUpdater
from ccbt.security.security_manager import SecurityManager


class TestBlacklistUpdater:
    """Tests for BlacklistUpdater class."""

    @pytest.fixture
    def security_manager(self):
        """Create security manager instance."""
        return SecurityManager()

    @pytest.fixture
    def updater(self, security_manager):
        """Create blacklist updater instance."""
        return BlacklistUpdater(
            security_manager, update_interval=60.0, sources=["http://example.com/list"]
        )

    @pytest.mark.asyncio
    async def test_update_from_source_plain_text(self, updater):
        """Test updating from plain text source."""
        content = "192.168.1.1\n192.168.1.2\n# Comment\n192.168.1.3\n"

        with patch("aiohttp.ClientSession") as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.text = AsyncMock(return_value=content)
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_resp
            )

            added = await updater.update_from_source("http://example.com/list")

            assert added == 3
            assert "192.168.1.1" in updater.security_manager.blacklist_entries
            assert "192.168.1.2" in updater.security_manager.blacklist_entries
            assert "192.168.1.3" in updater.security_manager.blacklist_entries

    @pytest.mark.asyncio
    async def test_update_from_source_json(self, updater):
        """Test updating from JSON source."""
        content = '{"ips": ["192.168.1.1", "192.168.1.2"]}'

        with patch("aiohttp.ClientSession") as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.text = AsyncMock(return_value=content)
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_resp
            )

            added = await updater.update_from_source("http://example.com/list")

            assert added == 2
            assert "192.168.1.1" in updater.security_manager.blacklist_entries
            assert "192.168.1.2" in updater.security_manager.blacklist_entries

    @pytest.mark.asyncio
    async def test_update_from_source_csv(self, updater):
        """Test updating from CSV source."""
        content = "ip,reason\n192.168.1.1,Test1\n192.168.1.2,Test2\n"

        with patch("aiohttp.ClientSession") as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.text = AsyncMock(return_value=content)
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_resp
            )

            added = await updater.update_from_source("http://example.com/list")

            assert added == 2

    @pytest.mark.asyncio
    async def test_update_from_source_http_error(self, updater):
        """Test handling HTTP errors."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 404
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_resp
            )

            added = await updater.update_from_source("http://example.com/list")

            assert added == 0

    @pytest.mark.asyncio
    async def test_update_from_source_timeout(self, updater):
        """Test handling timeout errors."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = (
                asyncio.TimeoutError()
            )

            added = await updater.update_from_source("http://example.com/list")

            assert added == 0

    @pytest.mark.asyncio
    async def test_start_auto_update(self, updater):
        """Test starting auto-update task."""
        with patch.object(updater, "update_from_source", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = 0

            await updater.start_auto_update()

            assert updater._update_task is not None
            assert not updater._update_task.done()

            # Cancel task
            updater.stop_auto_update()
            await asyncio.sleep(0.1)  # Allow cancellation to propagate

    def test_stop_auto_update(self, updater):
        """Test stopping auto-update task."""
        # Create a dummy task
        async def dummy_task():
            await asyncio.sleep(100)

        updater._update_task = asyncio.create_task(dummy_task())

        updater.stop_auto_update()

        assert updater._update_task.cancelled()

    def test_parse_plain_text(self, updater):
        """Test parsing plain text format."""
        content = "192.168.1.1\n192.168.1.2\n# Comment\n192.168.1.3 # With comment\n"
        ips = updater._parse_plain_text(content)

        assert len(ips) == 3
        assert "192.168.1.1" in ips
        assert "192.168.1.2" in ips
        assert "192.168.1.3" in ips

    def test_parse_json(self, updater):
        """Test parsing JSON format."""
        # Dict format
        content1 = '{"ips": ["192.168.1.1", "192.168.1.2"]}'
        ips1 = updater._parse_json(content1)
        assert len(ips1) == 2

        # Array format
        content2 = '["192.168.1.1", "192.168.1.2"]'
        ips2 = updater._parse_json(content2)
        assert len(ips2) == 2

    def test_parse_csv(self, updater):
        """Test parsing CSV format."""
        content = "ip,reason\n192.168.1.1,Test1\n192.168.1.2,Test2\n"
        ips = updater._parse_csv(content)

        assert len(ips) == 2
        assert "192.168.1.1" in ips
        assert "192.168.1.2" in ips

    def test_is_valid_ip(self, updater):
        """Test IP validation."""
        assert updater._is_valid_ip("192.168.1.1")
        assert updater._is_valid_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        assert not updater._is_valid_ip("invalid")
        assert not updater._is_valid_ip("999.999.999.999")
        assert not updater._is_valid_ip("")

    def test_parse_blacklist_content_detection(self, updater):
        """Test format detection in parse_blacklist_content."""
        # JSON detection
        json_content = '{"ips": ["192.168.1.1"]}'
        ips = updater._parse_blacklist_content(json_content, "http://example.com")
        assert len(ips) == 1

        # CSV detection
        csv_content = "ip\n192.168.1.1\n"
        ips = updater._parse_blacklist_content(csv_content, "http://example.com")
        assert len(ips) == 1

        # Plain text (default)
        text_content = "192.168.1.1\n"
        ips = updater._parse_blacklist_content(text_content, "http://example.com")
        assert len(ips) == 1









