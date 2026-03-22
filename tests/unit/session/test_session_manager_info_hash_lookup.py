"""Tests for inbound info hash lookup helpers."""
from __future__ import annotations

import asyncio

import pytest

from ccbt.peer.peer import ParsedInboundPlainHandshake
from ccbt.session.session import AsyncSessionManager

pytestmark = [pytest.mark.unit, pytest.mark.session]


def test_session_manager_extracts_v1_and_v2_from_parsed_handshake() -> None:
    parsed = ParsedInboundPlainHandshake(
        protocol_len=19,
        protocol=b"BitTorrent protocol",
        reserved_bytes=b"\x00" * 8,
        info_hash_v1=b"\x11" * 20,
        info_hash_v2=b"\x22" * 32,
        peer_id=b"-PC0001-000000000001",
    )

    candidates = AsyncSessionManager._extract_inbound_info_hash_candidates(parsed)

    assert candidates == [b"\x11" * 20, b"\x22" * 32]


@pytest.mark.asyncio
async def test_get_session_for_info_hash_accepts_parsed_handshake() -> None:
    manager = object.__new__(AsyncSessionManager)
    manager.lock = asyncio.Lock()
    session_v1 = object()
    session_v2 = object()
    manager.torrents = {
        b"\x11" * 20: session_v1,
        b"\x22" * 32: session_v2,
    }

    parsed = ParsedInboundPlainHandshake(
        protocol_len=19,
        protocol=b"BitTorrent protocol",
        reserved_bytes=b"\x00" * 8,
        info_hash_v1=b"\x11" * 20,
        info_hash_v2=b"\x22" * 32,
        peer_id=b"-PC0001-000000000001",
    )

    assert await manager.get_session_for_info_hash(parsed) is session_v1
