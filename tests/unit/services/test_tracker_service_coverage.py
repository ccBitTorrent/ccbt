"""Additional tests to boost coverage in tracker_service.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ccbt.services.tracker_service import TrackerService


@pytest.mark.unit
@pytest.mark.services
class TestTrackerServiceCoverage:
    """Test uncovered paths in tracker_service.py."""

    @pytest.mark.asyncio
    async def test_scrape_from_udp_tracker(self):
        """Test scrape_from_tracker with UDP tracker (lines 324-343)."""
        service = TrackerService()
        
        # Mock UDP client - patch at the import location
        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.scrape = AsyncMock(return_value={"seeders": 10, "leechers": 5})
        
        with patch(
            "ccbt.discovery.tracker_udp_client.AsyncUDPTrackerClient",
            return_value=mock_client,
        ):
            result = await service.scrape_torrent(
                "udp://tracker.example.com:6969",
                b"x" * 20,
            )
            
            assert result == {"seeders": 10, "leechers": 5}
            mock_client.start.assert_called_once()
            mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_from_http_tracker(self):
        """Test scrape_from_tracker with HTTP tracker (lines 344-359)."""
        service = TrackerService()
        
        # Mock HTTP client - patch at the import location
        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.scrape = AsyncMock(return_value={"seeders": 20, "leechers": 10})
        
        with patch(
            "ccbt.discovery.tracker.AsyncTrackerClient",
            return_value=mock_client,
        ):
            result = await service.scrape_torrent(
                "http://tracker.example.com/announce",
                b"x" * 20,
            )
            
            assert result == {"seeders": 20, "leechers": 10}
            mock_client.start.assert_called_once()
            mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_from_tracker_exception_handling(self):
        """Test scrape_from_tracker exception handling (lines 361-364)."""
        service = TrackerService()
        
        # Mock client that raises exception
        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.scrape = AsyncMock(side_effect=RuntimeError("Scrape failed"))
        
        with patch(
            "ccbt.discovery.tracker_udp_client.AsyncUDPTrackerClient",
            return_value=mock_client,
        ):
            result = await service.scrape_torrent(
                "udp://tracker.example.com:6969",
                b"x" * 20,
            )
            
            # Should return empty dict on error
            assert result == {}
            assert service.failed_scrapes > 0

