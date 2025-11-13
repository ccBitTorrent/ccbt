"""Status aggregation and collection for torrent sessions."""

from __future__ import annotations

import asyncio
import time
from typing import Any


class StatusAggregator:
    """Aggregates and validates status information from download manager."""

    def __init__(self, session: Any) -> None:
        """Initialize status aggregator.

        Args:
            session: AsyncTorrentSession instance

        """
        self.session = session

    async def get_torrent_status(self) -> dict[str, Any]:
        """Get current torrent status with validation.

        Returns:
            Dictionary with torrent status information

        """
        # Check if download_manager is available
        if not self.session.download_manager:
            return self._get_minimal_status()

        # Get status from download manager
        download_status = await self._get_download_status()

        # Validate and merge with session info
        status = dict(download_status)  # Create a copy to avoid mutating the original
        status.update(
            {
                "info_hash": self.session.info.info_hash.hex(),
                "name": self.session.info.name,
                "status": self.session.info.status,
                "added_time": self.session.info.added_time,
                "uptime": time.time() - self.session.info.added_time,
                "last_error": self.session._last_error,
                "tracker_status": self.session._tracker_connection_status,
                "last_tracker_error": self.session._last_tracker_error,
            },
        )
        return status

    def _get_minimal_status(self) -> dict[str, Any]:
        """Get minimal status when download manager is not available.

        Returns:
            Dictionary with minimal status information

        """
        return {
            "info_hash": self.session.info.info_hash.hex(),
            "name": self.session.info.name,
            "status": self.session.info.status,
            "added_time": self.session.info.added_time,
            "uptime": time.time() - self.session.info.added_time,
            "progress": 0.0,
            "connected_peers": 0,
            "active_peers": 0,
            "download_rate": 0.0,
            "upload_rate": 0.0,
            "download_complete": False,
            "last_error": self.session._last_error,
            "tracker_status": self.session._tracker_connection_status,
            "last_tracker_error": self.session._last_tracker_error,
        }

    async def _get_download_status(self) -> dict[str, Any]:
        """Get status from download manager with validation.

        Returns:
            Dictionary with download status information

        """
        get_status_method = getattr(self.session.download_manager, "get_status", None)
        if not get_status_method:
            # No get_status method available
            self.session.logger.debug("Download manager has no get_status method")
            return self._get_default_download_status()

        if asyncio.iscoroutinefunction(get_status_method):
            # It's async, await it
            try:
                download_status = await get_status_method()
                return self._validate_status(download_status)
            except Exception as e:
                # Log error but return minimal status
                self.session.logger.warning(
                    "Error getting download status (async): %s", e, exc_info=True
                )
                return self._get_default_download_status()
        else:
            # It's sync, call it directly (shouldn't happen but handle it)
            try:
                download_status = get_status_method()
                return self._validate_status(download_status)
            except Exception as e:
                # Log error but return minimal status
                self.session.logger.warning(
                    "Error getting download status (sync): %s", e, exc_info=True
                )
                return self._get_default_download_status()

    def _validate_status(self, download_status: Any) -> dict[str, Any]:
        """Validate download status is a dict.

        Args:
            download_status: Status object from download manager

        Returns:
            Validated status dictionary

        """
        if not isinstance(download_status, dict):
            self.session.logger.error(
                "Download manager get_status() returned non-dict: %s. Using minimal status.",
                type(download_status),
            )
            return self._get_default_download_status()
        return download_status

    def _get_default_download_status(self) -> dict[str, Any]:
        """Get default download status when status cannot be retrieved.

        Returns:
            Dictionary with default status values

        """
        return {
            "progress": 0.0,
            "connected_peers": 0,
            "active_peers": 0,
            "download_rate": 0.0,
            "upload_rate": 0.0,
            "download_complete": False,
        }
