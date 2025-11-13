from __future__ import annotations

import asyncio
from typing import Any, List

from ccbt.session.models import SessionContext
from ccbt.session.types import TrackerClientProtocol

try:
    # Prefer the concrete type for better typing where available
    from ccbt.discovery.tracker import TrackerResponse
except Exception:  # pragma: no cover - typing fallback
    TrackerResponse = Any  # type: ignore[misc,assignment]


class AnnounceController:
    """Encapsulates tracker announce flows for initial peer discovery."""

    def __init__(self, ctx: SessionContext, tracker: TrackerClientProtocol) -> None:
        self._ctx = ctx
        self._tracker = tracker
        self._logger = getattr(ctx, "logger", None)
        self._config = getattr(ctx, "config", None)

    async def announce_initial(self) -> List[TrackerResponse]:
        """Perform an initial announce to all known trackers concurrently.

        Returns:
            List of successful tracker responses.

        """
        td = self._prepare_torrent_dict(self._ctx.torrent_data)
        tracker_urls = self._collect_trackers(td)

        if not tracker_urls:
            if self._logger:
                self._logger.warning(
                    "No valid trackers found for %s; skipping initial announce",
                    getattr(getattr(self._ctx, "info", None), "name", "unknown"),
                )
            return []

        # Ensure tracker is started
        try:
            # Concrete client has 'session' attribute; protocol doesn't require it.
            if hasattr(self._tracker, "session"):
                session = self._tracker.session
                if session is None:
                    await self._tracker.start()
            else:
                await self._tracker.start()
        except Exception:
            # Best-effort: log and continue; announce will raise if not available.
            if self._logger:
                self._logger.warning(
                    "Tracker start failed, attempting announce anyway", exc_info=True
                )

        # CRITICAL FIX: Use external port if NAT mapping exists, otherwise use internal port
        # This ensures trackers receive the correct port for routing incoming connections
        listen_port = self._config.network.listen_port if self._config else 6881
        announce_port = listen_port

        # Try to get external port from NAT manager if available
        if (
            self._ctx.session_manager
            and hasattr(self._ctx.session_manager, "nat_manager")
            and self._ctx.session_manager.nat_manager
        ):
            try:
                external_port = (
                    await self._ctx.session_manager.nat_manager.get_external_port(
                        listen_port, "tcp"
                    )
                )
                if external_port is not None:
                    announce_port = external_port
                    if self._logger:
                        self._logger.debug(
                            "Using external port %d (mapped from internal %d) for tracker announce",
                            external_port,
                            listen_port,
                        )
            except Exception:
                # Best-effort: if NAT lookup fails, use internal port
                if self._logger:
                    self._logger.debug(
                        "Failed to get external port from NAT manager, using internal port %d",
                        listen_port,
                        exc_info=True,
                    )

        # Use built-in concurrent multi-tracker announce
        try:
            responses = await self._tracker.announce_to_multiple(
                td,
                tracker_urls,
                port=announce_port,
                event="started",
            )
            if self._logger:
                total_peers = sum(
                    len(getattr(r, "peers", []) or []) for r in responses or []
                )
                self._logger.info(
                    "Initial announce completed: %d tracker(s) responded, %d total peer(s)",
                    len(responses or []),
                    total_peers,
                )
            return responses or []
        except Exception:
            if self._logger:
                self._logger.warning(
                    "Initial multi-tracker announce failed", exc_info=True
                )
            return []

    def _prepare_torrent_dict(self, td: dict[str, Any] | Any) -> dict[str, Any]:
        """Normalize torrent_data to a dict that tracker client expects."""
        if isinstance(td, dict):
            result = dict(td)
        elif hasattr(td, "model_dump") and callable(td.model_dump):
            result = td.model_dump()  # type: ignore[call-arg]
        else:
            # Minimal mapping for objects with attributes
            result = {
                "info_hash": getattr(td, "info_hash", b""),
                "name": getattr(td, "name", "unknown"),
                "announce": getattr(td, "announce", ""),
                "file_info": {
                    "total_length": getattr(td, "total_length", 0),
                },
            }

        # Ensure file_info exists
        if "file_info" not in result or result["file_info"] is None:
            result["file_info"] = {"total_length": 0}
        if not isinstance(result["file_info"], dict):
            result["file_info"] = {"total_length": 0}
        return result

    def _collect_trackers(self, td: dict[str, Any]) -> list[str]:
        """Collect and deduplicate tracker URLs from torrent_data."""
        urls: list[str] = []

        # BEP 12 tiers or flat list from magnet parsing
        announce_list = td.get("announce_list")
        if isinstance(announce_list, list):
            for item in announce_list:
                if isinstance(item, list):
                    urls.extend([u for u in item if isinstance(u, str)])
                elif isinstance(item, str):
                    urls.append(item)

        # Additional trackers key (magnet parsing)
        trackers = td.get("trackers")
        if isinstance(trackers, list):
            urls.extend([u for u in trackers if isinstance(u, str)])

        # Fallback to single announce
        announce = td.get("announce")
        if isinstance(announce, str) and announce.strip():
            urls.append(announce.strip())

        # Deduplicate, basic validation
        seen: set[str] = set()
        unique: list[str] = []
        for u in urls:
            if not isinstance(u, str):
                continue
            v = u.strip()
            if not v or not v.startswith(("http://", "https://", "udp://")):
                continue
            if v not in seen:
                seen.add(v)
                unique.append(v)

        # Optional HTTP/HTTPS fallback set when only UDP provided
        try:
            has_http = any(u.startswith(("http://", "https://")) for u in unique)
            if (
                not has_http
                and self._config
                and getattr(self._config.discovery, "enable_http_trackers", False)
                and not getattr(self._config.discovery, "strict_private_mode", False)
            ):
                fallback = [
                    "https://tracker.opentrackr.org:443/announce",
                    "https://tracker.torrent.eu.org:443/announce",
                    "https://tracker.openbittorrent.com:443/announce",
                    "http://tracker.opentrackr.org:1337/announce",
                    "http://tracker.openbittorrent.com:80/announce",
                ]
                for f in fallback:
                    if f not in seen:
                        seen.add(f)
                        unique.append(f)
        except Exception:
            # Non-fatal
            if self._logger:
                self._logger.debug(
                    "HTTP tracker fallback evaluation failed", exc_info=True
                )

        return unique


