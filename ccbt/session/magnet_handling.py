"""Magnet link handling utilities for session management."""

from __future__ import annotations

from typing import Any

from ccbt.session.torrent_utils import get_torrent_info


class MagnetHandler:
    """Handler for magnet link file selection and metadata operations."""

    def __init__(self, session: Any) -> None:
        """Initialize magnet handler.

        Args:
            session: AsyncTorrentSession instance

        """
        self.session = session

    async def apply_file_selection(self) -> None:
        """Apply file selection from magnet URI indices if available (BEP 53)."""
        if not self.session.magnet_info:
            return

        # Ensure file selection manager exists
        if not await self._ensure_file_selection_manager():
            return

        # Get number of files from torrent info
        torrent_info = get_torrent_info(self.session.torrent_data, self.session.logger)
        if not torrent_info or not torrent_info.files:
            return

        num_files = len(torrent_info.files)
        if num_files <= 1:
            return  # pragma: no cover - Single-file torrent early return, tested via multi-file torrents

        # Apply magnet file selection
        from ccbt.core.magnet import apply_magnet_file_selection

        respect_indices = self.session.config.discovery.magnet_respect_indices

        await apply_magnet_file_selection(
            self.session.file_selection_manager,
            self.session.magnet_info,
            num_files,
            respect_indices=respect_indices,
        )

    async def _ensure_file_selection_manager(self) -> bool:
        """Ensure file selection manager exists, creating it if needed.

        Returns:
            True if file selection manager is available, False otherwise

        """
        return self.session.ensure_file_selection_manager()
