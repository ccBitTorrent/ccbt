"""WebSeed extension implementation (BEP 19).

from __future__ import annotations

Provides support for:
- HTTP range requests
- WebSeed peer simulation
- Integration with piece manager
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import aiohttp

from ccbt.events import Event, EventType, emit_event

if TYPE_CHECKING:
    from ccbt.models import PieceInfo


@dataclass
class WebSeedInfo:
    """WebSeed information."""

    url: str
    name: str | None = None
    is_active: bool = True
    last_accessed: float = 0.0
    bytes_downloaded: int = 0
    bytes_failed: int = 0
    success_rate: float = 1.0


class WebSeedExtension:
    """WebSeed extension implementation (BEP 19)."""

    def __init__(self):
        """Initialize WebSeed extension."""
        self.webseeds: dict[str, WebSeedInfo] = {}
        self.session: aiohttp.ClientSession | None = None
        self.timeout = aiohttp.ClientTimeout(total=30.0)

    async def start(self) -> None:
        """Start WebSeed extension."""
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def stop(self) -> None:
        """Stop WebSeed extension."""
        if self.session:
            await self.session.close()
            self.session = None

    def add_webseed(self, url: str, name: str | None = None) -> str:
        """Add WebSeed URL."""
        webseed_id = url
        self.webseeds[webseed_id] = WebSeedInfo(
            url=url,
            name=name or urlparse(url).netloc,
        )

        # Emit event for WebSeed added
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                emit_event(
                    Event(
                        event_type=EventType.WEBSEED_ADDED.value,
                        data={
                            "webseed_id": webseed_id,
                            "url": url,
                            "name": name,
                            "timestamp": time.time(),
                        },
                    ),
                )
            )
            # Store reference to prevent garbage collection
            _ = task
        except RuntimeError:
            # No event loop running, skip event emission
            pass

        return webseed_id

    def remove_webseed(self, webseed_id: str) -> None:
        """Remove WebSeed."""
        if webseed_id in self.webseeds:
            del self.webseeds[webseed_id]

            # Emit event for WebSeed removed
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(
                    emit_event(
                        Event(
                            event_type=EventType.WEBSEED_REMOVED.value,
                            data={
                                "webseed_id": webseed_id,
                                "timestamp": time.time(),
                            },
                        ),
                    )
                )
                # Store reference to prevent garbage collection
                _ = task
            except RuntimeError:
                # No event loop running, skip event emission
                pass

    def get_webseed(self, webseed_id: str) -> WebSeedInfo | None:
        """Get WebSeed information."""
        return self.webseeds.get(webseed_id)

    def list_webseeds(self) -> dict[str, WebSeedInfo]:
        """List all WebSeeds."""
        return self.webseeds.copy()

    async def download_piece(
        self,
        webseed_id: str,
        piece_info: PieceInfo,
        _piece_data: bytes,
    ) -> bytes | None:
        """Download piece from WebSeed."""
        if webseed_id not in self.webseeds:
            return None

        webseed = self.webseeds[webseed_id]
        if not webseed.is_active:
            return None

        try:
            if self.session is None:
                await self.start()

            # Calculate range for piece
            start_byte = piece_info.index * piece_info.length
            end_byte = start_byte + piece_info.length - 1

            # Make HTTP range request
            headers = {
                "Range": f"bytes={start_byte}-{end_byte}",
            }

            if self.session is None:
                return None
            async with self.session.get(webseed.url, headers=headers) as response:
                if response.status == 206:  # Partial Content
                    data = await response.read()

                    # Update WebSeed statistics
                    webseed.last_accessed = time.time()
                    webseed.bytes_downloaded += len(data)
                    webseed.success_rate = webseed.bytes_downloaded / (
                        webseed.bytes_downloaded + webseed.bytes_failed
                    )

                    # Emit event for successful download
                    await emit_event(
                        Event(
                            event_type=EventType.WEBSEED_DOWNLOAD_SUCCESS.value,
                            data={
                                "webseed_id": webseed_id,
                                "piece_index": piece_info.index,
                                "bytes_downloaded": len(data),
                                "timestamp": time.time(),
                            },
                        ),
                    )

                    return data
                # Update failure statistics
                webseed.bytes_failed += piece_info.length
                webseed.success_rate = webseed.bytes_downloaded / (
                    webseed.bytes_downloaded + webseed.bytes_failed
                )

                # Emit event for failed download
                await emit_event(
                    Event(
                        event_type=EventType.WEBSEED_DOWNLOAD_FAILED.value,
                        data={
                            "webseed_id": webseed_id,
                            "piece_index": piece_info.index,
                            "status_code": response.status,
                            "timestamp": time.time(),
                        },
                    ),
                )

                return None

        except Exception as e:
            # Update failure statistics
            webseed.bytes_failed += piece_info.length
            webseed.success_rate = webseed.bytes_downloaded / (
                webseed.bytes_downloaded + webseed.bytes_failed
            )

            # Emit event for error
            await emit_event(
                Event(
                    event_type=EventType.WEBSEED_ERROR.value,
                    data={
                        "webseed_id": webseed_id,
                        "piece_index": piece_info.index,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return None

    async def download_piece_range(
        self,
        webseed_id: str,
        start_byte: int,
        length: int,
    ) -> bytes | None:
        """Download specific byte range from WebSeed."""
        if webseed_id not in self.webseeds:
            return None

        webseed = self.webseeds[webseed_id]
        if not webseed.is_active:
            return None

        try:
            if self.session is None:
                await self.start()

            # Calculate range
            end_byte = start_byte + length - 1

            # Make HTTP range request
            headers = {
                "Range": f"bytes={start_byte}-{end_byte}",
            }

            if self.session is None:
                return None
            async with self.session.get(webseed.url, headers=headers) as response:
                if response.status == 206:  # Partial Content
                    data = await response.read()

                    # Update WebSeed statistics
                    webseed.last_accessed = time.time()
                    webseed.bytes_downloaded += len(data)
                    webseed.success_rate = webseed.bytes_downloaded / (
                        webseed.bytes_downloaded + webseed.bytes_failed
                    )

                    return data
                # Update failure statistics
                webseed.bytes_failed += length
                webseed.success_rate = webseed.bytes_downloaded / (
                    webseed.bytes_downloaded + webseed.bytes_failed
                )

                return None

        except Exception:
            # Update failure statistics
            webseed.bytes_failed += length
            webseed.success_rate = webseed.bytes_downloaded / (
                webseed.bytes_downloaded + webseed.bytes_failed
            )

            return None

    def get_best_webseed(self) -> str | None:
        """Get best WebSeed based on success rate and activity."""
        if not self.webseeds:
            return None

        best_webseed_id = None
        best_score = -1.0

        for webseed_id, webseed in self.webseeds.items():
            if not webseed.is_active:
                continue

            # Calculate score based on success rate and recency
            recency_score = (
                1.0 - (time.time() - webseed.last_accessed) / 3600.0
            )  # 1 hour decay
            recency_score = max(0.0, recency_score)

            score = webseed.success_rate * 0.7 + recency_score * 0.3

            if score > best_score:
                best_score = score
                best_webseed_id = webseed_id

        return best_webseed_id

    def get_webseed_statistics(self, webseed_id: str) -> dict[str, Any] | None:
        """Get WebSeed statistics."""
        webseed = self.webseeds.get(webseed_id)
        if not webseed:
            return None

        return {
            "url": webseed.url,
            "name": webseed.name,
            "is_active": webseed.is_active,
            "last_accessed": webseed.last_accessed,
            "bytes_downloaded": webseed.bytes_downloaded,
            "bytes_failed": webseed.bytes_failed,
            "success_rate": webseed.success_rate,
            "total_bytes": webseed.bytes_downloaded + webseed.bytes_failed,
        }

    def get_all_statistics(self) -> dict[str, Any]:
        """Get all WebSeed statistics."""
        total_bytes_downloaded = 0
        total_bytes_failed = 0
        active_webseeds = 0

        for webseed in self.webseeds.values():
            total_bytes_downloaded += webseed.bytes_downloaded
            total_bytes_failed += webseed.bytes_failed
            if webseed.is_active:
                active_webseeds += 1

        total_bytes = total_bytes_downloaded + total_bytes_failed
        overall_success_rate = (
            total_bytes_downloaded / total_bytes if total_bytes > 0 else 0.0
        )

        return {
            "total_webseeds": len(self.webseeds),
            "active_webseeds": active_webseeds,
            "total_bytes_downloaded": total_bytes_downloaded,
            "total_bytes_failed": total_bytes_failed,
            "overall_success_rate": overall_success_rate,
        }

    def set_webseed_active(self, webseed_id: str, active: bool) -> None:
        """Set WebSeed active status."""
        if webseed_id in self.webseeds:
            self.webseeds[webseed_id].is_active = active

    def reset_webseed_statistics(self, webseed_id: str) -> None:
        """Reset WebSeed statistics."""
        if webseed_id in self.webseeds:
            webseed = self.webseeds[webseed_id]
            webseed.bytes_downloaded = 0
            webseed.bytes_failed = 0
            webseed.success_rate = 1.0
            webseed.last_accessed = 0.0

    def reset_all_statistics(self) -> None:
        """Reset all WebSeed statistics."""
        for webseed in self.webseeds.values():
            webseed.bytes_downloaded = 0
            webseed.bytes_failed = 0
            webseed.success_rate = 1.0
            webseed.last_accessed = 0.0

    async def health_check(self, webseed_id: str) -> bool:
        """Perform health check on WebSeed."""
        if webseed_id not in self.webseeds:
            return False

        webseed = self.webseeds[webseed_id]
        if not webseed.is_active:
            return False

        try:
            if self.session is None:
                await self.start()

            # Make HEAD request to check availability
            if self.session is None:
                return False
            async with self.session.head(webseed.url) as response:
                return response.status == 200

        except Exception:
            return False

    async def health_check_all(self) -> dict[str, bool]:
        """Perform health check on all WebSeeds."""
        results = {}

        for webseed_id in self.webseeds:
            results[webseed_id] = await self.health_check(webseed_id)

        return results
