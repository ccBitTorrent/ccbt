"""Inbound protocol classifier utilities.

This module identifies whether an inbound TCP peer connection is starting with
plain BitTorrent handshake bytes, MSE/PE length-prefixed records, or an
unrecognized envelope.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from ccbt.protocols.bittorrent_v2 import PROTOCOL_STRING, PROTOCOL_STRING_LEN
from ccbt.security.mse_handshake import is_probable_mse_lead


class InboundProtocolKind(Enum):
    """Classification labels for inbound peer protocol leads."""

    BITTORRENT_PLAINTEXT = "BITTORRENT_PLAINTEXT"
    MSE_P2P = "MSE_P2P"
    UNKNOWN = "UNKNOWN"


_PLAINTEXT_PREFIX: Final[bytes] = bytes([PROTOCOL_STRING_LEN]) + PROTOCOL_STRING


def _is_mse_lead(prefix: bytes) -> bool:
    """Return True when prefix is consistent with a post-P3 MSE/PE lead."""
    return is_probable_mse_lead(prefix)


def classify_prefix(prefix: bytes) -> InboundProtocolKind:
    """Classify inbound protocol by its first bytes.

    Args:
        prefix: Already-received bytes from the connection pre-buffer.

    Returns:
        InboundProtocolKind label for the detected protocol.
    """
    if len(prefix) >= len(_PLAINTEXT_PREFIX) and prefix.startswith(_PLAINTEXT_PREFIX):
        return InboundProtocolKind.BITTORRENT_PLAINTEXT

    if _is_mse_lead(prefix):
        return InboundProtocolKind.MSE_P2P

    return InboundProtocolKind.UNKNOWN
