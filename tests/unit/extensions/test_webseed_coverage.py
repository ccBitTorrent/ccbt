"""Additional tests for extensions/webseed.py to achieve coverage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.extensions]

from ccbt.extensions.webseed import WebSeedExtension
from ccbt.models import PieceInfo


class TestWebSeedExtensionCoverage:
    """Test coverage gaps in WebSeed Extension."""

    @pytest.mark.asyncio
    async def test_download_piece_session_none_after_start(self):
        """Test download_piece with session None after start (line 200-202)."""
        extension = WebSeedExtension()
        webseed_id = extension.add_webseed("http://example.com/torrent")
        
        piece_info = PieceInfo(index=0, length=1024, hash=b"x" * 20)
        
        # Mock start to not create session
        original_start = extension.start
        
        async def mock_start():
            # Don't create session
            pass
        
        extension.start = mock_start
        
        # Mock session to be None even after start
        with patch.object(extension, "session", None):
            result = await extension.download_piece(webseed_id, piece_info, b"")
            assert result is None
        
        extension.start = original_start

    @pytest.mark.asyncio
    async def test_download_piece_range_session_none_after_start(self):
        """Test download_piece_range with session None after start (line 318-320)."""
        extension = WebSeedExtension()
        webseed_id = extension.add_webseed("http://example.com/torrent")
        
        # Mock session to be None even after start
        with patch.object(extension, "session", None):
            result = await extension.download_piece_range(webseed_id, 0, 1024)
            assert result is None

    @pytest.mark.asyncio
    async def test_health_check_webseed_not_found(self):
        """Test health_check with webseed not found (line 461-463)."""
        extension = WebSeedExtension()
        result = await extension.health_check("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_inactive_webseed(self):
        """Test health_check with inactive webseed (line 467-469)."""
        extension = WebSeedExtension()
        webseed_id = extension.add_webseed("http://example.com/torrent")
        extension.set_webseed_active(webseed_id, False)
        
        result = await extension.health_check(webseed_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_session_none_after_start(self):
        """Test health_check with session None after start (line 479-481)."""
        extension = WebSeedExtension()
        webseed_id = extension.add_webseed("http://example.com/torrent")
        
        # Mock session to be None even after start
        with patch.object(extension, "session", None):
            result = await extension.health_check(webseed_id)
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """Test health_check exception handling (line 485-488)."""
        extension = WebSeedExtension()
        webseed_id = extension.add_webseed("http://example.com/torrent")
        
        # Mock session.get to raise exception
        mock_session = MagicMock()
        mock_session.head = MagicMock(side_effect=Exception("Connection error"))
        extension.session = mock_session
        
        result = await extension.health_check(webseed_id)
        assert result is False