class AnnounceLoop:
    """Periodic tracker announce loop extracted from session."""

    def __init__(self, session: Any) -> None:
        self.s = session  # AsyncTorrentSession instance

    async def run(self) -> None:
        announce_interval = self.s.config.network.announce_interval
        while not self.s._stop_event.is_set():
            # Set connecting state
            self.s._tracker_connection_status = "connecting"
            try:
                # Normalize torrent_data for tracker usage
                if isinstance(self.s.torrent_data, dict):
                    td: dict[str, Any] = dict(self.s.torrent_data)
                    if "file_info" not in td:
                        if hasattr(self.s.torrent_data, "file_info"):
                            td["file_info"] = getattr(
                                self.s.torrent_data, "file_info", {}
                            )
                        elif hasattr(self.s.torrent_data, "total_length"):
                            td["file_info"] = {
                                "total_length": getattr(
                                    self.s.torrent_data, "total_length", 0
                                )
                            }
                else:
                    # Minimal mapping for non-dict types
                    td = {
                        "info_hash": getattr(self.s.torrent_data, "info_hash", b""),
                        "name": getattr(self.s.torrent_data, "name", "unknown"),
                        "announce": getattr(self.s.torrent_data, "announce", ""),
                        "file_info": {
                            "total_length": getattr(
                                self.s.torrent_data, "total_length", 0
                            ),
                        },
                    }

                # Normalize tracker URL if available
                if (
                    isinstance(td, dict)
                    and "announce" in td
                    and isinstance(td.get("announce"), str)
                    and hasattr(self.s.tracker, "_normalize_tracker_url")
                ):
                    try:
                        original_obj = td["announce"]
                        original = original_obj if isinstance(original_obj, str) else ""
                        if original and original.strip():
                            td["announce"] = self.s.tracker.normalize_tracker_url(
                                original
                            )
                    except Exception:
                        # Best-effort; continue with original URL
                        pass

                # Validate required fields
                if not td or (isinstance(td, dict) and not td.get("info_hash")):
                    self.s.logger.warning("Invalid torrent_data for announce, skipping")
                    await asyncio.sleep(announce_interval)
                    continue

                announce_url = td.get("announce", "") if isinstance(td, dict) else ""
                if not isinstance(announce_url, str) or not announce_url.strip():
                    self.s.logger.debug(
                        "No tracker URL available, skipping announce (using DHT/PEX)"
                    )
                    await asyncio.sleep(announce_interval)
                    continue

                # CRITICAL FIX: Use external port if NAT mapping exists, otherwise use internal port
                listen_port = self.s.config.network.listen_port
                announce_port = listen_port

                # Try to get external port from NAT manager if available
                if (
                    self.s.session_manager
                    and hasattr(self.s.session_manager, "nat_manager")
                    and self.s.session_manager.nat_manager
                ):
                    try:
                        external_port = (
                            await self.s.session_manager.nat_manager.get_external_port(
                                listen_port, "tcp"
                            )
                        )
                        if external_port is not None:
                            announce_port = external_port
                            self.s.logger.debug(
                                "Using external port %d (mapped from internal %d) for periodic announce",
                                external_port,
                                listen_port,
                            )
                    except Exception:
                        # Best-effort: if NAT lookup fails, use internal port
                        self.s.logger.debug(
                            "Failed to get external port from NAT manager, using internal port %d",
                            listen_port,
                            exc_info=True,
                        )

                # Perform announce
                response = await self.s.tracker.announce(td, port=announce_port)

                if not response:
                    self.s.logger.warning("Tracker announce returned None response")
                    self.s._tracker_connection_status = "error"
                    self.s._last_tracker_error = "Tracker returned None response"
                    await asyncio.sleep(announce_interval)
                    continue

                # Success
                self.s._tracker_connection_status = "connected"
                self.s._last_tracker_error = None
                if hasattr(self.s, "_tracker_consecutive_failures"):
                    self.s._tracker_consecutive_failures = 0  # type: ignore[attr-defined]

                # Connect peers to the existing download path when running
                if (
                    response
                    and hasattr(response, "peers")
                    and response.peers
                    and self.s.download_manager
                ):
                    # CRITICAL FIX: Check if peer manager exists (may have been initialized early)
                    has_peer_manager = (
                        hasattr(self.s.download_manager, "peer_manager")
                        and self.s.download_manager.peer_manager is not None
                    )

                    download_started = (
                        hasattr(self.s.download_manager, "_download_started")
                        and getattr(self.s.download_manager, "_download_started", False)
                    ) or has_peer_manager

                    # CRITICAL FIX: If peer manager exists, connect peers directly
                    if has_peer_manager:
                        peer_list = []
                        for p in response.peers:
                            try:
                                if hasattr(p, "ip") and hasattr(p, "port"):
                                    peer_list.append(
                                        {
                                            "ip": p.ip,
                                            "port": p.port,
                                            "peer_source": "tracker",
                                        }
                                    )
                                elif isinstance(p, dict) and "ip" in p and "port" in p:
                                    peer_list.append(
                                        {
                                            "ip": str(p["ip"]),
                                            "port": int(p["port"]),
                                            "peer_source": "tracker",
                                        }
                                    )
                                else:
                                    self.s.logger.debug(
                                        "Skipping invalid peer from tracker response: %s (type: %s)",
                                        p,
                                        type(p).__name__,
                                    )
                            except (ValueError, TypeError, KeyError) as peer_error:
                                self.s.logger.debug(
                                    "Error processing peer from tracker: %s (error: %s)",
                                    p,
                                    peer_error,
                                )

                        if peer_list:
                            self.s.logger.info(
                                "Connecting %d peer(s) from tracker to peer manager for %s",
                                len(peer_list),
                                self.s.info.name,
                            )
                            try:
                                # Connect peers to existing peer manager
                                await self.s.download_manager.peer_manager.connect_to_peers(
                                    peer_list
                                )  # type: ignore[misc]
                                self.s.logger.info(
                                    "Successfully initiated connection to %d peer(s) from tracker for %s",
                                    len(peer_list),
                                    self.s.info.name,
                                )
                                # CRITICAL FIX: Verify connections after a delay
                                await asyncio.sleep(
                                    1.0
                                )  # Give connections time to establish
                                peer_manager = self.s.download_manager.peer_manager
                                if peer_manager and hasattr(
                                    peer_manager, "connections"
                                ):
                                    active_count = len(
                                        [
                                            c
                                            for c in peer_manager.connections.values()
                                            if c.is_active()
                                        ]
                                    )
                                    self.s.logger.debug(
                                        "Tracker peer connection status for %s: %d active connections after adding %d peers",
                                        self.s.info.name,
                                        active_count,
                                        len(peer_list),
                                    )
                            except Exception as e:
                                self.s.logger.warning(
                                    "Failed to connect %d peers from tracker for %s: %s",
                                    len(peer_list),
                                    self.s.info.name,
                                    e,
                                    exc_info=True,
                                )
                        else:
                            self.s.logger.debug(
                                "No valid peers to connect from tracker response for %s (response had %d peer objects)",
                                self.s.info.name,
                                len(response.peers) if response.peers else 0,
                            )
                    elif download_started:
                        # Fallback: use helper if download started but no peer manager
                        peer_list = [
                            {
                                "ip": p.ip
                                if hasattr(p, "ip")
                                else str(p.get("ip", "")),
                                "port": p.port
                                if hasattr(p, "port")
                                else int(p.get("port", 0)),
                                "peer_source": "tracker",
                            }
                            for p in response.peers
                            if (hasattr(p, "ip") and hasattr(p, "port"))
                            or (isinstance(p, dict) and "ip" in p and "port" in p)
                        ]
                        if peer_list:
                            from ccbt.session.peers import PeerConnectionHelper

                            helper = PeerConnectionHelper(self.s)
                            await helper.connect_peers_to_download(peer_list)
                    elif hasattr(self.s.download_manager, "add_peers") and callable(
                        self.s.download_manager.add_peers
                    ):
                        # Fallback: use add_peers method if available
                        add_peers_method = self.s.download_manager.add_peers
                        if asyncio.iscoroutinefunction(add_peers_method):
                            await add_peers_method(response.peers)  # type: ignore[misc]
                        else:
                            add_peers_method(response.peers)  # type: ignore[misc]

                # Wait until next tick
                await asyncio.sleep(announce_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Failure/backoff management (simplified)
                consecutive = getattr(self.s, "_tracker_consecutive_failures", 0) + 1
                self.s._tracker_consecutive_failures = consecutive  # type: ignore[attr-defined]
                self.s._tracker_connection_status = "error"
                self.s._last_tracker_error = f"Tracker announce failed: {e}"
                is_net = (
                    "Network error" in str(e)
                    or "Connection" in type(e).__name__
                    or "Timeout" in type(e).__name__
                    or "timeout" in str(e).lower()
                )
                if is_net and consecutive > 3:
                    backoff = min(30 * (2 ** min(consecutive - 1, 4)), 300)
                elif is_net:
                    backoff = 30
                else:
                    backoff = min(60 * (2 ** min(consecutive - 1, 3)), 300)
                await asyncio.sleep(backoff)
