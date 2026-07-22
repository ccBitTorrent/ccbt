"""Tests for inbound protocol classification."""

from __future__ import annotations

import struct

import pytest

from ccbt.peer.inbound_protocol_classifier import (
    InboundProtocolKind,
    classify_prefix,
)
from ccbt.protocols.bittorrent_v2 import PROTOCOL_STRING, PROTOCOL_STRING_LEN

pytestmark = [pytest.mark.unit, pytest.mark.peer]


def _pack_mse_prefix(message_length: int = 96) -> bytes:
    """Build a deterministic MSE lead prefix."""
    return struct.pack("!I", message_length) + b"\x00"


def test_classify_prefix_plaintext() -> None:
    prefix = bytes([PROTOCOL_STRING_LEN]) + PROTOCOL_STRING + b"\x00" * 8
    assert classify_prefix(prefix) is InboundProtocolKind.BITTORRENT_PLAINTEXT


def test_classify_prefix_mse_p2p_skeye() -> None:
    prefix = _pack_mse_prefix(message_length=96)
    assert classify_prefix(prefix) is InboundProtocolKind.MSE_P2P


def test_classify_prefix_mse_p2p_rkeye() -> None:
    prefix = _pack_mse_prefix(message_length=128)
    assert classify_prefix(prefix) is InboundProtocolKind.MSE_P2P


def test_classify_prefix_mse_p2p_crypto() -> None:
    prefix = _pack_mse_prefix(message_length=200)
    assert classify_prefix(prefix) is InboundProtocolKind.MSE_P2P


def test_classify_prefix_mse_p2p_crypto_frame_lead() -> None:
    prefix = struct.pack("!I", 200) + bytes([0x04, 0x00])
    assert classify_prefix(prefix) is InboundProtocolKind.MSE_P2P


def test_classify_prefix_mse_p2p_small_crypto_frame_lead() -> None:
    prefix = struct.pack("!I", 8) + bytes([0x02, 0x00])
    assert classify_prefix(prefix) is InboundProtocolKind.MSE_P2P


def test_classify_prefix_unknown_when_plain_prefix_incomplete() -> None:
    prefix = bytes([PROTOCOL_STRING_LEN]) + PROTOCOL_STRING[:5]
    assert classify_prefix(prefix) is InboundProtocolKind.UNKNOWN


def test_classify_prefix_unknown_when_mse_too_small_length() -> None:
    assert (
        classify_prefix(struct.pack("!I", 2) + b"\x00")
        is InboundProtocolKind.UNKNOWN
    )


def test_classify_prefix_unknown_when_mse_too_large_length() -> None:
    assert (
        classify_prefix(struct.pack("!I", 5000) + b"\x02")
        is InboundProtocolKind.UNKNOWN
    )


def test_classify_prefix_unknown_when_mse_too_short_length_field() -> None:
    assert (
        classify_prefix(struct.pack("!I", 64) + b"\x00")
        is InboundProtocolKind.UNKNOWN
    )

