"""Tracker announcement management.

This module handles periodic announcements to trackers, including
announce loops, scrape operations, and tracker health monitoring.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Optional, Union

from ccbt.session.models import SessionContext

if TYPE_CHECKING:
    from ccbt.session.types import TrackerClientProtocol

try:
    # Prefer the concrete type for better typing where available
    from ccbt.discovery.tracker import TrackerResponse
except Exception:  # pragma: no cover - typing fallback
    TrackerResponse = Any  # type: ignore[misc,assignment]


def _normalize_tracker_peer(
    peer: Any, utility_signal: float = 0.0
) -> Optional[dict[str, Any]]:
    """Normalize a tracker peer payload to a consistent dictionary format."""
    try:
        if hasattr(peer, "ip") and hasattr(peer, "port"):
            ip_value = peer.ip
            port_value = peer.port
            peer_ssl = getattr(peer, "ssl_capable", None)
            tracker_encryption_preference = getattr(
                peer, "_tracker_encryption_preference", None
            )
        elif isinstance(peer, dict):
            ip_value = peer.get("ip")
            port_value = peer.get("port")
            peer_ssl = peer.get("ssl_capable")
            tracker_encryption_preference = peer.get("_tracker_encryption_preference")
        else:
            return None
        if ip_value is None or port_value is None:
            return None
        port_int = int(port_value)
        if port_int <= 0 or port_int > 65535:
            return None
        try:
            utility = float(utility_signal)
        except (TypeError, ValueError):
            utility = 0.0
        utility = max(0.0, min(1.0, utility))
        return {
            "ip": str(ip_value),
            "port": port_int,
            "peer_source": "tracker",
            "ssl_capable": peer_ssl,
            "_tracker_encryption_preference": tracker_encryption_preference,
            "_tracker_seed_ratio": utility,
            "_replacement_priority": utility + (0.1 if bool(peer_ssl) else 0.0),
        }
    except (ValueError, TypeError):
        return None


def _queue_tracker_peers_for_later(
    session: Any,
    peers: Optional[Any],
    *,
    peer_source: str = "tracker",
) -> int:
    """Queue normalized tracker peers for later connection."""
    if session is None or not peers:
        return 0

    peer_list: list[dict[str, Any]] = []
    for p in peers:
        normalized = _normalize_tracker_peer(p, utility_signal=0.0)
        if normalized is None:
            continue
        normalized["peer_source"] = peer_source
        if isinstance(p, dict):
            prior_priority = float(p.get("_replacement_priority", 0.0))
            normalized["_replacement_priority"] = max(
                float(normalized.get("_replacement_priority", 0.0)),
                prior_priority,
            )
            prior_seed_ratio = float(p.get("_tracker_seed_ratio", 0.0))
            if prior_seed_ratio > 0:
                normalized["_tracker_seed_ratio"] = prior_seed_ratio
        peer_list.append(normalized)

    if not peer_list:
        return 0

    peer_list.sort(
        key=lambda peer: (
            float(peer.get("_replacement_priority", 0.0)),
            bool(peer.get("ssl_capable")),
            peer.get("ip"),
            peer.get("port"),
        ),
        reverse=True,
    )
    queued_at = time.time()
    for peer in peer_list:
        peer["_queued_at"] = queued_at
        session.add_queued_peer(peer)
    return len(peer_list)


class AnnounceController:
    """Encapsulates tracker announce flows for initial peer discovery."""

    def __init__(self, ctx: SessionContext, tracker: TrackerClientProtocol) -> None:
        """Initialize announce controller.

        Args:
            ctx: Session context containing logger and config
            tracker: Tracker client protocol instance

        """
        self._ctx = ctx
        self._tracker = tracker
        self._logger = getattr(ctx, "logger", None)
        self._config = getattr(ctx, "config", None)

    async def announce_initial(self) -> list[TrackerResponse]:
        """Perform an initial announce to all known trackers concurrently.

        Returns:
            List of successful tracker responses.

        """
        td = self.prepare_torrent_dict(self._ctx.torrent_data)
        tracker_urls = self.collect_trackers(td)

        # Note: Log collected trackers for debugging
        if self._logger:
            self._logger.debug(
                "TRACKER_COLLECTION: Collected %d tracker(s) from torrent_data (announce_list=%s, trackers=%s, announce=%s)",
                len(tracker_urls),
                bool(td.get("announce_list")),
                bool(td.get("trackers")),
                bool(td.get("announce")),
            )
            if tracker_urls:
                self._logger.debug(
                    "TRACKER_COLLECTION: Trackers: %s",
                    ", ".join(tracker_urls[:10])
                    + ("..." if len(tracker_urls) > 10 else ""),
                )

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

        # Note: Use external port if NAT mapping exists, otherwise use internal port
        # This ensures trackers receive the correct port for routing incoming connections
        # Use listen_port_tcp (or listen_port as fallback) to match actual configured port
        # Try to get config from context first, then from session manager as fallback
        config = self._config
        if not config and self._ctx.session_manager:
            config = getattr(self._ctx.session_manager, "config", None)

        if config:
            listen_port_tcp = getattr(config.network, "listen_port_tcp", None)
            listen_port = getattr(config.network, "listen_port", 6881)
            listen_port = listen_port_tcp or listen_port
            if self._logger:
                self._logger.debug(
                    "Port selection: listen_port_tcp=%s, listen_port=%s, selected=%d (config source: %s)",
                    listen_port_tcp,
                    getattr(config.network, "listen_port", None),
                    listen_port,
                    "context" if self._config else "session_manager",
                )
        # Note: Try to get port from session_manager config if available
        # Avoid hardcoded 6881 fallback - use actual configured port
        elif (
            self._ctx
            and self._ctx.session_manager
            and hasattr(self._ctx.session_manager, "config")
        ):
            config = self._ctx.session_manager.config
            listen_port = (
                getattr(config.network, "listen_port_tcp", None)
                or getattr(config.network, "listen_port", None)
                or 6881  # Last resort fallback
            )
            if self._logger:
                self._logger.debug(
                    "No context config, using session_manager config port: %d",
                    listen_port,
                )
        else:
            listen_port = 6881  # Last resort fallback
            if self._logger:
                self._logger.warning(
                    "No config available (context=%s, session_manager=%s), using default port 6881. "
                    "This may cause port mismatch issues. Ensure config is properly initialized.",
                    self._config is not None,
                    self._ctx.session_manager is not None if self._ctx else False,
                )
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
                # Note: Log warning if external port lookup fails
                # This indicates NAT mapping may not exist for the configured port
                elif self._logger:
                    self._logger.warning(
                        "NAT external port lookup failed for internal port %d (protocol=tcp). "
                        "Tracker will announce internal port %d, which may prevent peer connections if behind NAT. "
                        "Verify NAT port mapping is active for TCP port %d.",
                        listen_port,
                        announce_port,
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
        # Note: Log the port being used for tracker announce
        if self._logger:
            self._logger.debug(
                "Calling tracker.announce_to_multiple with port=%d (listen_port=%d, announce_port=%d)",
                announce_port,
                listen_port,
                announce_port,
            )
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
                self._logger.debug(
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

    def get_or_create_peer_id(self, torrent_data: dict[str, Any]) -> Optional[bytes]:
        """Return a stable tracker peer ID for this torrent dict."""
        peer_id = torrent_data.get("peer_id")
        if isinstance(peer_id, bytes) and peer_id:
            return peer_id

        generate_peer_id = getattr(self._tracker, "_generate_peer_id", None)
        if callable(generate_peer_id):
            peer_id = generate_peer_id()
            if isinstance(peer_id, bytes) and peer_id:
                torrent_data["peer_id"] = peer_id
                return peer_id
        return None

    def prepare_torrent_dict(self, td: Union[dict[str, Any], Any]) -> dict[str, Any]:
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
        self.get_or_create_peer_id(result)
        return result

    def collect_trackers(self, td: dict[str, Any]) -> list[str]:
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

        # Get healthy trackers from health manager (prioritize these)
        healthy_trackers: list[str] = []
        try:
            get_healthy_trackers = getattr(self._tracker, "get_healthy_trackers", None)
            if get_healthy_trackers is not None:
                # Get healthy trackers, excluding ones we already have from torrent
                healthy_trackers = get_healthy_trackers(set(unique))
        except Exception as e:
            if self._logger:
                self._logger.debug("Failed to get healthy trackers: %s", e)

        # Combine: healthy trackers first, then original torrent trackers
        combined_trackers = healthy_trackers + unique

        # Add fallback trackers if needed
        try:
            has_http = any(
                u.startswith(("http://", "https://")) for u in combined_trackers
            )
            if (
                not has_http
                and self._config
                and getattr(self._config.discovery, "enable_http_trackers", False)
                and not getattr(self._config.discovery, "strict_private_mode", False)
            ):
                # Get fallback trackers from health manager
                fallback_trackers = []
                try:
                    get_fallback_trackers = getattr(
                        self._tracker, "get_fallback_trackers", None
                    )
                    if get_fallback_trackers is not None:
                        fallback_trackers = get_fallback_trackers(
                            set(combined_trackers)
                        )
                    else:
                        fallback_trackers = [
                            "https://tracker.opentrackr.org:443/announce",
                            "https://tracker.torrent.eu.org:443/announce",
                            "https://tracker.openbittorrent.com:443/announce",
                            "http://tracker.opentrackr.org:1337/announce",
                            "http://tracker.openbittorrent.com:80/announce",
                        ]
                except Exception:
                    fallback_trackers = [
                        "https://tracker.opentrackr.org:443/announce",
                        "https://tracker.torrent.eu.org:443/announce",
                        "https://tracker.openbittorrent.com:443/announce",
                        "http://tracker.opentrackr.org:1337/announce",
                        "http://tracker.openbittorrent.com:80/announce",
                    ]

                # Add fallback trackers not already in the list
                for f in fallback_trackers:
                    if f not in seen:
                        seen.add(f)
                        combined_trackers.append(f)
        except Exception:
            # Non-fatal
            if self._logger:
                self._logger.debug(
                    "HTTP tracker fallback evaluation failed", exc_info=True
                )

        # Final deduplication
        final_seen: set[str] = set()
        final_trackers: list[str] = []
        for u in combined_trackers:
            if u not in final_seen:
                final_seen.add(u)
                final_trackers.append(u)

        return final_trackers


class AnnounceLoop:
    """Periodic tracker announce loop extracted from session."""

    def __init__(self, session: Any) -> None:
        """Initialize announce loop.

        Args:
            session: AsyncTorrentSession instance

        """
        self.s = session  # AsyncTorrentSession instance

    def _get_tracker_peer_id(self) -> Optional[bytes]:
        """Return the stable tracker peer ID cached on the session, if any."""
        peer_id = getattr(self.s, "_tracker_peer_id", None)
        return peer_id if isinstance(peer_id, bytes) else None

    def _cache_tracker_peer_id(self, peer_id: bytes) -> None:
        """Cache the stable tracker peer ID on the session."""
        vars(self.s)["_tracker_peer_id"] = peer_id

    def _initial_announce_sent(self) -> bool:
        """Return whether the initial tracker announce was already sent."""
        return bool(getattr(self.s, "_initial_tracker_announce_sent", False))

    def _mark_initial_announce_sent(self) -> None:
        """Record that the initial tracker announce has been sent."""
        vars(self.s)["_initial_tracker_announce_sent"] = True

    async def _maybe_trigger_tracker_metadata_exchange(
        self,
        peer_list: list[dict[str, Any]],
        *,
        active_count: Optional[int] = None,
        connection_summary: Optional[dict[str, int]] = None,
    ) -> None:
        """Attempt magnet metadata exchange from tracker peers when startup is stalled."""
        if not peer_list:
            return

        is_magnet_link = (
            isinstance(self.s.torrent_data, dict)
            and self.s.torrent_data.get("file_info") is None
        ) or (
            isinstance(self.s.torrent_data, dict)
            and self.s.torrent_data.get("file_info", {}).get("total_length", 0) == 0
        )
        if not is_magnet_link:
            return

        metadata_available = (
            isinstance(self.s.torrent_data, dict)
            and self.s.torrent_data.get("file_info") is not None
            and self.s.torrent_data.get("file_info", {}).get("total_length", 0) > 0
        )
        if metadata_available:
            return

        summary = connection_summary or {}
        active_connections = summary.get("active_connections", active_count or 0)
        productive_connections = summary.get(
            "productive_connections", active_count or 0
        )
        metadata_capable_connections = summary.get("metadata_capable_connections", 0)
        metadata_exchange_active = summary.get("metadata_exchange_active", 0)
        peers_with_piece_info = summary.get("peers_with_piece_info", 0)
        requestable_connections = summary.get("requestable_connections", 0)

        metadata_metrics = getattr(self.s, "_peer_discovery_metrics", None)
        if isinstance(metadata_metrics, dict):
            if (
                active_connections == 0
                and productive_connections == 0
                and requestable_connections == 0
                and peers_with_piece_info == 0
            ):
                started_at = float(
                    metadata_metrics.get("metadata_starvation_started_at", 0.0) or 0.0
                )
                now = time.time()
                if started_at <= 0.0:
                    metadata_metrics["metadata_starvation_started_at"] = now
                    metadata_metrics["metadata_starvation_seconds"] = 0.0
                else:
                    metadata_metrics["metadata_starvation_seconds"] = max(
                        0.0, now - started_at
                    )
            else:
                metadata_metrics["metadata_starvation_started_at"] = 0.0
                metadata_metrics["metadata_starvation_seconds"] = 0.0

        self.s.logger.debug(
            "TRACKER_METADATA_STATUS: %s tracker_peers_added=%d active_connections=%d productive_connections=%d "
            "requestable_connections=%d metadata_capable_connections=%d metadata_exchange_active=%d peers_with_piece_info=%d "
            "metadata_starvation_seconds=%.1f",
            self.s.info.name,
            len(peer_list),
            active_connections,
            productive_connections,
            requestable_connections,
            metadata_capable_connections,
            metadata_exchange_active,
            peers_with_piece_info,
            float(
                metadata_metrics.get("metadata_starvation_seconds", 0.0)
                if isinstance(metadata_metrics, dict)
                else 0.0
            ),
        )
        if metadata_exchange_active > 0:
            self.s.logger.debug(
                "Skipping standalone tracker metadata fetch for %s because %d live metadata exchange(s) already started",
                self.s.info.name,
                metadata_exchange_active,
            )
            return

        self.s.logger.debug(
            "Magnet link detected, attempting metadata exchange with %d tracker-discovered peer(s) for %s",
            len(peer_list),
            self.s.info.name,
        )
        try:
            metadata_fetched = await self.s.handle_magnet_metadata_exchange(
                peer_list,
                metadata_source="tracker",
            )
            if metadata_fetched:
                self.s.logger.debug(
                    "TRACKER_METADATA_COMPLETE: Successfully fetched metadata from tracker-discovered peers for %s",
                    self.s.info.name,
                )
            else:
                self.s.logger.warning(
                    "TRACKER_METADATA_INCOMPLETE: Metadata exchange with tracker-discovered peers did not complete for %s "
                    "(active=%d productive=%d metadata_capable=%d peers_with_piece_info=%d)",
                    self.s.info.name,
                    active_connections,
                    productive_connections,
                    metadata_capable_connections,
                    peers_with_piece_info,
                )
        except Exception as metadata_error:
            self.s.logger.debug(
                "Error during metadata exchange with tracker peers for %s: %s (will retry with DHT or later)",
                self.s.info.name,
                metadata_error,
                exc_info=True,
            )

    async def run(self) -> None:
        """Run the announce loop."""
        base_announce_interval = float(self.s.config.network.announce_interval)

        def _tracker_seed_ratio(response: Any) -> float:
            complete = getattr(response, "complete", None)
            incomplete = getattr(response, "incomplete", None)
            if complete is None and incomplete is None:
                return 0.0
            try:
                complete_value = max(0.0, float(complete))
            except (TypeError, ValueError):
                complete_value = 0.0
            try:
                incomplete_value = max(0.0, float(incomplete))
            except (TypeError, ValueError):
                incomplete_value = 0.0
            total = complete_value + incomplete_value
            if total <= 0:
                return 0.0
            return min(1.0, complete_value / total)

        while not self.s.is_stopped():
            # Set connecting state
            self.s.tracker_connection_status = "connecting"
            next_announce_interval = base_announce_interval
            try:
                announce_controller = AnnounceController(
                    SessionContext(  # type: ignore[missing-argument]
                        config=self.s.config,
                        torrent_data=self.s.torrent_data,
                        output_dir=self.s.output_dir,
                        info=self.s.info,
                        logger=self.s.logger,
                    ),
                    self.s.tracker,
                )
                td = announce_controller.prepare_torrent_dict(self.s.torrent_data)
                tracker_peer_id = self._get_tracker_peer_id()
                if tracker_peer_id:
                    td["peer_id"] = tracker_peer_id
                elif td.get("peer_id"):
                    peer_id = td["peer_id"]
                    if isinstance(peer_id, bytes):
                        self._cache_tracker_peer_id(peer_id)

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
                    await asyncio.sleep(base_announce_interval)
                    continue

                # Note: Collect all trackers (not just single announce URL)
                # This ensures all trackers from magnet links are used
                tracker_urls = announce_controller.collect_trackers(td)

                if not tracker_urls:
                    self.s.logger.debug(
                        "No tracker URLs available, skipping announce (using DHT/PEX)"
                    )
                    await asyncio.sleep(base_announce_interval)
                    continue

                # Keep single announce_url for backward compatibility with events
                announce_url = tracker_urls[0] if tracker_urls else ""
                announce_event = "started" if not self._initial_announce_sent() else ""
                if announce_event == "started":
                    self._mark_initial_announce_sent()

                # Note: Use external port if NAT mapping exists, otherwise use internal port
                # Use listen_port_tcp (or listen_port as fallback) to match actual configured port
                listen_port = (
                    self.s.config.network.listen_port_tcp
                    or self.s.config.network.listen_port
                )
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
                        else:
                            # Note: Log warning if external port lookup fails
                            # This indicates NAT mapping may not exist for the configured port
                            self.s.logger.warning(
                                "NAT external port lookup failed for internal port %d (protocol=tcp). "
                                "Tracker will announce internal port %d, which may prevent peer connections if behind NAT. "
                                "Verify NAT port mapping is active for TCP port %d.",
                                listen_port,
                                announce_port,
                                listen_port,
                            )
                    except Exception:
                        # Best-effort: if NAT lookup fails, use internal port
                        self.s.logger.debug(
                            "Failed to get external port from NAT manager, using internal port %d",
                            listen_port,
                            exc_info=True,
                        )

                # Emit TRACKER_ANNOUNCE_STARTED event
                try:
                    from ccbt.utils.events import Event, emit_event

                    info_hash_hex = ""
                    if isinstance(td, dict) and "info_hash" in td:
                        info_hash = td["info_hash"]
                        if isinstance(info_hash, bytes):
                            info_hash_hex = info_hash.hex()
                        else:
                            info_hash_hex = str(info_hash)

                    await emit_event(
                        Event(
                            event_type="tracker_announce",
                            data={
                                "info_hash": info_hash_hex,
                                "tracker_url": announce_url,
                            },
                        )
                    )
                except Exception as e:
                    self.s.logger.debug(
                        "Failed to emit TRACKER_ANNOUNCE_STARTED event: %s", e
                    )

                # Note: Announce to all trackers, not just one
                # This ensures all trackers from magnet links are used for peer discovery
                if hasattr(self.s.tracker, "announce_to_multiple"):
                    responses = await self.s.tracker.announce_to_multiple(
                        td, tracker_urls, port=announce_port, event=announce_event
                    )
                    # Check if any tracker responded successfully
                    successful_responses = [r for r in responses if r is not None]
                    total_peers = sum(
                        len(getattr(r, "peers", []) or []) for r in successful_responses
                    )
                    swarm_state = await self.s.get_swarm_recovery_state()
                    self.s.logger.debug(
                        "TRACKER_SWARM_STATE: trackers=%d, successful=%d, discovered_peers=%d, active=%d, productive=%d, requestable=%d, piece_info=%d",
                        len(tracker_urls),
                        len(successful_responses),
                        total_peers,
                        int(swarm_state["active_peers"]),
                        int(swarm_state["productive_peers"]),
                        int(swarm_state["requestable_peers"]),
                        int(swarm_state["peers_with_piece_info"]),
                    )

                    if not successful_responses:
                        self.s.logger.warning(
                            "All tracker announces failed (%d trackers tried)",
                            len(tracker_urls),
                        )
                        self.s.tracker_connection_status = "error"
                        self.s.last_tracker_error = (
                            "All trackers returned None response"
                        )
                        # Emit TRACKER_ANNOUNCE_ERROR event
                        try:
                            from ccbt.utils.events import Event, emit_event

                            info_hash_hex = ""
                            if isinstance(td, dict) and "info_hash" in td:
                                info_hash = td["info_hash"]
                                if isinstance(info_hash, bytes):
                                    info_hash_hex = info_hash.hex()
                                else:
                                    info_hash_hex = str(info_hash)

                            await emit_event(
                                Event(
                                    event_type="tracker_announce_error",
                                    data={
                                        "info_hash": info_hash_hex,
                                        "tracker_url": announce_url,
                                        "error": "All trackers returned None response",
                                    },
                                )
                            )
                        except Exception as e:
                            self.s.logger.debug(
                                "Failed to emit TRACKER_ANNOUNCE_ERROR event: %s", e
                            )
                        await asyncio.sleep(min(base_announce_interval, 120.0))
                        continue

                    # Success - at least one tracker responded
                    self.s.logger.debug(
                        "Periodic announce: %d/%d tracker(s) responded, %d total peer(s)",
                        len(successful_responses),
                        len(tracker_urls),
                        total_peers,
                    )
                    # Note: Aggregate peers from ALL successful responses, not just the first one
                    # This ensures we connect to peers from all trackers that responded
                    all_peers = []
                    for resp in successful_responses:
                        if resp and hasattr(resp, "peers") and resp.peers:
                            all_peers.extend(resp.peers)

                    # Create a synthetic response with all aggregated peers for compatibility
                    # Use the first response as a template (for interval, etc.)
                    response = successful_responses[0] if successful_responses else None
                    if response and all_peers:
                        # Replace peers with enriched list from all trackers and prioritize utility.
                        ranked_tracker_peers: list[dict[str, Any]] = []
                        for tracker_response in successful_responses:
                            seed_ratio = _tracker_seed_ratio(tracker_response)
                            tracker_peers = (
                                getattr(tracker_response, "peers", None) or []
                            )
                            for tracker_peer in tracker_peers:
                                normalized_peer = _normalize_tracker_peer(
                                    tracker_peer, utility_signal=seed_ratio
                                )
                                if normalized_peer:
                                    ranked_tracker_peers.append(normalized_peer)

                        ranked_tracker_peers.sort(
                            key=lambda peer: (
                                float(peer.get("_replacement_priority", 0.0)),
                                bool(peer.get("ssl_capable")),
                                peer.get("ip"),
                                peer.get("port"),
                            ),
                            reverse=True,
                        )
                        response.peers = ranked_tracker_peers
                        self.s.logger.debug(
                            "Aggregated and prioritized %d peer(s) from %d successful tracker response(s)",
                            len(ranked_tracker_peers),
                            len(successful_responses),
                        )
                        all_peers = ranked_tracker_peers
                else:
                    # Fallback to single announce if announce_to_multiple not available
                    response = await self.s.tracker.announce(td, port=announce_port)
                    if not response:
                        self.s.logger.warning("Tracker announce returned None response")
                        self.s.tracker_connection_status = "error"
                        self.s.last_tracker_error = "Tracker returned None response"
                        await asyncio.sleep(min(base_announce_interval, 120.0))
                        continue

                usable_peer_count = (
                    len(response.peers)
                    if response and hasattr(response, "peers") and response.peers
                    else 0
                )
                tracker_interval = getattr(response, "interval", None)
                if isinstance(tracker_interval, (int, float)) and tracker_interval > 0:
                    next_announce_interval = max(
                        30.0,
                        min(float(tracker_interval), base_announce_interval),
                    )
                cached_status = getattr(self.s, "_cached_status", {})
                if not isinstance(cached_status, dict):
                    cached_status = {}
                connected_peers = int(cached_status.get("connected_peers", 0) or 0)
                productive_peers = int(
                    cached_status.get("productive_peers", connected_peers) or 0
                )
                requestable_peers = int(
                    cached_status.get("requestable_peers", connected_peers) or 0
                )
                handshake_complete_peers = int(
                    cached_status.get("handshake_complete_peers", 0) or 0
                )
                extension_capable_peers = int(
                    cached_status.get("extension_capable_peers", 0) or 0
                )
                metadata_capable_peers = int(
                    cached_status.get("metadata_capable_peers", 0) or 0
                )
                if usable_peer_count == 0:
                    self.s.tracker_connection_status = "degraded"
                    self.s.last_tracker_error = (
                        "Tracker responses contained no usable peers"
                    )
                    next_announce_interval = min(next_announce_interval, 60.0)
                    self.s.logger.warning(
                        "Tracker announce returned %d successful response(s) but no usable peers; marking tracker state degraded and retrying in %.1fs",
                        len(successful_responses)
                        if "successful_responses" in locals()
                        else 1,
                        next_announce_interval,
                    )
                else:
                    self.s.tracker_connection_status = "connected"
                    self.s.last_tracker_error = None
                    if (
                        connected_peers == 0
                        or productive_peers == 0
                        or requestable_peers == 0
                    ):
                        next_announce_interval = min(next_announce_interval, 120.0)
                        self.s.logger.debug(
                            "Tracker announce produced peers but swarm remains weak (connected=%d, productive=%d, requestable=%d, handshake_complete=%d, extension_capable=%d, metadata_capable=%d); using accelerated reannounce interval %.1fs",
                            connected_peers,
                            productive_peers,
                            requestable_peers,
                            handshake_complete_peers,
                            extension_capable_peers,
                            metadata_capable_peers,
                            next_announce_interval,
                        )

                # Emit TRACKER_ANNOUNCE_SUCCESS event
                try:
                    from ccbt.utils.events import Event, emit_event

                    info_hash_hex = ""
                    if isinstance(td, dict) and "info_hash" in td:
                        info_hash = td["info_hash"]
                        if isinstance(info_hash, bytes):
                            info_hash_hex = info_hash.hex()
                        else:
                            info_hash_hex = str(info_hash)

                    await emit_event(
                        Event(
                            event_type="tracker_announce_success",
                            data={
                                "info_hash": info_hash_hex,
                                "tracker_url": announce_url,
                                "peer_count": usable_peer_count,
                                "usable_peer_count": usable_peer_count,
                                "response_count": len(successful_responses)
                                if "successful_responses" in locals()
                                else 1,
                            },
                        )
                    )
                except Exception as e:
                    self.s.logger.debug(
                        "Failed to emit TRACKER_ANNOUNCE_SUCCESS event: %s", e
                    )
                self.s.tracker_consecutive_failures = 0

                # Connect peers to the existing download path when running
                if (
                    response
                    and hasattr(response, "peers")
                    and response.peers
                    and self.s.download_manager
                ):
                    # Note: Check if peer manager exists (may have been initialized early)
                    has_peer_manager = (
                        hasattr(self.s.download_manager, "peer_manager")
                        and self.s.download_manager.peer_manager is not None
                    )

                    download_started = (
                        hasattr(self.s.download_manager, "_download_started")
                        and getattr(self.s.download_manager, "_download_started", False)
                    ) or has_peer_manager

                    # Note: Log peer manager status for diagnostics
                    self.s.logger.debug(
                        "🔍 TRACKER PEER CONNECTION: response.peers=%d, download_manager=%s, has_peer_manager=%s, download_started=%s",
                        len(response.peers) if response.peers else 0,
                        self.s.download_manager is not None,
                        has_peer_manager,
                        download_started,
                    )

                    # Note: If peer manager exists, connect peers directly
                    # If peer manager doesn't exist yet, wait with retry logic, then queue peers for later
                    if not has_peer_manager:
                        # Note: Wait for peer_manager to be ready (similar to DHT retry logic)
                        # This handles timing issues where tracker responses arrive before peer_manager is initialized
                        self.s.logger.warning(
                            "⚠️ TRACKER PEER CONNECTION: peer_manager not ready for %s, waiting up to 2 seconds...",
                            self.s.info.name,
                        )
                        for retry in range(4):  # 4 retries * 0.5s = 2 seconds total
                            await asyncio.sleep(0.5)
                            has_peer_manager = (
                                hasattr(self.s.download_manager, "peer_manager")
                                and self.s.download_manager.peer_manager is not None
                            )
                            if has_peer_manager:
                                self.s.logger.debug(
                                    "✅ TRACKER PEER CONNECTION: peer_manager ready for %s after %.1fs",
                                    self.s.info.name,
                                    (retry + 1) * 0.5,
                                )
                                break

                        # If still not ready after retries, queue peers for later
                        if not has_peer_manager:
                            self.s.logger.warning(
                                "⚠️ TRACKER PEER CONNECTION: peer_manager still not ready for %s after retries, queuing %d peers for later connection",
                                self.s.info.name,
                                len(response.peers) if response.peers else 0,
                            )
                            queued_peers_count = _queue_tracker_peers_for_later(
                                self.s,
                                response.peers,
                                peer_source="tracker",
                            )
                            if queued_peers_count:
                                queued_peers = self.s.get_queued_peers()
                                self.s.logger.debug(
                                    "📦 TRACKER PEER CONNECTION: Queued %d peer(s) for later connection (total queued: %d)",
                                    queued_peers_count,
                                    len(queued_peers),
                                )
                            # CRITICAL: Do not exit the loop - keep periodic announces alive so tracker
                            # discovery continues and queued peers can be drained when peer_manager is ready
                            await asyncio.sleep(next_announce_interval)
                            continue

                    # Note: If peer manager exists (or became ready after retry), connect peers directly
                    if has_peer_manager:
                        peer_list = []
                        # Note: Use aggregated peers from all successful tracker responses
                        # The response object now contains all peers from all successful trackers
                        for p in (
                            response.peers
                            if (
                                response
                                and hasattr(response, "peers")
                                and response.peers
                            )
                            else []
                        ):
                            normalized = _normalize_tracker_peer(p, utility_signal=0.0)
                            if normalized:
                                if isinstance(p, dict):
                                    prior_priority = float(
                                        p.get("_replacement_priority", 0.0)
                                    )
                                    prior_seed_ratio = float(
                                        p.get("_tracker_seed_ratio", 0.0)
                                    )
                                    if prior_seed_ratio > 0:
                                        normalized["_tracker_seed_ratio"] = (
                                            prior_seed_ratio
                                        )
                                    normalized["_replacement_priority"] = max(
                                        float(
                                            normalized.get("_replacement_priority", 0.0)
                                        ),
                                        prior_priority,
                                    )
                                peer_list.append(normalized)
                            else:
                                self.s.logger.warning(
                                    "⚠️ TRACKER PEER CONNECTION: Skipping invalid peer from tracker response: %s (type: %s)",
                                    p,
                                    type(p).__name__,
                                )

                        peer_list.sort(
                            key=lambda peer: (
                                float(peer.get("_replacement_priority", 0.0)),
                                bool(peer.get("ssl_capable")),
                                peer.get("ip"),
                                peer.get("port"),
                            ),
                            reverse=True,
                        )

                        if peer_list:
                            # Note: Deduplicate peers before connecting
                            # Some trackers may return duplicate peers
                            seen_peers = set()
                            unique_peer_list = []
                            for peer in peer_list:
                                peer_key = (peer.get("ip"), peer.get("port"))
                                if peer_key not in seen_peers:
                                    seen_peers.add(peer_key)
                                    unique_peer_list.append(peer)

                            if len(unique_peer_list) < len(peer_list):
                                self.s.logger.debug(
                                    "Deduplicated %d duplicate peer(s) from tracker response (%d -> %d unique)",
                                    len(peer_list) - len(unique_peer_list),
                                    len(peer_list),
                                    len(unique_peer_list),
                                )

                            raw_peer_len = len(peer_list)
                            response_peer_len = (
                                len(response.peers) if response.peers else 0
                            )
                            self.s.logger.debug(
                                "🔗 TRACKER PEER CONNECTION (announce_loop): raw=%d unique=%d "
                                "response.peers=%d for %s",
                                raw_peer_len,
                                len(unique_peer_list),
                                response_peer_len,
                                self.s.info.name,
                            )
                            try:
                                await self.s._ingest_tracker_discovery_peers(  # noqa: SLF001
                                    unique_peer_list,
                                    tracker_url=announce_url,
                                    ingress_source="announce_loop",
                                )
                                self.s.logger.debug(
                                    "✅ TRACKER PEER CONNECTION: Successfully initiated connection to %d peer(s) from tracker for %s",
                                    len(unique_peer_list),
                                    self.s.info.name,
                                )

                                # Note: Also add tracker peers to PEX manager for sharing with other peers
                                # This helps bootstrap the PEX network with known good peers from trackers
                                if (
                                    hasattr(self.s, "pex_manager")
                                    and self.s.pex_manager
                                ):
                                    try:
                                        # Convert peer list to PEX format
                                        pex_peers = []
                                        for peer in unique_peer_list:
                                            try:
                                                from ccbt.discovery.pex import PexPeer

                                                pex_peer = PexPeer(
                                                    ip=peer.get("ip", ""),
                                                    port=peer.get("port", 0),
                                                    source="tracker",
                                                )
                                                pex_peers.append(pex_peer)
                                            except Exception as pex_error:
                                                self.s.logger.debug(
                                                    "Failed to create PEX peer from tracker peer %s: %s",
                                                    peer,
                                                    pex_error,
                                                )

                                        if pex_peers:
                                            # Add peers to PEX manager
                                            await self.s.pex_manager.add_peers(
                                                pex_peers
                                            )
                                            self.s.logger.debug(
                                                "Added %d tracker peer(s) to PEX manager for sharing",
                                                len(pex_peers),
                                            )
                                    except Exception as pex_error:
                                        self.s.logger.debug(
                                            "Failed to add tracker peers to PEX manager: %s",
                                            pex_error,
                                        )

                                # Note: Also notify DHT callbacks about tracker-discovered peers
                                # This helps bootstrap DHT peer discovery with known good peers
                                if hasattr(self.s, "dht_client") and self.s.dht_client:
                                    try:
                                        # Convert peer list to DHT callback format (list of (ip, port) tuples)
                                        dht_peers = []
                                        for peer in unique_peer_list:
                                            try:
                                                ip = peer.get("ip", "")
                                                port = peer.get("port", 0)
                                                if ip and port and port > 0:
                                                    dht_peers.append((ip, port))
                                            except Exception as dht_error:
                                                self.s.logger.debug(
                                                    "Failed to convert tracker peer to DHT format %s: %s",
                                                    peer,
                                                    dht_error,
                                                )

                                        if dht_peers:
                                            # Invoke DHT callbacks with tracker peers
                                            if hasattr(
                                                self.s.dht_client,
                                                "invoke_peer_callbacks",
                                            ):
                                                self.s.dht_client.invoke_peer_callbacks(
                                                    dht_peers, self.s.info.info_hash
                                                )
                                            elif hasattr(
                                                self.s.dht_client,
                                                "_invoke_peer_callbacks",
                                            ):
                                                # Fallback for backward compatibility
                                                self.s.dht_client._invoke_peer_callbacks(  # noqa: SLF001
                                                    dht_peers, self.s.info.info_hash
                                                )
                                            self.s.logger.debug(
                                                "Invoked DHT callbacks with %d tracker peer(s)",
                                                len(dht_peers),
                                            )
                                    except Exception as dht_error:
                                        self.s.logger.debug(
                                            "Failed to invoke DHT callbacks with tracker peers: %s",
                                            dht_error,
                                        )
                                await asyncio.sleep(1.0)
                                peer_manager = self.s.download_manager.peer_manager
                                active_count = None
                                connection_summary = None
                                if peer_manager and hasattr(
                                    peer_manager, "connections"
                                ):
                                    if hasattr(peer_manager, "get_connection_summary"):
                                        connection_summary = (
                                            await peer_manager.get_connection_summary()
                                        )
                                        active_count = connection_summary.get(
                                            "active_connections"
                                        )
                                        self.s.logger.debug(
                                            "Tracker peer connection status for %s: %s",
                                            self.s.info.name,
                                            connection_summary,
                                        )
                                    else:
                                        active_count = len(
                                            [
                                                c
                                                for c in peer_manager.connections.values()
                                                if c.is_active()
                                            ]
                                        )
                                        self.s.logger.debug(
                                            "Tracker peer connection status for %s: %d active connections after adding %d peers (success rate: %.1f%%)",
                                            self.s.info.name,
                                            active_count,
                                            len(unique_peer_list),
                                            (active_count / len(unique_peer_list) * 100)
                                            if unique_peer_list
                                            else 0.0,
                                        )
                                await self._maybe_trigger_tracker_metadata_exchange(
                                    unique_peer_list,
                                    active_count=active_count,
                                    connection_summary=connection_summary,
                                )
                            except Exception as connect_error:
                                self.s.logger.warning(
                                    "Failed to connect tracker peers for %s: %s",
                                    self.s.info.name,
                                    connect_error,
                                )
                                # Note: Verify connections after a delay
                                await asyncio.sleep(
                                    1.0
                                )  # Give connections time to establish
                                peer_manager = self.s.download_manager.peer_manager
                                active_count = None
                                connection_summary = None
                                if peer_manager and hasattr(
                                    peer_manager, "connections"
                                ):
                                    if hasattr(peer_manager, "get_connection_summary"):
                                        connection_summary = (
                                            await peer_manager.get_connection_summary()
                                        )
                                        active_count = connection_summary.get(
                                            "active_connections"
                                        )
                                        self.s.logger.debug(
                                            "Tracker peer connection status for %s after connect error: %s",
                                            self.s.info.name,
                                            connection_summary,
                                        )
                                    else:
                                        active_count = len(
                                            [
                                                c
                                                for c in peer_manager.connections.values()
                                                if c.is_active()
                                            ]
                                        )
                                        self.s.logger.debug(
                                            "Tracker peer connection status for %s: %d active connections after adding %d peers (success rate: %.1f%%)",
                                            self.s.info.name,
                                            active_count,
                                            len(unique_peer_list),
                                            (active_count / len(unique_peer_list) * 100)
                                            if unique_peer_list
                                            else 0.0,
                                        )
                                await self._maybe_trigger_tracker_metadata_exchange(
                                    unique_peer_list,
                                    active_count=active_count,
                                    connection_summary=connection_summary,
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
                            await self.s._ingest_tracker_discovery_peers(  # noqa: SLF001
                                peer_list,
                                tracker_url=announce_url,
                                ingress_source="announce_loop_fallback",
                            )
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
                await asyncio.sleep(next_announce_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Failure/backoff management (simplified)
                consecutive = self.s.tracker_consecutive_failures + 1
                self.s.tracker_consecutive_failures = consecutive
                self.s.tracker_connection_status = "error"
                self.s.last_tracker_error = f"Tracker announce failed: {e}"
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
