"""SSRF protections for remote URL fetches (tonic metadata, etc.)."""

from __future__ import annotations

import ipaddress
import socket
from typing import Union
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata",
    }
)


def is_public_url(url: str, *, allow_http: bool = True) -> bool:
    """Return True if URL scheme/host are safe for untrusted remote fetch.

    Blocks non-http(s), credentials-in-URL, localhost/link-local/private/
    loopback/multicast/reserved addresses after DNS resolution of the host.
    """
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme == "https" or (scheme == "http" and allow_http):
        pass
    else:
        return False
    if parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or host in _BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        return False
    # Literal IP?
    try:
        ip = ipaddress.ip_address(host)
        return _is_public_ip(ip)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if not _is_public_ip(ip):
            return False
    return True


def _is_public_ip(
    ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address],
) -> bool:
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_safe_remote_url(url: str, *, allow_http: bool = True) -> str:
    """Validate URL or raise RuntimeError (SSRF)."""
    if not is_public_url(url, allow_http=allow_http):
        msg = "Refusing remote fetch: URL fails SSRF checks"
        raise RuntimeError(msg)
    return url.strip()
