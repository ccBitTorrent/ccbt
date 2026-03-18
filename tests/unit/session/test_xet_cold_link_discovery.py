"""Unit tests for XET cold link peer discovery."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ccbt.models import PeerInfo
from ccbt.session.xet_cold_link_discovery import (
    _parse_source_peers,
    _peers_from_response,
    discover_peers_for_workspace,
)

pytestmark = [pytest.mark.unit, pytest.mark.session]

_WORKSPACE_ID_32 = bytes(32)  # Dummy 32-byte hash


class TestParseSourcePeers:
    """Tests for _parse_source_peers."""

    def test_none_or_empty_returns_empty(self) -> None:
        assert _parse_source_peers(None) == []
        assert _parse_source_peers([]) == []

    def test_ip_port_format(self) -> None:
        assert _parse_source_peers(["192.168.1.1:6881"]) == [("192.168.1.1", 6881)]
        assert _parse_source_peers(["10.0.0.1:7000"]) == [("10.0.0.1", 7000)]

    def test_ip_only_uses_default_port(self) -> None:
        assert _parse_source_peers(["1.2.3.4"]) == [("1.2.3.4", 6881)]

    def test_skips_invalid_entries(self) -> None:
        result = _parse_source_peers(["valid:6881", "bad:port", "", "  "])
        assert result == [("valid", 6881)]

    def test_strips_whitespace(self) -> None:
        assert _parse_source_peers(["  1.2.3.4:6881  "]) == [("1.2.3.4", 6881)]


@pytest.mark.asyncio
async def test_discover_source_peers_only() -> None:
    """Discovery with only source_peers returns them (no DHT)."""
    peers = await discover_peers_for_workspace(
        _WORKSPACE_ID_32,
        trackers=None,
        source_peers=["1.2.3.4:6881", "5.6.7.8"],
        dht_client=None,
        max_peers=50,
        timeout=1.0,
    )
    assert ("1.2.3.4", 6881) in peers
    assert ("5.6.7.8", 6881) in peers
    assert len(peers) == 2


@pytest.mark.asyncio
async def test_discover_dedupes_peers() -> None:
    """Duplicate (ip, port) from source_peers appear only once."""
    peers = await discover_peers_for_workspace(
        _WORKSPACE_ID_32,
        trackers=None,
        source_peers=["1.2.3.4:6881", "1.2.3.4:6881", "1.2.3.4"],
        dht_client=None,
        max_peers=50,
        timeout=1.0,
    )
    assert peers.count(("1.2.3.4", 6881)) == 1
    assert len(peers) == 1


@pytest.mark.asyncio
async def test_discover_respects_max_peers() -> None:
    """Result is capped at max_peers."""
    source = [f"1.2.3.{i}:6881" for i in range(10)]
    peers = await discover_peers_for_workspace(
        _WORKSPACE_ID_32,
        trackers=None,
        source_peers=source,
        dht_client=None,
        max_peers=3,
        timeout=1.0,
    )
    assert len(peers) == 3


@pytest.mark.asyncio
async def test_discover_with_dht_client() -> None:
    """DHT get_peers results are merged after source_peers."""
    dht = AsyncMock()
    dht.get_peers = AsyncMock(return_value=[("10.0.0.1", 6881), ("10.0.0.2", 7000)])

    peers = await discover_peers_for_workspace(
        _WORKSPACE_ID_32,
        trackers=None,
        source_peers=["1.2.3.4:6881"],
        dht_client=dht,
        max_peers=50,
        timeout=5.0,
    )
    assert ("1.2.3.4", 6881) in peers
    assert ("10.0.0.1", 6881) in peers
    assert ("10.0.0.2", 7000) in peers
    dht.get_peers.assert_called_once()


@pytest.mark.asyncio
async def test_discover_dht_none_no_trackers_returns_source_only() -> None:
    """When dht_client is None and no trackers, only source_peers are returned."""
    peers = await discover_peers_for_workspace(
        _WORKSPACE_ID_32,
        trackers=["http://tracker.example/announce"],
        source_peers=["2.3.4.5:6881"],
        dht_client=None,
        max_peers=50,
        timeout=1.0,
    )
    assert peers == [("2.3.4.5", 6881)]


@pytest.mark.asyncio
async def test_discover_dht_dedupes_with_source() -> None:
    """DHT peer that duplicates a source_peer is not added twice."""
    dht = AsyncMock()
    dht.get_peers = AsyncMock(return_value=[("1.2.3.4", 6881)])

    peers = await discover_peers_for_workspace(
        _WORKSPACE_ID_32,
        trackers=None,
        source_peers=["1.2.3.4:6881"],
        dht_client=dht,
        max_peers=50,
        timeout=5.0,
    )
    assert peers.count(("1.2.3.4", 6881)) == 1


@pytest.mark.asyncio
async def test_discover_includes_tracker_peers_when_mock_returns() -> None:
    """When _announce_workspace_trackers is mocked to return peers, they appear in result."""
    from ccbt.session.xet_cold_link_discovery import (
        _announce_workspace_trackers,
        discover_peers_for_workspace,
    )

    with patch(
        "ccbt.session.xet_cold_link_discovery._announce_workspace_trackers",
        new_callable=AsyncMock,
        return_value=[("9.8.7.6", 6881), ("5.4.3.2", 7000)],
    ):
        peers = await discover_peers_for_workspace(
            _WORKSPACE_ID_32,
            trackers=["http://tracker.example/announce"],
            source_peers=None,
            dht_client=None,
            max_peers=50,
            timeout=2.0,
        )
    assert ("9.8.7.6", 6881) in peers
    assert ("5.4.3.2", 7000) in peers


@pytest.mark.asyncio
async def test_announce_workspace_trackers_empty_for_udp_only() -> None:
    """_announce_workspace_trackers only uses HTTP/HTTPS; UDP URLs are filtered out."""
    from ccbt.session.xet_cold_link_discovery import _announce_workspace_trackers

    # No HTTP trackers -> no announce calls, empty result
    peers = await _announce_workspace_trackers(
        _WORKSPACE_ID_32,
        trackers=["udp://tracker.example:80/announce"],
        port=6881,
        timeout=1.0,
    )
    assert peers == []


@pytest.mark.asyncio
async def test_announce_workspace_trackers_empty_for_non_32_workspace() -> None:
    """_announce_workspace_trackers returns empty for non-32-byte workspace_id."""
    from ccbt.session.xet_cold_link_discovery import _announce_workspace_trackers

    peers = await _announce_workspace_trackers(
        b"short",
        trackers=["http://tracker.example/announce"],
        port=6881,
        timeout=1.0,
    )
    assert peers == []


class TestPeersFromResponse:
    """Tests for _peers_from_response (tracker response → (ip, port) list).

    Used when aggregating peers from BEP 15/41-aware tracker clients; supports
    both PeerInfo and dict formats for compatibility with HTTP and UDP responses.
    """

    def test_empty_peers_returns_empty(self) -> None:
        class R:
            peers = []
        assert _peers_from_response(R()) == []

    def test_peer_info_objects(self) -> None:
        class R:
            peers = [
                PeerInfo(ip="1.2.3.4", port=6881),
                PeerInfo(ip="::1", port=7000),
            ]
        assert _peers_from_response(R()) == [("1.2.3.4", 6881), ("::1", 7000)]

    def test_dict_peers(self) -> None:
        class R:
            peers = [
                {"ip": "10.0.0.1", "port": 6969},
                {"host": "10.0.0.2", "port": 6881},
            ]
        assert _peers_from_response(R()) == [("10.0.0.1", 6969), ("10.0.0.2", 6881)]

    def test_none_peers_attribute_returns_empty(self) -> None:
        class R:
            pass
        assert _peers_from_response(R()) == []
