"""Proxy-related exceptions."""

from __future__ import annotations


class ProxyError(Exception):
    """Base exception for proxy-related errors."""


class ProxyAuthError(ProxyError):
    """Proxy authentication error."""


class ProxyConnectionError(ProxyError):
    """Proxy connection error."""


class ProxyTimeoutError(ProxyError):
    """Proxy timeout error."""


class ProxyConfigurationError(ProxyError):
    """Proxy configuration error."""
