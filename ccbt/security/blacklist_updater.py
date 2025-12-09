"""Blacklist Updater for ccBitTorrent.

from __future__ import annotations

Provides automatic blacklist updates from external sources.
"""

from __future__ import annotations

import asyncio
import csv
import ipaddress
import json
import logging
from io import StringIO
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from ccbt.security.security_manager import SecurityManager

logger = logging.getLogger(__name__)


class BlacklistUpdater:
    """Automatic blacklist update manager."""

    def __init__(
        self,
        security_manager: SecurityManager,
        update_interval: float = 3600.0,
        sources: list[str] | None = None,
        local_source_config: Any | None = None,
    ):
        """Initialize blacklist updater.

        Args:
            security_manager: SecurityManager instance
            update_interval: Update interval in seconds
            sources: List of source URLs to update from
            local_source_config: LocalBlacklistSourceConfig instance

        """
        self.security_manager = security_manager
        self.update_interval = update_interval
        self.sources = sources or []
        self._update_task: asyncio.Task | None = None
        self._local_source: Any | None = None
        self._local_source_config = local_source_config

    async def update_from_source(self, source_url: str) -> int:
        """Update blacklist from a single source URL.

        Supports:
        - Plain text files (one IP per line)
        - JSON format: {"ips": ["1.2.3.4", ...]}
        - CSV format

        Args:
            source_url: URL to download blacklist from

        Returns:
            Number of IPs added to blacklist

        """
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(source_url) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "Failed to fetch blacklist from %s: HTTP %d",
                            source_url,
                            resp.status,
                        )
                        return 0

                    content = await resp.text()
                    ips = self._parse_blacklist_content(content, source_url)

                    added = 0
                    for ip in ips:
                        if self._is_valid_ip(ip) and ip not in self.security_manager.blacklist_entries:
                            self.security_manager.add_to_blacklist(
                                ip, f"Auto-updated from {source_url}", source="auto"
                            )
                            added += 1

                    logger.info("Updated %d IPs from %s", added, source_url)
                    return added
        except asyncio.TimeoutError:
            logger.warning("Timeout downloading blacklist from %s", source_url)
            return 0
        except aiohttp.ClientError as e:
            logger.warning("Network error downloading from %s: %s", source_url, e)
            return 0
        except Exception as e:
            logger.warning("Error updating from %s: %s", source_url, e)
            return 0

    async def start_auto_update(self) -> None:
        """Start automatic update task."""
        if self._update_task and not self._update_task.done():
            logger.warning("Auto-update task already running")
            return

        # Initialize local source if configured
        if self._local_source_config and getattr(self._local_source_config, "enabled", False):
            from ccbt.security.local_blacklist_source import LocalBlacklistSource

            self._local_source = LocalBlacklistSource(
                self.security_manager,
                evaluation_interval=getattr(
                    self._local_source_config, "evaluation_interval", 300.0
                ),
                metric_window=getattr(
                    self._local_source_config, "metric_window", 3600.0
                ),
                thresholds=getattr(self._local_source_config, "thresholds", {}),
                expiration_hours=getattr(
                    self._local_source_config, "expiration_hours", 24.0
                ),
                min_observations=getattr(
                    self._local_source_config, "min_observations", 3
                ),
            )
            # Start local source evaluation
            await self._local_source.start_evaluation()
            logger.info("Started local blacklist source evaluation")

        async def update_loop():
            while True:
                try:
                    await asyncio.sleep(self.update_interval)
                    logger.info("Starting automatic blacklist update...")

                    for source in self.sources:
                        await self.update_from_source(source)

                    # Save after updates
                    try:
                        await self.security_manager.save_blacklist()
                    except Exception as e:
                        logger.warning("Failed to save blacklist after update: %s", e)
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Error in blacklist auto-update")
                    await asyncio.sleep(60)  # Retry after 1 minute

        self._update_task = asyncio.create_task(update_loop())
        logger.info(
            "Started blacklist auto-update (interval: %ss)", self.update_interval
        )

    def stop_auto_update(self) -> None:
        """Stop auto-update background task."""
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            logger.info("Stopped blacklist auto-update task")
        
        # Stop local source if running
        if self._local_source:
            self._local_source.stop_evaluation()

    def _parse_blacklist_content(self, content: str, source_url: str) -> list[str]:
        """Parse blacklist content and extract IP addresses.

        Args:
            content: Content to parse
            source_url: Source URL (for format detection)

        Returns:
            List of IP addresses

        """
        # Try JSON first
        if content.strip().startswith("{"):
            return self._parse_json(content)

        # Try CSV
        if "," in content and "\n" in content:
            try:
                return self._parse_csv(content)
            except Exception:
                pass

        # Default to plain text (one IP per line)
        return self._parse_plain_text(content)

    def _parse_plain_text(self, content: str) -> list[str]:
        """Parse plain text format (one IP per line).

        Args:
            content: Plain text content

        Returns:
            List of IP addresses

        """
        ips = []
        for line in content.splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Extract IP (may have comments after)
            ip_part = line.split()[0] if " " in line else line
            if self._is_valid_ip(ip_part):
                ips.append(ip_part)
        return ips

    def _parse_json(self, content: str) -> list[str]:
        """Parse JSON format.

        Expected format: {"ips": ["1.2.3.4", ...]} or ["1.2.3.4", ...]

        Args:
            content: JSON content

        Returns:
            List of IP addresses

        """
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                # Format: {"ips": [...]}
                ips = data.get("ips", [])
            elif isinstance(data, list):
                # Format: ["1.2.3.4", ...]
                ips = data
            else:
                return []

            return [ip for ip in ips if isinstance(ip, str) and self._is_valid_ip(ip)]
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON blacklist content")
            return []

    def _parse_csv(self, content: str) -> list[str]:
        """Parse CSV format.

        Args:
            content: CSV content

        Returns:
            List of IP addresses

        """
        ips = []
        try:
            reader = csv.reader(StringIO(content))
            for row in reader:
                if not row:
                    continue
                # Try first column as IP
                for cell in row:
                    cell = cell.strip()
                    if self._is_valid_ip(cell):
                        ips.append(cell)
                        break
        except Exception:
            logger.warning("Failed to parse CSV blacklist content")
        return ips

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format.

        Args:
            ip: IP address string to validate

        Returns:
            True if valid IP address

        """
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False


