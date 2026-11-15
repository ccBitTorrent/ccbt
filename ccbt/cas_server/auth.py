"""Scoped static-token auth and signed transfer URLs for the CAS server.

Tokens are configured as a mapping of token string -> scopes, where
scopes are drawn from {"read", "write"}. Transfer (xorb byte) URLs are
signed with HMAC-SHA256 over "{xorb_hex}:{expiry}" so reconstruction
responses can hand out capability URLs that need no bearer token.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional

READ = "read"
WRITE = "write"


class TokenAuth:
    """Public class."""

    def __init__(self, tokens: Optional[dict[str, set[str]]] = None) -> None:
        # No tokens configured -> open mode (local development only).
        """Initialize instance."""
        self.tokens = tokens or {}
        self.open_mode = not self.tokens

    def check(self, authorization: Optional[str], scope: str) -> bool:
        """Public method."""
        if self.open_mode:
            return True
        if not authorization or not authorization.startswith("Bearer "):
            return False
        token = authorization[len("Bearer ") :].strip()
        scopes = self.tokens.get(token)
        return scopes is not None and scope in scopes


def sign_transfer_url(secret: bytes, xorb_hex: str, ttl_seconds: int = 3600) -> str:
    """Public function."""
    exp = int(time.time()) + ttl_seconds
    sig = hmac.new(secret, f"{xorb_hex}:{exp}".encode(), hashlib.sha256).hexdigest()
    return f"exp={exp}&sig={sig}"


def verify_transfer_signature(
    secret: bytes, xorb_hex: str, exp: Optional[str], sig: Optional[str]
) -> bool:
    """Public function."""
    if not exp or not sig:
        return False
    try:
        exp_i = int(exp)
    except ValueError:
        return False
    if exp_i < int(time.time()):
        return False
    expected = hmac.new(
        secret, f"{xorb_hex}:{exp_i}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig)
