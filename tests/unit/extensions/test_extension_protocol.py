"""Unit tests for peer-aware extension protocol helpers."""

from __future__ import annotations

import struct

import pytest

from ccbt.extensions.protocol import ExtensionProtocol


def _extension_message_id(message: bytes) -> tuple[int, bytes]:
    payload_len = struct.unpack("!I", message[:4])[0] - 1
    message_id = message[4]
    payload = message[5 : 5 + payload_len]
    return message_id, payload


def test_send_extension_message_prefers_peer_advertised_id():
    """send_extension_message uses peer-advertised extension ID when available."""
    protocol = ExtensionProtocol()
    protocol.register_extension("xet", "1.0")
    peer_id = "peer-1"
    protocol.peer_extensions[peer_id] = protocol._build_peer_extension_state({"m": {"xet": 77}})

    result = protocol.send_extension_message("xet", b"payload", peer_id=peer_id)
    message_id, payload = _extension_message_id(result)

    assert message_id == 77
    assert payload == b"payload"


def test_send_extension_message_falls_back_to_local_id_when_explicitly_requested():
    """send_extension_message falls back to local ID for unknown peer mapping."""
    protocol = ExtensionProtocol()
    local_id = protocol.register_extension("xet", "1.0")
    peer_id = "peer-2"
    protocol.peer_extensions[peer_id] = protocol._build_peer_extension_state({"m": {"other": 3}})

    result = protocol.send_extension_message(
        "xet", b"payload", peer_id=peer_id, local_fallback=True
    )

    message_id, payload = _extension_message_id(result)

    assert message_id == local_id
    assert payload == b"payload"


def test_send_extension_message_without_peer_warns_deprecated_usage():
    """Calling send_extension_message without peer_id triggers deprecation warning."""
    protocol = ExtensionProtocol()
    protocol.register_extension("xet", "1.0")

    with pytest.warns(DeprecationWarning):
        result = protocol.send_extension_message("xet", b"payload")

    message_id, payload = _extension_message_id(result)
    assert message_id == 1
    assert payload == b"payload"


def test_send_extension_message_for_peer_enforces_peer_map_without_fallback():
    """send_extension_message_for_peer requires a peer-specific mapping."""
    protocol = ExtensionProtocol()
    protocol.register_extension("xet", "1.0")
    peer_id = "peer-3"
    protocol.peer_extensions[peer_id] = protocol._build_peer_extension_state({"m": {"other": 3}})

    with pytest.raises(ValueError, match="no id for peer"):
        protocol.send_extension_message_for_peer(peer_id, "xet", b"payload")


def test_send_extension_message_without_local_fallback_requires_peer_mapping():
    """Default send_extension_message behavior requires a peer mapping."""
    protocol = ExtensionProtocol()
    protocol.register_extension("xet", "1.0")
    peer_id = "peer-4"
    protocol.peer_extensions[peer_id] = protocol._build_peer_extension_state({"m": {"other": 3}})

    with pytest.raises(ValueError, match="no id for peer"):
        protocol.send_extension_message("xet", b"payload", peer_id=peer_id)


def test_build_peer_extension_state_normalizes_encryption_preference():
    """Encryption preference from `e` is normalized and retained."""
    protocol = ExtensionProtocol()
    state = protocol._build_peer_extension_state({"m": {"xet": 1}, "e": b"preferred"})
    assert state["e"] == "preferred"


@pytest.mark.asyncio
async def test_handle_extension_handshake_stores_encryption_preference():
    """Incoming extension handshake stores peer encryption preference in peer extensions."""
    protocol = ExtensionProtocol()
    protocol.peer_extensions["peer-1"] = {}
    await protocol.handle_extension_handshake("peer-1", {b"m": {b"xet": 1}, b"e": b"required"})
    peer_state = protocol.get_peer_extensions("peer-1")
    assert peer_state["e"] == "required"
