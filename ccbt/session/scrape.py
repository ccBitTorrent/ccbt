"""Scrape operations for tracker statistics."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ccbt.models import ScrapeResult


class ScrapeManager:
    """Manager for tracker scrape operations and caching."""

    def __init__(self, manager: Any) -> None:
        """Initialize scrape manager.

        Args:
            manager: AsyncSessionManager instance

        """
        self.manager = manager
        self.config = manager.config
        self.logger = manager.logger

    async def force_scrape(self, info_hash_hex: str) -> bool:
        """Force tracker scrape for a torrent.

        Args:
            info_hash_hex: Info hash in hex format (40 characters)

        Returns:
            True if scrape was successful, False otherwise

        """
        try:
            # Validate and convert info_hash
            if len(info_hash_hex) != 40:
                self.logger.debug("Invalid info_hash length: %d", len(info_hash_hex))
                return False

            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError as e:
            self.logger.debug("Invalid info_hash format: %s", e)
            return False

        # Find torrent session
        async with self.manager.lock:
            session = self.manager.torrents.get(info_hash)

        if not session:
            self.logger.debug("Torrent not found: %s", info_hash_hex)
            return False

        # Get torrent data and convert to TorrentInfo
        try:
            from ccbt.models import TorrentInfo

            torrent_data = session.torrent_data

            # Convert to TorrentInfo if needed
            if isinstance(torrent_data, dict):
                # Normalize announce_list to list[list[str]] format (BEP 12)
                raw_announce_list = torrent_data.get("announce_list")
                normalized_announce_list: list[list[str]] | None = None
                if raw_announce_list and isinstance(raw_announce_list, list):
                    normalized_announce_list = []
                    for item in raw_announce_list:
                        if isinstance(item, list):
                            # Already in correct format (list of lists)
                            normalized_announce_list.append(item)
                        elif isinstance(item, str):
                            # Flat list format (from magnet parsing) - wrap in list
                            normalized_announce_list.append([item])
                        # If empty after normalization, set to None
                        if not normalized_announce_list:
                            normalized_announce_list = None

                # Build TorrentInfo from dict
                torrent_info = TorrentInfo(
                    name=torrent_data.get("name", "Unknown"),
                    info_hash=torrent_data.get("info_hash", info_hash),
                    announce=torrent_data.get("announce", ""),
                    announce_list=normalized_announce_list,
                    files=[],
                    total_length=torrent_data.get("total_length", 0),
                    # CRITICAL FIX: Handle None values (common for magnet links)
                    piece_length=(torrent_data.get("file_info") or {}).get(
                        "piece_length", 16384
                    ),
                    pieces=[],
                    num_pieces=0,
                )
            elif hasattr(torrent_data, "model_dump"):
                # It's already a Pydantic model
                torrent_info = torrent_data
            else:
                self.logger.debug(
                    "Unsupported torrent_data type: %s", type(torrent_data)
                )
                return False

            # Create BitTorrentProtocol instance for scraping
            from ccbt.protocols.bittorrent import BitTorrentProtocol

            protocol = BitTorrentProtocol(session_manager=self.manager)

            # Scrape torrent
            stats = await protocol.scrape_torrent(torrent_info)

            # Check if scrape was successful (at least one non-zero stat)
            success = stats.get("seeders", 0) > 0 or stats.get("leechers", 0) > 0

            if success:
                self.logger.info(
                    "Scrape successful for %s: seeders=%d, leechers=%d, completed=%d",
                    info_hash_hex,
                    stats.get("seeders", 0),
                    stats.get("leechers", 0),
                    stats.get("completed", 0),
                )

                # Cache scrape result (BEP 48)
                scrape_result = ScrapeResult(
                    info_hash=info_hash,
                    seeders=stats.get("seeders", 0),
                    leechers=stats.get("leechers", 0),
                    completed=stats.get("completed", 0),
                    last_scrape_time=time.time(),
                    scrape_count=1,
                )

                async with self.manager.scrape_cache_lock:
                    # Update or create cache entry
                    if info_hash in self.manager.scrape_cache:
                        old_result = self.manager.scrape_cache[info_hash]
                        scrape_result.scrape_count = old_result.scrape_count + 1
                    self.manager.scrape_cache[info_hash] = scrape_result
            else:
                self.logger.debug("Scrape returned zero stats for %s", info_hash_hex)

            return success

        except Exception:
            self.logger.exception("Error during force_scrape for %s", info_hash_hex)
            return False

    async def get_cached_result(self, info_hash_hex: str) -> Any | None:
        """Get cached scrape result for a torrent.

        Args:
            info_hash_hex: Info hash in hex format (40 characters)

        Returns:
            ScrapeResult if cached, None otherwise

        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return None

        async with self.manager.scrape_cache_lock:
            return self.manager.scrape_cache.get(info_hash)

    def is_stale(self, scrape_result: Any) -> bool:
        """Check if scrape result is stale based on interval.

        Args:
            scrape_result: Cached scrape result (ScrapeResult)

        Returns:
            True if scrape is stale and should be refreshed

        """
        if scrape_result.last_scrape_time == 0.0:
            return True

        elapsed = time.time() - scrape_result.last_scrape_time
        return elapsed >= self.config.discovery.tracker_scrape_interval

    async def auto_scrape(self, info_hash_hex: str) -> None:
        """Auto-scrape a torrent after adding (background task).

        Args:
            info_hash_hex: Info hash in hex format

        """
        try:
            # Wait a short delay to ensure torrent is fully initialized
            await asyncio.sleep(2.0)

            # Perform scrape
            await self.force_scrape(info_hash_hex)

            self.logger.debug("Auto-scrape completed for %s", info_hash_hex)
        except Exception:
            self.logger.debug("Auto-scrape failed for %s", info_hash_hex, exc_info=True)

    async def start_periodic_loop(self) -> None:
        """Periodic background task to scrape all active torrents.

        Runs every `tracker_scrape_interval` seconds.
        """
        interval = self.config.discovery.tracker_scrape_interval

        while True:
            try:
                # Wait for interval
                await asyncio.sleep(interval)

                # Get all active torrents
                async with self.manager.lock:
                    active_info_hashes = [
                        info_hash.hex() for info_hash in self.manager.torrents
                    ]

                # Scrape each torrent (with rate limiting)
                for info_hash_hex in active_info_hashes:
                    # Check if scrape is needed (not stale)
                    cached = await self.get_cached_result(info_hash_hex)
                    if cached and not self.is_stale(cached):
                        continue  # Skip if recently scraped  # pragma: no cover - Skip stale scrape, tested via integration tests with fresh scrape data

                    # Perform scrape
                    await self.force_scrape(info_hash_hex)

                    # Rate limit: wait 1 second between scrapes
                    await asyncio.sleep(1.0)

            except asyncio.CancelledError:  # pragma: no cover - background loop cancellation, tested via cancellation
                break  # pragma: no cover
            except Exception:
                self.logger.exception("Error in periodic scrape loop")
                await asyncio.sleep(60.0)  # Wait before retry on error
