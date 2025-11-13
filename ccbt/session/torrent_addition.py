"""Torrent addition handling with queue integration and emergency start."""

from __future__ import annotations

import asyncio
from typing import Any


class TorrentAdditionHandler:
    """Handles torrent addition with queue integration and emergency recovery."""

    def __init__(self, manager: Any) -> None:
        """Initialize torrent addition handler.

        Args:
            manager: AsyncSessionManager instance

        """
        self.manager = manager
        self.logger = manager.logger
        self.config = manager.config

    async def add_torrent_background(
        self, session: Any, info_hash: bytes, resume: bool = False
    ) -> None:
        """Start session in background task with queue integration.

        Args:
            session: AsyncTorrentSession instance
            info_hash: Torrent info hash
            resume: Whether to resume from checkpoint

        """
        try:
            # Log at the very start to confirm function is being called
            session_name = (
                getattr(session.info, "name", "Unknown")
                if hasattr(session, "info") and session.info
                else "Unknown"
            )
            self.logger.info("Starting torrent session in background: %s", session_name)
        except Exception:
            self.logger.exception("Error getting session name")
            session_name = "Unknown"

        try:
            # Simplified logic: Add to queue if available, then ensure session starts
            if self.manager.queue_manager:
                if await self._handle_queue_integration(session, info_hash, resume):
                    return  # Session started by queue manager

            # If we get here, either no queue manager or session wasn't started by queue
            # Start the session ourselves
            await self._start_session_directly(session, resume)

        except Exception:
            self.logger.exception(
                "Error starting torrent %s in background",
                info_hash.hex()[:8],
            )
            # Try to start anyway - might still work
            try:
                self.logger.info("Attempting to start session despite error (fallback)")
                task = asyncio.create_task(session.start(resume=resume))
                _ = task  # Store reference to avoid unused variable warning
            except Exception:
                self.logger.exception("Fallback session start also failed")

    async def _handle_queue_integration(
        self, session: Any, info_hash: bytes, resume: bool
    ) -> bool:
        """Handle queue manager integration.

        Args:
            session: AsyncTorrentSession instance
            info_hash: Torrent info hash
            resume: Whether to resume from checkpoint

        Returns:
            True if session was started by queue manager, False otherwise

        """
        self.logger.info("Queue manager exists, adding torrent to queue")
        priority = self.config.queue.default_priority
        queue_added = False
        try:
            # Add timeout to prevent hanging
            await asyncio.wait_for(
                self.manager.queue_manager.add_torrent(
                    info_hash,
                    priority,
                    auto_start=True,
                    resume=resume,
                ),
                timeout=10.0,  # 10 second timeout for queue operations
            )
            queue_added = True
            self.logger.info("Torrent added to queue successfully")
        except asyncio.TimeoutError:
            self.logger.warning(
                "Timeout adding torrent to queue (continuing to start session directly)"
            )
        except Exception:
            self.logger.exception("Failed to add torrent to queue")
            # Continue to start session directly below

        if queue_added:
            # Wait a short time for queue manager to process
            await asyncio.sleep(0.5)

            # Check if queue manager started the session
            try:
                status = await asyncio.wait_for(session.get_status(), timeout=2.0)
                session_status = status.get("status", "stopped")
                self.logger.info("Session status after queue add: %s", session_status)

                if session_status not in ("stopped", "starting"):
                    self.logger.info(
                        "Queue manager started session (status: %s)",
                        session_status,
                    )
                    return True  # Session already started by queue manager
                if session_status == "starting":
                    self.logger.info(
                        "Session is starting (status: starting), waiting for completion"
                    )
                    # Wait a bit more for it to finish starting
                    await asyncio.sleep(2.0)
                    status = await asyncio.wait_for(session.get_status(), timeout=2.0)
                    session_status = status.get("status", "stopped")
                    if session_status not in ("stopped", "starting"):
                        self.logger.info(
                            "Session started by queue manager (status: %s)",
                            session_status,
                        )
                        return True
            except asyncio.TimeoutError:
                self.logger.warning(
                    "Timeout getting session status, starting session directly"
                )
            except Exception as status_error:
                self.logger.warning(
                    "Error getting session status: %s, starting session directly",
                    status_error,
                )

        return False

    async def _start_session_directly(self, session: Any, resume: bool) -> None:
        """Start session directly (not via queue).

        Args:
            session: AsyncTorrentSession instance
            resume: Whether to resume from checkpoint

        """
        self.logger.info("Starting session directly")
        try:
            status = await asyncio.wait_for(session.get_status(), timeout=2.0)
            session_status = status.get("status", "stopped")
            self.logger.info("Current session status: %s", session_status)
        except Exception as status_error:
            self.logger.warning(
                "Could not get session status: %s, attempting to start anyway",
                status_error,
            )
            session_status = "stopped"

        if session_status == "stopped":
            await self._start_stopped_session(session, resume)
        elif session_status == "starting":
            await self._wait_for_starting_session(session)

    async def _start_stopped_session(self, session: Any, resume: bool) -> None:
        """Start a stopped session.

        Args:
            session: AsyncTorrentSession instance
            resume: Whether to resume from checkpoint

        """
        self.logger.info(
            "Calling session.start() for %s (status: stopped)",
            session.info.name,
        )
        try:
            # CRITICAL: Add logging before and after the call to see if it executes
            self.logger.info(
                "About to await session.start() for %s",
                session.info.name,
            )
            await asyncio.wait_for(session.start(resume=resume), timeout=60.0)
            self.logger.info("Session started successfully for %s", session.info.name)
        except asyncio.TimeoutError:
            self.logger.warning(
                "Timeout starting torrent %s after 60 seconds (continuing in background)",
                session.info.info_hash.hex()[:8],
            )
            # Start in background anyway - don't block
            self.logger.info(
                "Creating background task for session.start() for %s",
                session.info.name,
            )
            task = asyncio.create_task(session.start(resume=resume))
            _ = task  # Store reference to avoid unused variable warning
        except Exception:
            self.logger.exception(
                "Exception starting torrent %s",
                session.info.info_hash.hex()[:8],
            )
            # Try background start as fallback
            task = asyncio.create_task(session.start(resume=resume))
            _ = task  # Store reference to avoid unused variable warning

    async def _wait_for_starting_session(self, session: Any) -> None:
        """Wait for a session that is already starting.

        Args:
            session: AsyncTorrentSession instance

        """
        # Session is already starting - wait for it to complete or timeout
        self.logger.info("Session is starting, waiting for completion (max 60s)")
        try:
            # Wait for status to change from "starting"
            for i in range(60):  # Check every second for 60 seconds
                await asyncio.sleep(1.0)
                try:
                    status = await asyncio.wait_for(session.get_status(), timeout=2.0)
                    new_status = status.get("status", "stopped")
                    if new_status != "starting":
                        self.logger.info(
                            "Session finished starting (status: %s)",
                            new_status,
                        )
                        return
                    # Log progress every 10 seconds
                    if (i + 1) % 10 == 0:
                        self.logger.info(
                            "Still waiting for session to start... (status: %s, %d seconds elapsed)",
                            new_status,
                            i + 1,
                        )
                except Exception as status_check_error:
                    self.logger.warning(
                        "Error checking session status: %s",
                        status_check_error,
                    )
                    # Continue waiting despite error

            # Still "starting" after 60 seconds - check if download manager was started
            # CRITICAL FIX: Don't force status change - check actual download state
            await self._check_and_recover_starting_session(session)

        except Exception as wait_error:
            self.logger.warning(
                "Error waiting for session to start: %s",
                wait_error,
            )
            # CRITICAL FIX: Don't force status - check actual state instead
            await self._check_download_state_after_error(session, wait_error)

    async def _check_and_recover_starting_session(self, session: Any) -> None:
        """Check download state and recover if needed after 60s wait.

        Args:
            session: AsyncTorrentSession instance

        """
        download_started = hasattr(
            session.download_manager, "_download_started"
        ) and getattr(session.download_manager, "_download_started", False)
        has_peer_manager = (
            hasattr(session.download_manager, "peer_manager")
            and session.download_manager.peer_manager is not None
        )
        is_downloading = (
            hasattr(session.piece_manager, "is_downloading")
            and getattr(session.piece_manager, "is_downloading", False)
            if session.piece_manager
            else False
        )

        if download_started and has_peer_manager and is_downloading:
            # Download actually started but status didn't transition - this is a bug, log it
            self.logger.warning(
                "Session still in 'starting' state after 60 seconds but download is actually running "
                "(download_started=%s, has_peer_manager=%s, is_downloading=%s) - status transition bug",
                download_started,
                has_peer_manager,
                is_downloading,
            )
            # Only set status if download is actually running
            session.info.status = "downloading"
            self.logger.info(
                "Corrected session status to 'downloading' (download is actually running)"
            )
        elif download_started or has_peer_manager:
            # Partial start - log diagnostic info
            self.logger.warning(
                "Session still in 'starting' state after 60 seconds with partial initialization "
                "(download_started=%s, has_peer_manager=%s, is_downloading=%s) - download may not be fully started",
                download_started,
                has_peer_manager,
                is_downloading,
            )
            # Don't force status - let the actual download state determine it
        else:
            # Download manager wasn't started - this is the real problem
            self.logger.error(
                "Session still in 'starting' state after 60 seconds and download_manager was NOT started - this indicates a critical failure"
            )
            # Try to start download manager as last resort
            await self.emergency_start_download(session)

    async def _check_download_state_after_error(
        self, session: Any, error: Exception
    ) -> None:
        """Check download state after wait error.

        Args:
            session: AsyncTorrentSession instance
            error: The error that occurred

        """
        try:
            # Check if download actually started despite the error
            if (
                hasattr(session.download_manager, "_download_started")
                and getattr(
                    session.download_manager,
                    "_download_started",
                    False,
                )
                and hasattr(session.download_manager, "peer_manager")
                and session.download_manager.peer_manager is not None
            ):
                # Download actually started - update status to reflect reality
                session.info.status = "downloading"
                self.logger.info(
                    "Session status updated to 'downloading' (download actually started despite wait error)"
                )
            else:
                # Download didn't start - keep status as 'starting' or 'error'
                self.logger.warning(
                    "Session wait error and download not started - status will reflect actual state"
                )
        except Exception as check_error:
            self.logger.warning(
                "Error checking download state after wait error: %s",
                check_error,
            )

    async def emergency_start_download(self, session: Any) -> None:
        """Emergency start of download manager when normal start fails.

        Args:
            session: AsyncTorrentSession instance

        """
        try:
            if hasattr(session.download_manager, "start_download"):
                self.logger.info("Attempting emergency start of download manager...")
                await session.download_manager.start()
                await session.download_manager.start_download([])
                _started_flag: bool = True
                setattr(  # noqa: B010  # type: ignore[assignment]
                    session.download_manager,
                    "_download_started",
                    _started_flag,
                )
                session.info.status = "downloading"
                self.logger.info(
                    "Emergency start successful - status set to 'downloading'"
                )

                # CRITICAL FIX: Set up peer discovery even in emergency start
                # The normal start() flow sets up DHT/tracker/PEX, but if it hung,
                # we need to set it up here
                self.logger.info("Setting up peer discovery after emergency start...")
                try:
                    await self._setup_emergency_peer_discovery(session)
                except Exception as discovery_error:
                    self.logger.warning(
                        "Failed to set up peer discovery after emergency start: %s",
                        discovery_error,
                    )
        except Exception:
            # CRITICAL FIX: Don't force status - log error and let status reflect actual state
            self.logger.exception(
                "Emergency start failed - session status will remain 'starting' until download actually starts. "
                "This indicates a critical failure in download initialization."
            )

    async def _setup_emergency_peer_discovery(self, session: Any) -> None:
        """Set up peer discovery after emergency start.

        Args:
            session: AsyncTorrentSession instance

        """
        # CRITICAL: Start tracker first if not started
        if hasattr(session, "tracker") and session.tracker:
            try:
                self.logger.info(
                    "Emergency: Starting tracker client for %s",
                    session.info.name,
                )
                await asyncio.wait_for(
                    session.tracker.start(),
                    timeout=5.0,
                )
                self.logger.info("Emergency: Tracker client started successfully")
            except Exception as tracker_start_error:
                self.logger.warning(
                    "Emergency: Failed to start tracker: %s",
                    tracker_start_error,
                )

        # Trigger initial announce in background
        if hasattr(session, "tracker") and session.tracker:

            async def emergency_announce():
                try:
                    td = (
                        session.torrent_data
                        if isinstance(session.torrent_data, dict)
                        else {}
                    )
                    if td and "info_hash" in td:
                        self.logger.info(
                            "Emergency: Triggering tracker announce for %s",
                            session.info.name,
                        )
                        # CRITICAL FIX: Use configured listen_port instead of default 6881
                        response = await asyncio.wait_for(
                            session.tracker.announce(
                                td,
                                port=session.config.network.listen_port,
                            ),
                            timeout=10.0,
                        )
                        if response and hasattr(response, "peers") and response.peers:
                            peer_list = [
                                {
                                    "ip": p.ip,
                                    "port": p.port,
                                    "peer_source": "tracker",
                                }
                                for p in response.peers
                                if hasattr(p, "ip")
                            ]
                            if peer_list and session.download_manager.peer_manager:
                                self.logger.info(
                                    "Emergency: Connecting to %d peers from tracker",
                                    len(peer_list),
                                )
                                await session.download_manager.peer_manager.connect_to_peers(
                                    peer_list
                                )
                except Exception as e:
                    self.logger.warning(
                        "Emergency announce failed: %s",
                        e,
                        exc_info=True,
                    )

            task = asyncio.create_task(emergency_announce())
            _ = task  # Store reference to avoid unused variable warning

        # Also trigger DHT get_peers if DHT is available
        if (
            session.session_manager
            and hasattr(session.session_manager, "dht_client")
            and session.session_manager.dht_client
            and not session.is_private
        ):

            async def emergency_dht_query():
                try:
                    if not session.session_manager:
                        return
                    dht_client = getattr(
                        session.session_manager,
                        "dht_client",
                        None,
                    )
                    if not dht_client:
                        self.logger.warning(
                            "Emergency DHT query: No DHT client available"
                        )
                    elif not hasattr(dht_client, "routing_table"):
                        self.logger.warning(
                            "Emergency DHT query: DHT client has no routing_table"
                        )
                    elif len(dht_client.routing_table.nodes) == 0:
                        self.logger.warning(
                            "Emergency DHT query: DHT routing table is empty (%d nodes)",
                            len(dht_client.routing_table.nodes),
                        )
                    else:
                        self.logger.info(
                            "Emergency: Triggering DHT get_peers for %s (routing table has %d nodes)",
                            session.info.name,
                            len(dht_client.routing_table.nodes),
                        )
                        peers = await asyncio.wait_for(
                            dht_client.get_peers(
                                session.info.info_hash,
                                max_peers=50,
                            ),
                            timeout=30.0,
                        )
                        if peers:
                            self.logger.info(
                                "Emergency: DHT get_peers returned %d peers",
                                len(peers),
                            )
                            if session.download_manager.peer_manager:
                                peer_list = [
                                    {
                                        "ip": ip,
                                        "port": port,
                                        "peer_source": "dht",
                                    }
                                    for ip, port in peers
                                ]
                                self.logger.info(
                                    "Emergency: Connecting to %d peers from DHT",
                                    len(peer_list),
                                )
                                await session.download_manager.peer_manager.connect_to_peers(
                                    peer_list
                                )
                            else:
                                self.logger.warning(
                                    "Emergency: DHT found %d peers but peer_manager is None",
                                    len(peers),
                                )
                        else:
                            self.logger.warning(
                                "Emergency: DHT get_peers returned no peers"
                            )
                except Exception as e:
                    self.logger.warning(
                        "Emergency DHT query failed: %s",
                        e,
                        exc_info=True,
                    )

            task = asyncio.create_task(emergency_dht_query())
            _ = task  # Store reference to avoid unused variable warning
