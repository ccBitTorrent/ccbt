"""Tests for BEP 11 PEX message encoding and handling."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from ccbt.core.bencode import BencodeDecoder
from ccbt.extensions.manager import ExtensionManager, ExtensionStatus
from ccbt.extensions.pex import PEXPeer, PeerExchange


@pytest.mark.unit
def test_encode_bep11_payload_includes_flags_and_ipv6_keys():
    """Test that BEP 11 payload includes added.f and IPv6-specific keys."""
    exchange = PeerExchange()

    payload = exchange.encode_bep11_payload(
        added_peers=[
            PEXPeer(ip="192.0.2.1", port=7001, flags=0x01),
            PEXPeer(ip="2001:db8::1", port=7002, flags=0x02),
        ],
        dropped_peers=[
            PEXPeer(ip="198.51.100.2", port=7003, flags=0x03),
            PEXPeer(ip="2001:db8::2", port=7004, flags=0x01),
        ],
    )

    decoded = BencodeDecoder(payload).decode()
    assert isinstance(decoded, dict)
    assert b"added" in decoded
    assert b"added.f" in decoded
    assert b"added6" in decoded
    assert b"added6.f" in decoded
    assert b"dropped" in decoded
    assert b"dropped.f" in decoded
    assert b"dropped6" in decoded
    assert b"dropped6.f" in decoded


@pytest.mark.unit
def test_decode_bep11_payload_roundtrip():
    """Test decode roundtrip for encoded BEP 11 peer payloads."""
    exchange = PeerExchange()
    added_v4 = [
        PEXPeer(ip="198.51.100.10", port=7010, flags=0x01),
    ]
    added_v6 = [
        PEXPeer(ip="2001:db8::10", port=7011, flags=0x02),
    ]
    dropped_v4 = [
        PEXPeer(ip="198.51.100.11", port=7012, flags=0x03),
    ]
    dropped_v6 = [
        PEXPeer(ip="2001:db8::11", port=7013, flags=0x01),
    ]
    payload = exchange.encode_bep11_payload(
        added_peers=added_v4 + added_v6,
        dropped_peers=dropped_v4 + dropped_v6,
    )

    decoded_added_v4, decoded_added_v6, decoded_dropped_v4, decoded_dropped_v6 = (
        exchange.decode_bep11_payload(payload)
    )
    assert decoded_added_v4 == added_v4
    assert decoded_added_v6 == added_v6
    assert decoded_dropped_v4 == dropped_v4
    assert decoded_dropped_v6 == dropped_v6


@pytest.mark.unit
def test_decode_peers_list_accepts_flag_list():
    """Test decode peers list can include per-peer flags."""
    exchange = PeerExchange()
    ip = "203.0.113.10"
    peers_compact = exchange.encode_peers_list(
        [PEXPeer(ip=ip, port=7014, flags=0x7F)], is_ipv6=False
    )
    peers = exchange.decode_peers_list(peers_compact, is_ipv6=False, flags=b"\x05")
    assert len(peers) == 1
    assert peers[0].ip == ip
    assert peers[0].port == 7014
    assert peers[0].flags == 0x05


@pytest.mark.unit
def test_peer_extension_flag_helpers_match_bep11_semantics():
    """BEP 11 flags map 0x01 to encryption preference and 0x02 to seed state."""
    exchange = PeerExchange()

    exchange.set_peer_flags("198.51.100.20", 7001, 0x01)
    exchange.set_peer_flags("198.51.100.21", 7002, 0x02)
    exchange.set_peer_flags("198.51.100.22", 7003, 0x03)

    assert exchange.is_peer_encrypt_preferred("198.51.100.20", 7001) is True
    assert exchange.is_peer_seed("198.51.100.20", 7001) is False

    assert exchange.is_peer_encrypt_preferred("198.51.100.21", 7002) is False
    assert exchange.is_peer_seed("198.51.100.21", 7002) is True

    assert exchange.is_peer_encrypt_preferred("198.51.100.22", 7003) is True
    assert exchange.is_peer_seed("198.51.100.22", 7003) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extension_manager_handles_bep11_pex_added_message():
    """Test ExtensionManager routes BEP 11 added messages to the PEX extension."""
    manager = ExtensionManager()
    manager.extension_states["pex"].status = ExtensionStatus.ACTIVE
    pex_ext = manager.extensions["pex"]
    pex_ext.handle_added_peers = AsyncMock()

    exchange = PeerExchange()
    payload = exchange.encode_bep11_payload(
        added_peers=[PEXPeer(ip="192.0.2.20", port=7001, flags=0x01)]
    )
    await manager.handle_pex_message("peer-id", 7, payload)

    pex_ext.handle_added_peers.assert_called_once()
    called_peers = pex_ext.handle_added_peers.call_args.args[1]
    assert len(called_peers) == 1
    assert called_peers[0].ip == "192.0.2.20"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extension_manager_handles_bep11_pex_dropped_message():
    """Test ExtensionManager routes BEP 11 dropped messages to the PEX extension."""
    manager = ExtensionManager()
    manager.extension_states["pex"].status = ExtensionStatus.ACTIVE
    pex_ext = manager.extensions["pex"]
    pex_ext.handle_dropped_peers = AsyncMock()

    exchange = PeerExchange()
    payload = exchange.encode_bep11_payload(
        dropped_peers=[PEXPeer(ip="192.0.2.30", port=7002, flags=0x02)]
    )
    await manager.handle_pex_message("peer-id", 8, payload)

    pex_ext.handle_dropped_peers.assert_called_once()
    called_peers = pex_ext.handle_dropped_peers.call_args.args[1]
    assert len(called_peers) == 1
    assert called_peers[0].ip == "192.0.2.30"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extension_manager_handles_legacy_prefixed_pex_payload():
    """Legacy payloads with ut_pex-id prefix are decoded by compatibility path."""
    manager = ExtensionManager()
    manager.extension_states["pex"].status = ExtensionStatus.ACTIVE
    pex_ext = manager.extensions["pex"]
    pex_ext.handle_added_peers = AsyncMock()

    peer_exchange = PeerExchange()
    compact_payload = peer_exchange.encode_peers_list(
        [PEXPeer(ip="192.0.2.50", port=7003, flags=0x01)],
        is_ipv6=False,
    )
    pex_id = 9
    payload = bytes([pex_id, 0]) + compact_payload

    await manager.handle_pex_message("peer-id", pex_id, payload)

    pex_ext.handle_added_peers.assert_called_once()
    called_peers = pex_ext.handle_added_peers.call_args.args[1]
    assert len(called_peers) == 1
    assert called_peers[0].ip == "192.0.2.50"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extension_manager_handles_bep11_pex_payload_with_both_added_and_dropped():
    """Payload containing both added and dropped peer groups is routed correctly."""
    manager = ExtensionManager()
    manager.extension_states["pex"].status = ExtensionStatus.ACTIVE
    pex_ext = manager.extensions["pex"]
    pex_ext.handle_added_peers = AsyncMock()
    pex_ext.handle_dropped_peers = AsyncMock()

    exchange = PeerExchange()
    payload = exchange.encode_bep11_payload(
        added_peers=[PEXPeer(ip="192.0.2.40", port=7004, flags=0x01)],
        dropped_peers=[PEXPeer(ip="198.51.100.41", port=7005, flags=0x02)],
    )
    await manager.handle_pex_message("peer-id", 9, payload)

    pex_ext.handle_added_peers.assert_called_once()
    pex_ext.handle_dropped_peers.assert_called_once()
    assert pex_ext.handle_added_peers.call_args.args[1][0].ip == "192.0.2.40"
    assert pex_ext.handle_dropped_peers.call_args.args[1][0].ip == "198.51.100.41"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extension_manager_handles_bep11_payload_with_ipv6_and_flags():
    """IPv6 added/dropped peers with flag bytes are decoded from BEP 11 payload."""
    manager = ExtensionManager()
    manager.extension_states["pex"].status = ExtensionStatus.ACTIVE
    pex_ext = manager.extensions["pex"]
    pex_ext.handle_added_peers = AsyncMock()
    pex_ext.handle_dropped_peers = AsyncMock()

    exchange = PeerExchange()
    payload = exchange.encode_bep11_payload(
        added_peers=[PEXPeer(ip="2001:db8::40", port=7010, flags=0x01)],
        dropped_peers=[PEXPeer(ip="2001:db8::41", port=7011, flags=0x02)],
    )

    await manager.handle_pex_message("peer-id", 12, payload)

    pex_ext.handle_added_peers.assert_called_once()
    pex_ext.handle_dropped_peers.assert_called_once()
    assert pex_ext.handle_added_peers.call_args.args[1][0].ip == "2001:db8::40"
    assert pex_ext.handle_dropped_peers.call_args.args[1][0].ip == "2001:db8::41"
    assert pex_ext.handle_added_peers.call_args.args[1][0].flags == 0x01
    assert pex_ext.handle_dropped_peers.call_args.args[1][0].flags == 0x02


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extension_manager_handles_bep11_payload_with_ipv4_v6_split():
    """BEP 11 payload containing mixed v4/v6 updates routes all peer groups."""
    manager = ExtensionManager()
    manager.extension_states["pex"].status = ExtensionStatus.ACTIVE
    pex_ext = manager.extensions["pex"]
    pex_ext.handle_added_peers = AsyncMock()
    pex_ext.handle_dropped_peers = AsyncMock()

    exchange = PeerExchange()
    payload = exchange.encode_bep11_payload(
        added_peers=[
            PEXPeer(ip="203.0.113.50", port=7015, flags=0x01),
            PEXPeer(ip="2001:db8::50", port=7016, flags=0x02),
        ],
        dropped_peers=[
            PEXPeer(ip="198.51.100.60", port=7017, flags=0x03),
            PEXPeer(ip="2001:db8::60", port=7018, flags=0x01),
        ],
    )

    await manager.handle_pex_message("peer-id", 12, payload)

    pex_ext.handle_added_peers.assert_called_once()
    pex_ext.handle_dropped_peers.assert_called_once()

    added_ips = {peer.ip for peer in pex_ext.handle_added_peers.call_args.args[1]}
    dropped_ips = {peer.ip for peer in pex_ext.handle_dropped_peers.call_args.args[1]}
    assert added_ips == {"203.0.113.50", "2001:db8::50"}
    assert dropped_ips == {"198.51.100.60", "2001:db8::60"}
    added_flags = {peer.flags for peer in pex_ext.handle_added_peers.call_args.args[1]}
    dropped_flags = {peer.flags for peer in pex_ext.handle_dropped_peers.call_args.args[1]}
    assert added_flags == {0x01, 0x02}
    assert dropped_flags == {0x03, 0x01}
