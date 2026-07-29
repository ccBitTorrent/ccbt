"""Shared helpers for security posture checks in CLI surfaces."""

from __future__ import annotations

from typing import Any


def is_strict_ssl_posture(ssl_cfg: Any) -> bool:
    """Return True when strict SSL posture is active but verification is disabled."""
    strict_transport = bool(getattr(ssl_cfg, "enable_ssl_trackers", False)) or (
        bool(getattr(ssl_cfg, "enable_ssl_peers", False))
        and not bool(getattr(ssl_cfg, "ssl_allow_insecure_peers", False))
    )
    return strict_transport and not bool(
        getattr(ssl_cfg, "ssl_verify_certificates", True)
    )
