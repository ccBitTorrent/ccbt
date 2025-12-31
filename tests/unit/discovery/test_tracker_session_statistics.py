"""Unit tests for TrackerSession statistics storage.

Tests the new statistics fields (last_complete, last_incomplete, last_downloaded, last_scrape_time)
and _update_tracker_session() method to ensure statistics are properly stored from tracker responses.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.tracker]

from ccbt.discovery.tracker import AsyncTrackerClient, TrackerResponse, TrackerSession


class TestTrackerSessionStatistics:
    """Test TrackerSession statistics storage."""

    def test_tracker_session_initialization(self):
        """Test TrackerSession initializes with default statistics values."""
        session = TrackerSession(url="http://tracker.example.com/announce")

        assert session.url == "http://tracker.example.com/announce"
        assert session.last_complete is None
        assert session.last_incomplete is None
        assert session.last_downloaded is None
        assert session.last_scrape_time == 0.0

    def test_tracker_session_statistics_fields_exist(self):
        """Test that TrackerSession has all required statistics fields."""
        session = TrackerSession(url="http://tracker.example.com/announce")

        # Verify fields exist
        assert hasattr(session, "last_complete")
        assert hasattr(session, "last_incomplete")
        assert hasattr(session, "last_downloaded")
        assert hasattr(session, "last_scrape_time")

    def test_update_tracker_session_stores_complete(self):
        """Test _update_tracker_session stores complete (seeders) from response."""
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"

        # Create response with complete count
        response = TrackerResponse(
            interval=1800,
            peers=[],
            complete=100,  # 100 seeders
            incomplete=50,  # 50 leechers
        )

        client._update_tracker_session(url, response)

        # Verify session was created and statistics stored
        assert url in client.sessions
        session = client.sessions[url]
        assert session.last_complete == 100
        assert session.last_incomplete == 50
        assert session.last_scrape_time > 0

    def test_update_tracker_session_stores_incomplete(self):
        """Test _update_tracker_session stores incomplete (leechers) from response."""
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"

        response = TrackerResponse(
            interval=1800,
            peers=[],
            complete=200,
            incomplete=75,
        )

        client._update_tracker_session(url, response)

        session = client.sessions[url]
        assert session.last_incomplete == 75

    def test_update_tracker_session_handles_none_values(self):
        """Test _update_tracker_session handles None values in response."""
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"

        # First update with values
        response1 = TrackerResponse(
            interval=1800,
            peers=[],
            complete=100,
            incomplete=50,
        )
        client._update_tracker_session(url, response1)
        session = client.sessions[url]
        initial_complete = session.last_complete
        initial_incomplete = session.last_incomplete

        # Update with None values (should not overwrite existing values)
        response2 = TrackerResponse(
            interval=1800,
            peers=[],
            complete=None,
            incomplete=None,
        )
        client._update_tracker_session(url, response2)

        # Values should remain unchanged
        assert session.last_complete == initial_complete
        assert session.last_incomplete == initial_incomplete

    def test_update_tracker_session_updates_timestamp(self):
        """Test _update_tracker_session updates last_scrape_time when statistics are received."""
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"

        response = TrackerResponse(
            interval=1800,
            peers=[],
            complete=100,
            incomplete=50,
        )

        before_time = time.time()
        client._update_tracker_session(url, response)
        after_time = time.time()

        session = client.sessions[url]
        assert before_time <= session.last_scrape_time <= after_time

    def test_update_tracker_session_no_timestamp_update_without_statistics(self):
        """Test _update_tracker_session does not update timestamp if no statistics."""
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"

        # First update with statistics
        response1 = TrackerResponse(
            interval=1800,
            peers=[],
            complete=100,
            incomplete=50,
        )
        client._update_tracker_session(url, response1)
        session = client.sessions[url]
        initial_timestamp = session.last_scrape_time

        # Wait a bit
        time.sleep(0.1)

        # Update without statistics
        response2 = TrackerResponse(
            interval=1800,
            peers=[],
            complete=None,
            incomplete=None,
        )
        client._update_tracker_session(url, response2)

        # Timestamp should not be updated
        assert session.last_scrape_time == initial_timestamp

    def test_update_tracker_session_multiple_updates(self):
        """Test _update_tracker_session handles multiple updates correctly."""
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"

        # First update
        response1 = TrackerResponse(
            interval=1800,
            peers=[],
            complete=100,
            incomplete=50,
        )
        client._update_tracker_session(url, response1)
        session = client.sessions[url]
        assert session.last_complete == 100
        assert session.last_incomplete == 50

        # Second update with different values
        response2 = TrackerResponse(
            interval=3600,
            peers=[],
            complete=150,
            incomplete=75,
        )
        client._update_tracker_session(url, response2)

        # Values should be updated
        assert session.last_complete == 150
        assert session.last_incomplete == 75
        assert session.interval == 3600

    def test_update_tracker_session_creates_new_session(self):
        """Test _update_tracker_session creates new session if it doesn't exist."""
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"

        assert url not in client.sessions

        response = TrackerResponse(
            interval=1800,
            peers=[],
            complete=100,
            incomplete=50,
        )
        client._update_tracker_session(url, response)

        assert url in client.sessions
        session = client.sessions[url]
        assert isinstance(session, TrackerSession)
        assert session.url == url

    def test_update_tracker_session_resets_failure_count(self):
        """Test _update_tracker_session resets failure_count on success."""
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"

        # Create session with failure count
        session = TrackerSession(url=url)
        session.failure_count = 5
        client.sessions[url] = session

        response = TrackerResponse(
            interval=1800,
            peers=[],
            complete=100,
            incomplete=50,
        )
        client._update_tracker_session(url, response)

        assert session.failure_count == 0

    def test_tracker_session_statistics_persistence(self):
        """Test that statistics persist across multiple updates."""
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"

        # Update with complete statistics
        response1 = TrackerResponse(
            interval=1800,
            peers=[],
            complete=100,
            incomplete=50,
        )
        client._update_tracker_session(url, response1)
        session = client.sessions[url]

        # Update with only complete (no incomplete)
        response2 = TrackerResponse(
            interval=1800,
            peers=[],
            complete=200,
            incomplete=None,
        )
        client._update_tracker_session(url, response2)

        # Complete should be updated, incomplete should remain
        assert session.last_complete == 200
        assert session.last_incomplete == 50  # Preserved from first update
















































