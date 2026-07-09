"""Status aggregation and collection for torrent sessions."""

from __future__ import annotations

import asyncio
import time
from typing import Any

# Canonical internal field names; IPC translation occurs where canonical status is serialized.
CANONICAL_TORRENT_STATUS_KEYS = (
    "info_hash",
    "name",
    "status",
    "progress",
    "download_rate",
    "upload_rate",
    "connected_peers",
    "active_peers",
    "downloaded",
    "uploaded",
    "left",
    "total_size",
    "pieces_completed",
    "pieces_total",
    "is_private",
    "output_dir",
    "tracker_status",
    "last_error",
    "uptime",
    "added_time",
    "download_complete",
)


class StatusAggregator:
    """Aggregates and validates status information from download manager."""

    def __init__(self, session: Any) -> None:
        """Initialize status aggregator.

        Args:
            session: AsyncTorrentSession instance

        """
        self.session = session

    def _normalize_canonical_status(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Fill canonical torrent status with optional fields from session/piece_manager."""
        out: dict[str, Any] = dict(raw)
        pm = getattr(self.session, "piece_manager", None)
        if pm and hasattr(pm, "num_pieces") and hasattr(pm, "piece_length"):
            try:
                num_pieces = int(getattr(pm, "num_pieces", 0) or 0)
                piece_length = int(getattr(pm, "piece_length", 16384) or 16384)
            except (TypeError, ValueError):
                num_pieces = 0
                piece_length = 16384
            vp = getattr(pm, "verified_pieces", set())
            try:
                verified = len(vp) if isinstance(vp, (set, list, tuple)) else 0
            except (TypeError, AttributeError):
                verified = 0
            out.setdefault("pieces_total", num_pieces)
            out.setdefault("pieces_completed", verified)
            if num_pieces > 0:
                last_piece_len = piece_length
                pieces_list = getattr(pm, "pieces", None)
                if isinstance(pieces_list, (list, tuple)) and pieces_list:
                    last_idx = num_pieces - 1
                    if last_idx < len(pieces_list):
                        last_piece_len = getattr(
                            pieces_list[last_idx], "length", piece_length
                        )
                total_size = (num_pieces - 1) * piece_length + last_piece_len
                downloaded = verified * piece_length
                if verified == num_pieces:
                    downloaded = total_size
                out.setdefault("total_size", total_size)
                out.setdefault("downloaded", downloaded)
                out.setdefault("left", max(0, total_size - downloaded))
            else:
                out.setdefault("total_size", 0)
                out.setdefault("downloaded", 0)
                out.setdefault("left", 0)
        else:
            out.setdefault("pieces_total", 0)
            out.setdefault("pieces_completed", 0)
            out.setdefault("total_size", 0)
            out.setdefault("downloaded", out.get("downloaded", 0))
            out.setdefault("left", out.get("left", 0))
        out.setdefault("uploaded", out.get("uploaded", 0))
        # Canonical peer counters stay internal as connected_peers/active_peers.
        # Preserve compatibility for older local status providers that still emit `peers`.
        out.setdefault("connected_peers", out.get("peers", 0))
        out.setdefault("active_peers", 0)
        out.setdefault("output_dir", str(getattr(self.session, "output_dir", "")))
        out.setdefault("is_private", getattr(self.session, "is_private", False))
        out.setdefault(
            "torrent_file_path", getattr(self.session, "torrent_file_path", None)
        )
        out.setdefault("magnet_uri", getattr(self.session, "magnet_uri", None))
        return out

    async def get_torrent_status(self) -> dict[str, Any]:
        """Get current torrent status as canonical snapshot.

        Returns:
            Dictionary with canonical torrent status (all optional fields filled).
        """
        if not self.session.download_manager:
            minimal = self._get_minimal_status()
            return self._normalize_canonical_status(minimal)

        download_status = await self._get_download_status()
        status = dict(download_status)
        status.update(
            {
                "info_hash": self.session.info.info_hash.hex(),
                "name": self.session.info.name,
                "status": self.session.info.status,
                "added_time": self.session.info.added_time,
                "uptime": time.time() - self.session.info.added_time,
                "last_error": getattr(self.session, "_last_error", None),
                "tracker_status": getattr(
                    self.session, "_tracker_connection_status", None
                ),
                "last_tracker_error": getattr(
                    self.session, "_last_tracker_error", None
                ),
            },
        )
        return self._normalize_canonical_status(status)

    def _get_minimal_status(self) -> dict[str, Any]:
        """Get minimal status when download manager is not available."""
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
            "last_error": getattr(self.session, "_last_error", None),
            "tracker_status": getattr(self.session, "_tracker_connection_status", None),
            "last_tracker_error": getattr(self.session, "_last_tracker_error", None),
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
