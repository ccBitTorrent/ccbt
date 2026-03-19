"""Resolve tonic files and tonic links into workspace metadata."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ccbt.core.tonic import TonicFile
from ccbt.core.tonic_link import parse_tonic_link
from ccbt.session.xet_cold_link_discovery import discover_peers_for_workspace
from ccbt.session.xet_cold_link_fetch import fetch_xet_metadata_from_peers
from ccbt.utils.compat import to_thread_compat

logger = logging.getLogger(__name__)

# Default max size for remote .tonic file (10 MiB)
_DEFAULT_MAX_TONIC_URL_SIZE = 10 * 1024 * 1024
_DEFAULT_TONIC_URL_TIMEOUT = 30.0

# Max redirects for URL fetch
_MAX_REDIRECTS = 5


async def _fetch_tonic_bytes_from_url(
    url: str,
    timeout: float = _DEFAULT_TONIC_URL_TIMEOUT,
    max_size: int = _DEFAULT_MAX_TONIC_URL_SIZE,
) -> bytes:
    """Fetch .tonic file bytes from an http(s) URL.

    Args:
        url: HTTP or HTTPS URL to the .tonic file.
        timeout: Request timeout in seconds.
        max_size: Maximum response body size in bytes.

    Returns:
        Response body as bytes.

    Raises:
        RuntimeError: On invalid scheme, timeout, non-2xx, or body too large.
    """
    url_stripped = url.strip()
    lower = url_stripped.lower()
    if not lower.startswith(("http://", "https://")):
        msg = "Invalid URL scheme for .tonic fetch: " + url_stripped[:50]
        raise RuntimeError(msg)

    try:
        import aiohttp
    except ImportError:
        # Fallback: run blocking urllib in thread
        def _fetch_sync() -> bytes:
            import urllib.request

            req = urllib.request.Request(url_stripped, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    msg = (
                        "HTTP "
                        + str(resp.status)
                        + " for .tonic URL: "
                        + url_stripped[:80]
                    )
                    raise RuntimeError(msg)
                body = resp.read(max_size + 1)
                if len(body) > max_size:
                    msg = (
                        ".tonic file from URL exceeds max size ("
                        + str(max_size)
                        + " bytes)"
                    )
                    raise RuntimeError(msg)
                return body

        return await to_thread_compat(_fetch_sync)

    body = b""
    redirect_count = 0
    current_url: Optional[str] = url_stripped

    while current_url is not None and redirect_count <= _MAX_REDIRECTS:
        timeout_ctx = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_ctx) as session:  # noqa: SIM117
            async with session.get(current_url) as resp:
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location")
                    if location and redirect_count < _MAX_REDIRECTS:
                        current_url = location
                        redirect_count += 1
                        continue
                if resp.status != 200:
                    msg = (
                        "HTTP "
                        + str(resp.status)
                        + " for .tonic URL: "
                        + current_url[:80]
                    )
                    raise RuntimeError(msg)
                body = b""
                async for chunk in resp.content.iter_chunked(65536):
                    body += chunk
                    if len(body) > max_size:
                        msg = (
                            ".tonic file from URL exceeds max size ("
                            + str(max_size)
                            + " bytes)"
                        )
                        raise RuntimeError(msg)
                return body
        current_url = None

    msg = "Too many redirects or invalid response for .tonic URL: " + url_stripped[:80]
    raise RuntimeError(msg)


@dataclass
class ResolvedTonicMetadata:
    """Resolved workspace metadata used to start a folder runtime."""

    workspace_id: bytes
    metadata_bytes: bytes
    parsed_metadata: dict[str, Any]
    tonic_source: str


class XetMetadataResolver:
    """Resolve local or linked tonic metadata into a runtime snapshot."""

    def __init__(self) -> None:
        """Initialize tonic parsing helpers for metadata resolution."""
        self._tonic_file = TonicFile()

    async def resolve(
        self,
        tonic_input: str,
        session_manager: Optional[Any] = None,
    ) -> ResolvedTonicMetadata:
        """Resolve a ``.tonic`` file path, remote .tonic URL, or ``tonic?:`` link."""
        if tonic_input.startswith("tonic?:"):
            return await self._resolve_link(
                tonic_input, session_manager=session_manager
            )
        if tonic_input.strip().lower().startswith(("http://", "https://")):
            return await self._resolve_remote_url(tonic_input)
        return await self._resolve_file(tonic_input)

    async def _resolve_file(self, tonic_input: str) -> ResolvedTonicMetadata:
        tonic_path = Path(tonic_input)

        def _read_and_resolve() -> tuple[bytes, str]:
            data = tonic_path.read_bytes()
            resolved = str(tonic_path.resolve())
            return data, resolved

        metadata_bytes, resolved_str = await to_thread_compat(_read_and_resolve)
        parsed_metadata = self._tonic_file.parse_bytes(metadata_bytes)
        workspace_id = self._tonic_file.get_info_hash(parsed_metadata)
        return ResolvedTonicMetadata(
            workspace_id=workspace_id,
            metadata_bytes=metadata_bytes,
            parsed_metadata=parsed_metadata,
            tonic_source=resolved_str,
        )

    async def _resolve_remote_url(self, url: str) -> ResolvedTonicMetadata:
        """Resolve a remote http(s) URL to .tonic metadata."""
        metadata_bytes = await _fetch_tonic_bytes_from_url(
            url,
            timeout=_DEFAULT_TONIC_URL_TIMEOUT,
            max_size=_DEFAULT_MAX_TONIC_URL_SIZE,
        )
        parsed_metadata = self._tonic_file.parse_bytes(metadata_bytes)
        workspace_id = self._tonic_file.get_info_hash(parsed_metadata)
        return ResolvedTonicMetadata(
            workspace_id=workspace_id,
            metadata_bytes=metadata_bytes,
            parsed_metadata=parsed_metadata,
            tonic_source=url,
        )

    async def _resolve_link(
        self,
        tonic_input: str,
        session_manager: Optional[Any] = None,
    ) -> ResolvedTonicMetadata:
        link_info = parse_tonic_link(tonic_input)
        metadata_bytes: Optional[bytes] = None
        workspace_id_hex = link_info.info_hash.hex()

        if session_manager is not None:
            getter = getattr(session_manager, "get_registered_xet_metadata", None)
            if callable(getter):
                metadata_bytes = await getter(workspace_id_hex)
            if metadata_bytes is None:
                fetcher = getattr(session_manager, "fetch_xet_metadata", None)
                if callable(fetcher):
                    metadata_bytes = await fetcher(workspace_id_hex)

        if metadata_bytes is None:
            # Cold link: discover peers and fetch metadata from them
            dht_client = None
            if session_manager is not None:
                get_dht = getattr(session_manager, "get_dht_client_for_xet", None)
                if callable(get_dht):
                    dht_client = get_dht()
            trackers = getattr(link_info, "trackers", None) or []
            source_peers = getattr(link_info, "source_peers", None) or []
            peer_list = await discover_peers_for_workspace(
                link_info.info_hash,
                trackers=trackers,
                source_peers=source_peers,
                dht_client=dht_client,
                max_peers=50,
                timeout=15.0,
            )
            if peer_list:
                metadata_bytes = await fetch_xet_metadata_from_peers(
                    link_info.info_hash,
                    peer_list,
                    timeout=30.0,
                )
            if metadata_bytes is not None and session_manager is not None:
                register = getattr(session_manager, "register_xet_metadata", None)
                if callable(register):
                    await register(workspace_id_hex, metadata_bytes)
            if metadata_bytes is None:
                msg = (
                    "Could not discover peers or fetch metadata for this tonic link. "
                    "Ensure the link is correct and at least one peer is reachable, or use a .tonic file."
                )
                raise RuntimeError(msg)

        if metadata_bytes is None:
            msg = "metadata_bytes unexpectedly None after cold link path"
            raise RuntimeError(msg)
        parsed_metadata = self._tonic_file.parse_bytes(metadata_bytes)
        return ResolvedTonicMetadata(
            workspace_id=link_info.info_hash,
            metadata_bytes=metadata_bytes,
            parsed_metadata=parsed_metadata,
            tonic_source=tonic_input,
        )
