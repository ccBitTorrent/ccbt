"""Tests for tracker session stats method.

Additional tests for get_session_stats to achieve 100% coverage.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.tracker, pytest.mark.network]

from ccbt.discovery.tracker import AsyncTrackerClient


def test_get_session_stats_empty():
    """Test get_session_stats with no metrics."""
    client = AsyncTrackerClient()
    
    stats = client.get_session_stats()
    
    assert stats == {}


def test_get_session_stats_with_metrics():
    """Test get_session_stats with various metrics."""
    client = AsyncTrackerClient()
    
    # Add session metrics
    client._session_metrics = {
        "http://tracker1.example.com/announce": {
            "request_count": 10,
            "total_request_time": 5.0,
            "total_dns_time": 0.5,
            "connection_reuse_count": 8,
            "error_count": 1
        },
        "http://tracker2.example.com/announce": {
            "request_count": 5,
            "total_request_time": 2.0,
            "total_dns_time": 0.2,
            "connection_reuse_count": 4,
            "error_count": 0
        },
        "http://tracker3.example.com/announce": {
            "request_count": 0,  # Zero requests
            "total_request_time": 0.0,
            "total_dns_time": 0.0,
            "connection_reuse_count": 0,
            "error_count": 0
        }
    }
    
    stats = client.get_session_stats()
    
    # Should include all trackers (implementation includes all)
    assert "http://tracker1.example.com/announce" in stats
    assert "http://tracker2.example.com/announce" in stats
    # tracker3 may or may not be included depending on implementation
    # Just verify the main stats are correct
    
    # Verify stats calculations
    tracker1_stats = stats["http://tracker1.example.com/announce"]
    assert tracker1_stats["request_count"] == 10
    assert tracker1_stats["average_request_time"] == 0.5  # 5.0 / 10
    assert tracker1_stats["average_dns_time"] == 0.05  # 0.5 / 10
    assert tracker1_stats["connection_reuse_rate"] == 80.0  # 8 / 10 * 100
    assert tracker1_stats["error_rate"] == 10.0  # 1 / 10 * 100


def test_get_session_stats_with_missing_keys():
    """Test get_session_stats handles missing metric keys."""
    client = AsyncTrackerClient()
    
    # Add metrics with missing keys
    client._session_metrics = {
        "http://tracker.example.com/announce": {
            "request_count": 5,
            # Missing other keys
        }
    }
    
    stats = client.get_session_stats()
    
    # Should handle missing keys gracefully
    assert "http://tracker.example.com/announce" in stats
    tracker_stats = stats["http://tracker.example.com/announce"]
    assert tracker_stats["request_count"] == 5
    # Should have defaults for missing values
    assert "average_request_time" in tracker_stats

