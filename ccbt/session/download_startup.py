"""Download startup orchestration with retry logic."""

from __future__ import annotations

import asyncio
import traceback
from typing import Any


class DownloadStartupOrchestrator:
    """Orchestrates download startup with retry logic and validation."""

    def __init__(self, session: Any) -> None:
        """Initialize download startup orchestrator.

        Args:
            session: AsyncTorrentSession instance

        """
        self.session = session

    async def ensure_download_started(self) -> None:
        """Ensure download is started even if initial announce fails.

        Retries up to 3 times with exponential backoff to handle race conditions.
        Waits for initial announce to complete before starting download with empty peer list.
        """
        max_retries = 3
        initial_wait = 5.0

        # CRITICAL FIX: Wait for initial announce to complete (with timeout)
        # This prevents race condition where we start download before peers are discovered
        if self.session._initial_announce_in_progress:
            self.session.logger.info(
                "Waiting for initial announce to complete before starting download for %s",
                self.session.info.name,
            )
            try:
                # Wait up to 35 seconds for initial announce (30s announce timeout + 5s buffer)
                await asyncio.wait_for(
                    self.session._initial_announce_complete.wait(),
                    timeout=35.0,
                )
                self.session.logger.info(
                    "Initial announce completed for %s - proceeding with download start check",
                    self.session.info.name,
                )
            except asyncio.TimeoutError:
                self.session.logger.warning(
                    "Timeout waiting for initial announce for %s - proceeding anyway",
                    self.session.info.name,
                )

        for attempt in range(max_retries):
            try:
                # CRITICAL FIX: Wait with exponential backoff (5s, 10s, 20s)
                wait_time = initial_wait * (2**attempt)
                self.session.logger.debug(
                    "_ensure_download_started: attempt %d/%d, waiting %.1fs",
                    attempt + 1,
                    max_retries,
                    wait_time,
                )
                await asyncio.sleep(wait_time)

                # Validate download state
                if not self._validate_download_state(attempt, max_retries):
                    continue

                # Check if download has already started
                if await self._is_download_started():
                    return  # Success - exit retry loop

                # Try to start download
                if await self._start_download_with_retry(attempt, max_retries):
                    return  # Success - exit retry loop

            except (TypeError, AttributeError) as e:
                self._handle_type_error(e, attempt, max_retries)
                if attempt < max_retries - 1:
                    continue
                raise  # Re-raise on last attempt
            except Exception as e:
                error_msg = str(e)
                # Check if it's the list.get error
                if "list" in error_msg.lower() and (
                    "get" in error_msg.lower() or "attribute" in error_msg.lower()
                ):
                    self.session.logger.exception(
                        "ERROR: List object error in _ensure_download_started: %s",
                        error_msg,
                    )
                else:
                    self.session.logger.warning(
                        "Error ensuring download started: %s",
                        error_msg,
                        exc_info=True,
                    )
                # Retry on next iteration if not last attempt
                if attempt < max_retries - 1:
                    continue
                # Don't raise - this is a background task, log and continue

    def _validate_download_state(self, attempt: int, max_retries: int) -> bool:
        """Validate download manager state before starting.

        Args:
            attempt: Current attempt number
            max_retries: Maximum number of retries

        Returns:
            True if validation passes, False otherwise

        """
        # CRITICAL FIX: Validate download_manager exists and has correct type
        if not self.session.download_manager:
            self.session.logger.warning(
                "Cannot ensure download started: download_manager is None"
            )
            if attempt < max_retries - 1:
                return False  # Will retry
            return False

        # CRITICAL FIX: Validate download_manager.torrent_data is not a list
        if hasattr(self.session.download_manager, "torrent_data") and isinstance(
            self.session.download_manager.torrent_data, list
        ):
            self.session.logger.error(
                "Cannot start download: download_manager.torrent_data is a list, not dict. "
                "This indicates a bug in torrent_data initialization."
            )
            if attempt < max_retries - 1:
                return False  # Will retry
            return False

        return True

    async def _is_download_started(self) -> bool:
        """Check if download has already started.

        Returns:
            True if download is already started, False otherwise

        """
        # CRITICAL FIX: Check if download has been started - use getattr with default False
        # This prevents race conditions where _download_started hasn't been set yet
        download_started = getattr(
            self.session.download_manager, "_download_started", False
        )
        has_peer_manager = (
            hasattr(self.session.download_manager, "peer_manager")
            and self.session.download_manager.peer_manager is not None
        )

        # CRITICAL FIX: Also check if piece_manager.is_downloading is True
        # This ensures we don't skip download start if peer_manager exists but download isn't actually started
        is_downloading = (
            getattr(self.session.piece_manager, "is_downloading", False)
            if self.session.piece_manager
            else False
        )

        self.session.logger.info(
            "_ensure_download_started: download_started=%s, has_peer_manager=%s, is_downloading=%s, connections=%d",
            download_started,
            has_peer_manager,
            is_downloading,
            len(self.session.download_manager.peer_manager.connections)
            if (
                has_peer_manager
                and hasattr(self.session.download_manager.peer_manager, "connections")
            )
            else 0,
        )

        # CRITICAL FIX: Only skip if download is actually started (both peer_manager exists AND is_downloading is True)
        # This fixes the issue where peer_manager exists but piece_manager.is_downloading is False
        if download_started and has_peer_manager and is_downloading:
            conn_count = (
                len(self.session.download_manager.peer_manager.connections)
                if hasattr(self.session.download_manager.peer_manager, "connections")
                else 0
            )
            self.session.logger.info(
                "Download already started: peer_manager exists, is_downloading=True, %d connections - skipping duplicate start",
                conn_count,
            )
            return True  # Success - exit retry loop

        # If peer_manager exists but is_downloading is False, we need to start the download
        if has_peer_manager and not is_downloading:
            self.session.logger.info(
                "Peer manager exists but download not started (is_downloading=False) - starting download"
            )
            # Ensure _peer_manager is set on piece_manager
            if self.session.piece_manager and not hasattr(
                self.session.piece_manager, "_peer_manager"
            ):
                setattr(  # noqa: B010
                    self.session.piece_manager,
                    "_peer_manager",
                    self.session.download_manager.peer_manager,
                )
            # Start download
            if self.session.piece_manager and hasattr(
                self.session.piece_manager, "start_download"
            ):
                if asyncio.iscoroutinefunction(
                    self.session.piece_manager.start_download
                ):
                    await self.session.piece_manager.start_download(
                        self.session.download_manager.peer_manager
                    )
                else:
                    self.session.piece_manager.start_download(
                        self.session.download_manager.peer_manager
                    )
                self.session.logger.info("Started piece manager download")
            return True  # Success - exit retry loop

        return False

    async def _start_download_with_retry(self, attempt: int, max_retries: int) -> bool:
        """Start download with retry logic.

        Args:
            attempt: Current attempt number
            max_retries: Maximum number of retries

        Returns:
            True if download started successfully, False otherwise

        """
        # Check if download has been started (legacy check for compatibility)
        if not hasattr(self.session.download_manager, "_download_started"):
            # Initial announce likely failed or returned no peers
            # Start download with torrent_data - DHT/PEX will discover peers later
            if hasattr(self.session.download_manager, "start_download"):
                # CRITICAL FIX: Validate torrent_data is not a list before calling start_download
                if isinstance(self.session.torrent_data, list):
                    self.session.logger.error(
                        "Cannot start download: torrent_data is a list, not dict or TorrentInfo. "
                        "This indicates a bug in torrent_data initialization."
                    )
                    if attempt < max_retries - 1:
                        return False  # Will retry
                    return False

                self.session.logger.info(
                    "[DOWNLOAD_STARTUP] Starting download without initial peers for %s (initial announce completed, will use DHT/PEX discovery)",
                    self.session.info.name,
                )
                # async_main.AsyncDownloadManager: start() initializes piece_manager, start_download(peers) orchestrates everything
                # Start with empty peer list - peers will be added via connect_to_peers() as they're discovered
                try:
                    # Initialize piece_manager
                    self.session.logger.info(
                        "[DOWNLOAD_STARTUP] Initializing download manager for %s (no initial peers)",
                        self.session.info.name,
                    )
                    await self.session.download_manager.start()
                    self.session.logger.info(
                        "[DOWNLOAD_STARTUP] Download manager initialized for %s",
                        self.session.info.name,
                    )

                    # Start download with empty peer list (peers will be added incrementally)
                    self.session.logger.info(
                        "[DOWNLOAD_STARTUP] Starting download for %s with empty peer list (peers will be discovered via DHT/PEX)",
                        self.session.info.name,
                    )
                    await self.session.download_manager.start_download([])
                    self.session.logger.info(
                        "[DOWNLOAD_STARTUP] Download started for %s (waiting for peer discovery)",
                        self.session.info.name,
                    )

                    # CRITICAL FIX: Set status to 'downloading' immediately after start_download() regardless of peer count
                    self.session.info.status = "downloading"
                    self.session.logger.info(
                        "Status set to 'downloading' immediately after start_download() (peers will be discovered via DHT/PEX)"
                    )

                    # Set up session callbacks on peer_manager (created by start_download)
                    if self.session.download_manager.peer_manager:
                        self.session.download_manager.peer_manager.on_peer_connected = (
                            self.session._on_peer_connected
                        )
                        self.session.download_manager.peer_manager.on_peer_disconnected = self.session._on_peer_disconnected
                        self.session.download_manager.peer_manager.on_piece_received = (
                            self.session._on_peer_piece_received
                        )
                        self.session.download_manager.peer_manager.on_bitfield_received = self.session._on_peer_bitfield_received

                        # Update session-level references
                        self.session.peer_manager = (
                            self.session.download_manager.peer_manager
                        )
                        self.session.piece_manager = (
                            self.session.download_manager.piece_manager
                        )

                    setattr(  # noqa: B010
                        self.session.download_manager, "_download_started", True
                    )  # type: ignore[assignment]

                    # CRITICAL FIX: Ensure status is set even with empty peer list
                    if self.session.info.status != "downloading":
                        self.session.info.status = "downloading"
                        self.session.logger.info(
                            "Status set to 'downloading' in _ensure_download_started() (empty peer list)"
                        )

                    self.session.logger.info(
                        "Download started (waiting for peer discovery)"
                    )
                    # Initialize cache immediately to prevent property errors
                    self.session._cached_status = {
                        "downloaded": 0,
                        "uploaded": 0,
                        "left": 0,
                        "peers": 0,
                        "download_rate": 0.0,
                        "upload_rate": 0.0,
                    }
                    return True  # Success - exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.session.logger.warning(
                            "Failed to start download (attempt %d/%d): %s, will retry",
                            attempt + 1,
                            max_retries,
                            e,
                        )
                        return False  # Will retry
                    self.session.logger.exception(
                        "Failed to start download after %d attempts",
                        max_retries,
                    )
                    raise
            else:
                self.session.logger.warning(
                    "Download manager does not support start_download()"
                )
                if attempt < max_retries - 1:
                    return False  # Will retry
                return False

        return False

    def _handle_type_error(
        self, error: Exception, attempt: int, max_retries: int
    ) -> None:
        """Handle TypeError/AttributeError with detailed diagnostics.

        Args:
            error: The exception that occurred
            attempt: Current attempt number
            max_retries: Maximum number of retries

        """
        # Catch TypeError/AttributeError specifically (e.g., "list object has no attribute get")
        error_msg = str(error)

        # Make error message readable and actionable
        if "list" in error_msg.lower() and (
            "get" in error_msg.lower() or "attribute" in error_msg.lower()
        ):
            # Get diagnostic info
            dm_type = (
                type(self.session.download_manager).__name__
                if self.session.download_manager
                else "None"
            )
            dm_td = getattr(self.session.download_manager, "torrent_data", None)
            dm_td_type = type(dm_td).__name__ if dm_td is not None else "None"
            td_type = type(self.session.torrent_data).__name__

            # Check peer_manager for any list issues
            peer_mgr = getattr(self.session.download_manager, "peer_manager", None)
            peer_mgr_type = type(peer_mgr).__name__ if peer_mgr else "None"
            peer_mgr_td = getattr(peer_mgr, "torrent_data", None) if peer_mgr else None
            peer_mgr_td_type = (
                type(peer_mgr_td).__name__ if peer_mgr_td is not None else "None"
            )

            # Log in simple, readable format (one line at a time)
            self.session.logger.exception("=" * 60)
            self.session.logger.exception(
                "ERROR: List object passed where dict expected"
            )
            self.session.logger.exception("Location: _ensure_download_started()")
            self.session.logger.exception("Error message: %s", error_msg)
            self.session.logger.exception("download_manager type: %s", dm_type)
            self.session.logger.exception(
                "download_manager.torrent_data type: %s", dm_td_type
            )
            self.session.logger.exception("self.torrent_data type: %s", td_type)
            self.session.logger.exception("peer_manager type: %s", peer_mgr_type)
            self.session.logger.exception(
                "peer_manager.torrent_data type: %s", peer_mgr_td_type
            )

            # If torrent_data is a list, show first few items
            if isinstance(self.session.torrent_data, list):
                items_preview = (
                    str(self.session.torrent_data[:3])
                    if len(self.session.torrent_data) > 0
                    else "empty list"
                )
                self.session.logger.exception(
                    "torrent_data is a list with %d items",
                    len(self.session.torrent_data),
                )
                self.session.logger.exception("First items: %s", items_preview)

            # If download_manager.torrent_data is a list, show it
            if isinstance(dm_td, list):
                items_preview = str(dm_td[:3]) if len(dm_td) > 0 else "empty list"
                self.session.logger.exception(
                    "download_manager.torrent_data is a list with %d items",
                    len(dm_td),
                )
                self.session.logger.exception("First items: %s", items_preview)

            # If peer_manager.torrent_data is a list, show it
            if isinstance(peer_mgr_td, list):
                items_preview = (
                    str(peer_mgr_td[:3]) if len(peer_mgr_td) > 0 else "empty list"
                )
                self.session.logger.exception(
                    "peer_manager.torrent_data is a list with %d items",
                    len(peer_mgr_td),
                )
                self.session.logger.exception("First items: %s", items_preview)

            # Log full traceback to identify exact location
            self.session.logger.exception("Full traceback:")
            for line in traceback.format_exc().split("\n"):
                if line.strip():
                    self.session.logger.exception(line)
            self.session.logger.exception("=" * 60)
        else:
            self.session.logger.warning(
                "TypeError/AttributeError ensuring download started: %s",
                error_msg,
                exc_info=True,
            )
