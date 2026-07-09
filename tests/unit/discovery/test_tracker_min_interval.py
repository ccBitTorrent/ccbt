"""Tests for tracker `min interval` parsing and persistence (RC-4/5 fix).

Covers:
- `TrackerResponse.min_interval` field exists on HTTP and UDP dataclasses.
- `_parse_response_async` extracts `b"min interval"` from bencode.
- `_update_tracker_session` persists `min_interval` onto `TrackerSession`.
- Missing `min interval` leaves the field as None (no regression).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.tracker]

from ccbt.core.bencode import encode
from ccbt.discovery.tracker import (
    AsyncTrackerClient,
    TrackerResponse,
    TrackerSession,
)
from ccbt.discovery.tracker_udp_client import TrackerResponse as UDPTrackerResponse


class TestTrackerResponseMinIntervalField:
    """The min_interval field must exist on both TrackerResponse dataclasses."""

    def test_http_tracker_response_has_min_interval_field(self):
        response = TrackerResponse(
            interval=1800,
            peers=[],
            min_interval=300,
        )
        assert response.min_interval == 300

    def test_http_tracker_response_min_interval_defaults_none(self):
        response = TrackerResponse(interval=1800, peers=[])
        assert response.min_interval is None

    def test_udp_tracker_response_has_min_interval_field(self):
        # BEP 15 UDP announce responses do not carry min_interval, but the field
        # exists for type parity so callers can treat both response types uniformly.
        response = UDPTrackerResponse(
            action=None,  # type: ignore[arg-type]
            transaction_id=1,
            interval=1800,
            min_interval=300,
        )
        assert response.min_interval == 300

    def test_udp_tracker_response_min_interval_defaults_none(self):
        response = UDPTrackerResponse(action=None, transaction_id=1)  # type: ignore[arg-type]
        assert response.min_interval is None


class TestParseResponseAsyncMinInterval:
    """_parse_response_async must extract b"min interval" from bencode."""

    @pytest.fixture
    def client(self):
        return AsyncTrackerClient()

    def test_parse_response_async_extracts_min_interval(self, client):
        response_data = encode(
            {
                b"interval": 1800,
                b"peers": b"",
                b"min interval": 300,
            },
        )
        response = client._parse_response_async(response_data)
        assert response.min_interval == 300

    def test_parse_response_async_min_interval_missing_returns_none(self, client):
        response_data = encode(
            {
                b"interval": 1800,
                b"peers": b"",
            },
        )
        response = client._parse_response_async(response_data)
        assert response.min_interval is None

    def test_parse_response_async_min_interval_with_other_optional_fields(self, client):
        response_data = encode(
            {
                b"interval": 1800,
                b"peers": b"",
                b"complete": 100,
                b"incomplete": 50,
                b"min interval": 120,
                b"tracker id": b"test-id",
                b"warning message": b"slow down",
            },
        )
        response = client._parse_response_async(response_data)
        assert response.min_interval == 120
        assert response.complete == 100
        assert response.incomplete == 50
        assert response.tracker_id == "test-id"
        assert response.warning_message == "slow down"


class TestUpdateTrackerSessionMinInterval:
    """_update_tracker_session must persist min_interval onto TrackerSession."""

    def test_update_tracker_session_persists_min_interval(self):
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"
        response = TrackerResponse(
            interval=1800,
            peers=[],
            min_interval=300,
        )
        client._update_tracker_session(url, response)
        session = client.sessions[url]
        assert isinstance(session, TrackerSession)
        assert session.interval == 1800
        assert session.min_interval == 300

    def test_update_tracker_session_leaves_min_interval_none_when_absent(self):
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"
        response = TrackerResponse(interval=1800, peers=[], min_interval=None)
        client._update_tracker_session(url, response)
        session = client.sessions[url]
        assert session.min_interval is None

    def test_update_tracker_session_overwrites_previous_min_interval(self):
        client = AsyncTrackerClient()
        url = "http://tracker.example.com/announce"
        first = TrackerResponse(interval=1800, peers=[], min_interval=300)
        client._update_tracker_session(url, first)
        assert client.sessions[url].min_interval == 300
        # A subsequent response without min_interval must NOT clear the existing value
        # (the response simply didn't advertise it; the prior floor stays in force).
        second = TrackerResponse(interval=1800, peers=[], min_interval=None)
        client._update_tracker_session(url, second)
        assert client.sessions[url].min_interval == 300
