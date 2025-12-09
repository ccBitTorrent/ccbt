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
        
        # CRITICAL FIX: Log collected trackers for debugging
        if self._logger:
            self._logger.info(
                "TRACKER_COLLECTION: Collected %d tracker(s) from torrent_data (announce_list=%s, trackers=%s, announce=%s)",
                len(tracker_urls),
                bool(td.get("announce_list")),
                bool(td.get("trackers")),
                bool(td.get("announce")),
            )
            if tracker_urls:
                self._logger.debug(
                    "TRACKER_COLLECTION: Trackers: %s",
                    ", ".join(tracker_urls[:10]) + ("..." if len(tracker_urls) > 10 else ""),
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

        # CRITICAL FIX: Use external port if NAT mapping exists, otherwise use internal port
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
        # CRITICAL FIX: Try to get port from session_manager config if available
        # Avoid hardcoded 6881 fallback - use actual configured port
        elif self._ctx and self._ctx.session_manager and hasattr(self._ctx.session_manager, "config"):
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
                # CRITICAL FIX: Log warning if external port lookup fails
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
        # CRITICAL FIX: Log the port being used for tracker announce
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

        # Get healthy trackers from health manager (prioritize these)
        healthy_trackers: list[str] = []
        try:
            if hasattr(self._tracker, "get_healthy_trackers"):
                # Get healthy trackers, excluding ones we already have from torrent
                healthy_trackers = self._tracker.get_healthy_trackers(set(unique))
        except Exception as e:
            if self._logger:
                self._logger.debug("Failed to get healthy trackers: %s", e)

        # Combine: healthy trackers first, then original torrent trackers
        combined_trackers = healthy_trackers + unique

        # Add fallback trackers if needed
        try:
            has_http = any(u.startswith(("http://", "https://")) for u in combined_trackers)
            if (
                not has_http
                and self._config
                and getattr(self._config.discovery, "enable_http_trackers", False)
                and not getattr(self._config.discovery, "strict_private_mode", False)
            ):
                # Get fallback trackers from health manager
                fallback_trackers = []
                try:
                    if hasattr(self._tracker, "get_fallback_trackers"):
                        fallback_trackers = self._tracker.get_fallback_trackers(set(combined_trackers))
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

                # CRITICAL FIX: Collect all trackers (not just single announce URL)
                # This ensures all trackers from magnet links are used
                announce_controller = AnnounceController(
                    SessionContext(
                        torrent_data=td,
                        info=self.s.info,
                        logger=self.s.logger,
                    ),
                    self.s.tracker,
                )
                tracker_urls = announce_controller._collect_trackers(td)
                
                if not tracker_urls:
                    self.s.logger.debug(
                        "No tracker URLs available, skipping announce (using DHT/PEX)"
                    )
                    await asyncio.sleep(announce_interval)
                    continue
                
                # Keep single announce_url for backward compatibility with events
                announce_url = tracker_urls[0] if tracker_urls else ""

                # CRITICAL FIX: Use external port if NAT mapping exists, otherwise use internal port
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
                            # CRITICAL FIX: Log warning if external port lookup fails
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
                    self.s.logger.debug("Failed to emit TRACKER_ANNOUNCE_STARTED event: %s", e)
                
                # CRITICAL FIX: Announce to all trackers, not just one
                # This ensures all trackers from magnet links are used for peer discovery
                if hasattr(self.s.tracker, "announce_to_multiple"):
                    responses = await self.s.tracker.announce_to_multiple(
                        td, tracker_urls, port=announce_port, event=""
                    )
                    # Check if any tracker responded successfully
                    successful_responses = [r for r in responses if r is not None]
                    total_peers = sum(
                        len(getattr(r, "peers", []) or []) for r in successful_responses
                    )
                    
                    if not successful_responses:
                        self.s.logger.warning(
                            "All tracker announces failed (%d trackers tried)",
                            len(tracker_urls)
                        )
                        self.s._tracker_connection_status = "error"
                        self.s._last_tracker_error = "All trackers returned None response"
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
                            self.s.logger.debug("Failed to emit TRACKER_ANNOUNCE_ERROR event: %s", e)
                        await asyncio.sleep(announce_interval)
                        continue
                    
                    # Success - at least one tracker responded
                    self.s.logger.info(
                        "Periodic announce: %d/%d tracker(s) responded, %d total peer(s)",
                        len(successful_responses),
                        len(tracker_urls),
                        total_peers,
                    )
                    # CRITICAL FIX: Aggregate peers from ALL successful responses, not just the first one
                    # This ensures we connect to peers from all trackers that responded
                    all_peers = []
                    for resp in successful_responses:
                        if resp and hasattr(resp, "peers") and resp.peers:
                            all_peers.extend(resp.peers)
                    
                    # Create a synthetic response with all aggregated peers for compatibility
                    # Use the first response as a template (for interval, etc.)
                    response = successful_responses[0] if successful_responses else None
                    if response and all_peers:
                        # Replace peers with aggregated list from all trackers
                        response.peers = all_peers
                        self.s.logger.info(
                            "Aggregated %d peer(s) from %d successful tracker response(s)",
                            len(all_peers),
                            len(successful_responses),
                        )
                else:
                    # Fallback to single announce if announce_to_multiple not available
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
                    
                    peer_count = 0
                    if response and hasattr(response, "peers") and response.peers:
                        peer_count = len(response.peers)
                    
                    await emit_event(
                        Event(
                            event_type="tracker_announce_success",
                            data={
                                "info_hash": info_hash_hex,
                                "tracker_url": announce_url,
                                "peer_count": peer_count,
                            },
                        )
                    )
                except Exception as e:
                    self.s.logger.debug("Failed to emit TRACKER_ANNOUNCE_SUCCESS event: %s", e)
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

                    # CRITICAL FIX: Log peer manager status for diagnostics
                    self.s.logger.info(
                        "🔍 TRACKER PEER CONNECTION: response.peers=%d, download_manager=%s, has_peer_manager=%s, download_started=%s",
                        len(response.peers) if response.peers else 0,
                        self.s.download_manager is not None,
                        has_peer_manager,
                        download_started,
                    )

                    # CRITICAL FIX: If peer manager exists, connect peers directly
                    # If peer manager doesn't exist yet, wait with retry logic, then queue peers for later
                    if not has_peer_manager:
                        # CRITICAL FIX: Wait for peer_manager to be ready (similar to DHT retry logic)
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
                                self.s.logger.info(
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
                            # Build peer list for queuing
                            peer_list = []
                            for p in response.peers if (response and hasattr(response, "peers") and response.peers) else []:
                                try:
                                    if hasattr(p, "ip") and hasattr(p, "port"):
                                        peer_list.append(
                                            {
                                                "ip": p.ip,
                                                "port": p.port,
                                                "peer_source": "tracker",
                                                "ssl_capable": getattr(p, "ssl_capable", None),
                                            }
                                        )
                                    elif isinstance(p, dict) and "ip" in p and "port" in p:
                                        peer_list.append(
                                            {
                                                "ip": str(p["ip"]),
                                                "port": int(p["port"]),
                                                "peer_source": "tracker",
                                                "ssl_capable": p.get("ssl_capable"),
                                            }
                                        )
                                except (ValueError, TypeError, KeyError):
                                    pass
                            
                            # Queue peers for later connection (using same mechanism as DHT)
                            if peer_list:
                                import time as time_module
                                current_time = time_module.time()
                                # Add timestamp to each peer for timeout checking
                                for peer in peer_list:
                                    peer["_queued_at"] = current_time
                                
                                if not hasattr(self.s, "_queued_peers"):
                                    self.s._queued_peers = []  # type: ignore[attr-defined]
                                self.s._queued_peers.extend(peer_list)  # type: ignore[attr-defined]
                                self.s.logger.info(
                                    "📦 TRACKER PEER CONNECTION: Queued %d peer(s) for later connection (total queued: %d)",
                                    len(peer_list),
                                    len(self.s._queued_peers),  # type: ignore[attr-defined]
                                )
                            return  # Exit early since peers are queued
                    
                    # CRITICAL FIX: If peer manager exists (or became ready after retry), connect peers directly
                    if has_peer_manager:
                        peer_list = []
                        # CRITICAL FIX: Use aggregated peers from all successful tracker responses
                        # The response object now contains all peers from all successful trackers
                        for p in response.peers if (response and hasattr(response, "peers") and response.peers) else []:
                            try:
                                if hasattr(p, "ip") and hasattr(p, "port"):
                                    peer_list.append(
                                        {
                                            "ip": p.ip,
                                            "port": p.port,
                                            "peer_source": "tracker",
                                            "ssl_capable": getattr(p, "ssl_capable", None),
                                        }
                                    )
                                elif isinstance(p, dict) and "ip" in p and "port" in p:
                                    peer_list.append(
                                        {
                                            "ip": str(p["ip"]),
                                            "port": int(p["port"]),
                                            "peer_source": "tracker",
                                            "ssl_capable": p.get("ssl_capable"),
                                        }
                                    )
                                else:
                                    self.s.logger.warning(
                                        "⚠️ TRACKER PEER CONNECTION: Skipping invalid peer from tracker response: %s (type: %s)",
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
                            # CRITICAL FIX: Deduplicate peers before connecting
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
                            
                            self.s.logger.info(
                                "🔗 TRACKER PEER CONNECTION: Connecting %d unique peer(s) from tracker to peer manager for %s (response had %d total peers)",
                                len(unique_peer_list),
                                self.s.info.name,
                                len(response.peers) if response.peers else 0,
                            )
                            try:
                                # Connect peers to existing peer manager
                                await self.s.download_manager.peer_manager.connect_to_peers(
                                    unique_peer_list
                                )  # type: ignore[misc]
                                self.s.logger.info(
                                    "✅ TRACKER PEER CONNECTION: Successfully initiated connection to %d peer(s) from tracker for %s",
                                    len(unique_peer_list),
                                    self.s.info.name,
                                )

                                # CRITICAL FIX: Also add tracker peers to PEX manager for sharing with other peers
                                # This helps bootstrap the PEX network with known good peers from trackers
                                if hasattr(self.s, "pex_manager") and self.s.pex_manager:
                                    try:
                                        # Convert peer list to PEX format
                                        pex_peers = []
                                        for peer in unique_peer_list:
                                            try:
                                                from ccbt.discovery.pex import PexPeer
                                                pex_peer = PexPeer(
                                                    ip=peer.get("ip", ""),
                                                    port=peer.get("port", 0),
                                                    source="tracker"
                                                )
                                                pex_peers.append(pex_peer)
                                            except Exception as pex_error:
                                                self.s.logger.debug(
                                                    "Failed to create PEX peer from tracker peer %s: %s",
                                                    peer, pex_error
                                                )

                                        if pex_peers:
                                            # Add peers to PEX manager
                                            await self.s.pex_manager.add_peers(pex_peers)
                                            self.s.logger.debug(
                                                "Added %d tracker peer(s) to PEX manager for sharing",
                                                len(pex_peers)
                                            )
                                    except Exception as pex_error:
                                        self.s.logger.debug(
                                            "Failed to add tracker peers to PEX manager: %s", pex_error
                                        )

                                # CRITICAL FIX: Also notify DHT callbacks about tracker-discovered peers
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
                                                    peer, dht_error
                                                )

                                        if dht_peers:
                                            # Invoke DHT callbacks with tracker peers
                                            self.s.dht_client._invoke_peer_callbacks(
                                                dht_peers, self.s.info.info_hash
                                            )
                                            self.s.logger.debug(
                                                "Invoked DHT callbacks with %d tracker peer(s)",
                                                len(dht_peers)
                                            )
                                    except Exception as dht_error:
                                        self.s.logger.debug(
                                            "Failed to invoke DHT callbacks with tracker peers: %s", dht_error
                                        )
                            except Exception as connect_error:
                                self.s.logger.warning(
                                    "Failed to connect tracker peers for %s: %s",
                                    self.s.info.name, connect_error
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
                                    self.s.logger.info(
                                        "Tracker peer connection status for %s: %d active connections after adding %d peers (success rate: %.1f%%)",
                                        self.s.info.name,
                                        active_count,
                                        len(unique_peer_list),
                                        (active_count / len(unique_peer_list) * 100) if unique_peer_list else 0.0,
                                    )

                                # CRITICAL FIX: Trigger metadata exchange for magnet links when peers connect from tracker
                                # Check if this is a magnet link (metadata not available)
                                is_magnet_link = (
                                    isinstance(self.s.torrent_data, dict)
                                    and self.s.torrent_data.get("file_info") is None
                                ) or (
                                    isinstance(self.s.torrent_data, dict)
                                    and self.s.torrent_data.get("file_info", {}).get("total_length", 0) == 0
                                )

                                if is_magnet_link:
                                    # Check if metadata is already available
                                    metadata_available = (
                                        isinstance(self.s.torrent_data, dict)
                                        and self.s.torrent_data.get("file_info") is not None
                                        and self.s.torrent_data.get("file_info", {}).get("total_length", 0) > 0
                                    )

                                    if not metadata_available:
                                        self.s.logger.info(
                                            "Magnet link detected, attempting metadata exchange with %d tracker-discovered peer(s) for %s",
                                            len(peer_list),
                                            self.s.info.name,
                                        )
                                        try:
                                            # Use DHT setup's metadata exchange handler if available
                                            if hasattr(self.s, "_dht_setup") and self.s._dht_setup:
                                                metadata_fetched = await self.s._dht_setup._handle_magnet_metadata_exchange(peer_list)
                                                if metadata_fetched:
                                                    self.s.logger.info(
                                                        "Successfully fetched metadata from tracker-discovered peers for %s",
                                                        self.s.info.name,
                                                    )
                                            else:
                                                # Fallback: use metadata exchange directly
                                                from ccbt.piece.async_metadata_exchange import (
                                                    fetch_metadata_from_peers,
                                                )
                                                metadata = await fetch_metadata_from_peers(
                                                    self.s.info.info_hash,
                                                    peer_list,
                                                    timeout=60.0,
                                                )
                                                if metadata:
                                                    self.s.logger.info(
                                                        "Successfully fetched metadata from tracker-discovered peers for %s",
                                                        self.s.info.name,
                                                    )
                                                    # Update torrent_data with metadata
                                                    from ccbt.core.magnet import (
                                                        build_torrent_data_from_metadata,
                                                    )
                                                    updated_torrent_data = build_torrent_data_from_metadata(
                                                        self.s.info.info_hash,
                                                        metadata,
                                                    )
                                                    if isinstance(self.s.torrent_data, dict):
                                                        self.s.torrent_data.update(updated_torrent_data)
                                                        # CRITICAL FIX: Update file assembler if it exists (rebuild file segments)
                                                        if (
                                                            hasattr(self.s.download_manager, "file_assembler")
                                                            and self.s.download_manager.file_assembler is not None
                                                        ):
                                                            try:
                                                                self.s.download_manager.file_assembler.update_from_metadata(
                                                                    self.s.torrent_data
                                                                )
                                                                self.s.logger.info(
                                                                    "Updated file assembler with new metadata for %s",
                                                                    self.s.info.name,
                                                                )
                                                            except Exception as e:
                                                                self.s.logger.warning(
                                                                    "Failed to update file assembler with metadata: %s",
                                                                    e,
                                                                )
                                                        # Update piece_manager with new metadata
                                                        if hasattr(self.s.download_manager, "piece_manager") and self.s.download_manager.piece_manager:
                                                            piece_manager = self.s.download_manager.piece_manager
                                                            if "pieces_info" in updated_torrent_data:
                                                                pieces_info = updated_torrent_data["pieces_info"]
                                                                if "num_pieces" in pieces_info:
                                                                    piece_manager.num_pieces = int(pieces_info["num_pieces"])
                                                                    self.s.logger.info(
                                                                        "Updated piece_manager.num_pieces to %d from metadata",
                                                                        piece_manager.num_pieces,
                                                                    )
                                                                if "piece_length" in pieces_info:
                                                                    piece_manager.piece_length = int(pieces_info["piece_length"])
                                                                    self.s.logger.info(
                                                                        "Updated piece_manager.piece_length to %d from metadata",
                                                                        piece_manager.piece_length,
                                                                    )
                                                            if hasattr(piece_manager, "torrent_data"):
                                                                piece_manager.torrent_data = self.s.torrent_data
                                                else:
                                                    self.s.logger.debug(
                                                        "Metadata exchange with tracker-discovered peers did not complete (will retry with DHT or later)",
                                                    )
                                        except Exception as metadata_error:
                                            self.s.logger.debug(
                                                "Error during metadata exchange with tracker peers for %s: %s (will retry with DHT or later)",
                                                self.s.info.name,
                                                metadata_error,
                                                exc_info=True,
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
