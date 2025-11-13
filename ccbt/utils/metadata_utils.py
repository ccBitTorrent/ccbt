"""Metadata utilities (BEP 3) for info-hash calculation and validation."""

from __future__ import annotations

import hashlib
from typing import Any

from ccbt.core.bencode import BencodeEncoder


def calculate_info_hash(info_dict: dict[bytes, Any]) -> bytes:
    """Compute v1 SHA-1 info hash from bencoded info dict (BEP 3)."""
    encoder = BencodeEncoder()
    encoded = encoder.encode(info_dict)
    return hashlib.sha1(encoded).digest()  # nosec - BEP 3 requires SHA-1


def validate_info_dict(
    info_dict: dict[bytes, Any], expected_info_hash: bytes | None
) -> bool:
    """Validate info dict matches expected v1 info hash if provided."""
    if expected_info_hash is None:
        return True
    try:
        return calculate_info_hash(info_dict) == expected_info_hash
    except Exception:
        return False
