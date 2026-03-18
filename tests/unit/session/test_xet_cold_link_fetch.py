"""Unit tests for XET cold link metadata fetch from peers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ccbt.core.tonic import TonicFile
from ccbt.models import XetTorrentMetadata
from ccbt.session.xet_cold_link_fetch import (
    _normalize_peers,
    fetch_xet_metadata_from_peers,
)

pytestmark = [pytest.mark.unit, pytest.mark.session]


def _build_minimal_tonic_bytes(folder_name: str) -> tuple[bytes, bytes]:
    tonic_file = TonicFile()
    tonic_bytes = tonic_file.create(
        folder_name=folder_name,
        xet_metadata=XetTorrentMetadata(),
        sync_mode="best_effort",
    )
    parsed = tonic_file.parse_bytes(tonic_bytes)
    return tonic_bytes, tonic_file.get_info_hash(parsed)


class TestNormalizePeers:
    """Tests for _normalize_peers."""

    def test_empty_list_returns_empty(self) -> None:
        assert _normalize_peers([]) == []

    def test_tuples_ip_port(self) -> None:
        assert _normalize_peers([("192.168.1.1", 6881), ("10.0.0.1", 7000)]) == [
            ("192.168.1.1", 6881),
            ("10.0.0.1", 7000),
        ]

    def test_lists_ip_port(self) -> None:
        assert _normalize_peers([["1.2.3.4", 6881]]) == [("1.2.3.4", 6881)]

    def test_dicts_ip_port(self) -> None:
        assert _normalize_peers([{"ip": "1.2.3.4", "port": 6881}]) == [
            ("1.2.3.4", 6881),
        ]
        assert _normalize_peers([{"host": "5.6.7.8", "port": 9999}]) == [
            ("5.6.7.8", 9999),
        ]

    def test_skips_invalid_entries(self) -> None:
        result = _normalize_peers([
            ("ok", 6881),
            [],
            ("short",),
            {"ip": "a"},
            None,
            "string",
        ])
        assert result == [("ok", 6881)]


@pytest.mark.asyncio
async def test_fetch_returns_none_for_empty_peers() -> None:
    """Empty peer list should return None."""
    _, info_hash = _build_minimal_tonic_bytes("ws")
    result = await fetch_xet_metadata_from_peers(info_hash, [], timeout=1.0)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_returns_none_for_invalid_workspace_id() -> None:
    """Non-32-byte workspace_id should return None."""
    result = await fetch_xet_metadata_from_peers(b"short", [("1.2.3.4", 6881)], timeout=1.0)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_returns_none_when_all_peers_fail() -> None:
    """When no peer returns metadata, result is None (connection/timeout to invalid host)."""
    _, info_hash = _build_minimal_tonic_bytes("ws")
    # Use an address that will not accept connections (or use a very short timeout)
    result = await fetch_xet_metadata_from_peers(
        info_hash,
        [("127.0.0.1", 37999)],  # Unlikely to have a listener
        timeout=0.5,
    )
    assert result is None


@pytest.mark.asyncio
async def test_fetch_success_when_mock_returns_metadata() -> None:
    """When _connect_and_fetch_one returns metadata bytes, fetch returns them."""
    metadata_bytes, info_hash = _build_minimal_tonic_bytes("cold-ws")

    async def fake_connect(_wid: bytes, ip: str, port: int, _timeout: float) -> bytes | None:
        if ip == "1.2.3.4" and port == 6881:
            return metadata_bytes
        return None

    with patch(
        "ccbt.session.xet_cold_link_fetch._connect_and_fetch_one",
        side_effect=fake_connect,
    ):
        result = await fetch_xet_metadata_from_peers(
            info_hash,
            [("1.2.3.4", 6881)],
            timeout=5.0,
        )
    assert result == metadata_bytes


@pytest.mark.asyncio
async def test_fetch_returns_first_successful_peer() -> None:
    """First peer that returns metadata wins."""
    metadata_bytes, info_hash = _build_minimal_tonic_bytes("cold-ws")
    call_order: list[tuple[str, int]] = []

    async def fake_connect(_wid: bytes, ip: str, port: int, _timeout: float) -> bytes | None:
        call_order.append((ip, port))
        if (ip, port) == ("1.2.3.4", 6881):
            return None
        if (ip, port) == ("5.6.7.8", 6881):
            return metadata_bytes
        return None

    with patch(
        "ccbt.session.xet_cold_link_fetch._connect_and_fetch_one",
        side_effect=fake_connect,
    ):
        result = await fetch_xet_metadata_from_peers(
            info_hash,
            [("1.2.3.4", 6881), ("5.6.7.8", 6881)],
            timeout=5.0,
        )
    assert result == metadata_bytes
    assert len(call_order) >= 2
