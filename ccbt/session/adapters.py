from __future__ import annotations

from typing import Any, Callable

from ccbt.session.types import DHTClientProtocol, TrackerClientProtocol


class DHTAdapter(DHTClientProtocol):
    """Adapter to expose a concrete DHT client behind DHTClientProtocol."""

    def __init__(self, dht_client: Any) -> None:
        self._dht = dht_client

    def add_peer_callback(
        self,
        callback: Callable[[list[tuple[str, int]]], None],
        info_hash: bytes | None = None,
    ) -> None:
        self._dht.add_peer_callback(callback, info_hash=info_hash)

    async def get_peers(
        self, info_hash: bytes, max_peers: int = 50
    ) -> list[tuple[str, int]]:
        return await self._dht.get_peers(info_hash, max_peers=max_peers)

    async def wait_for_bootstrap(self, timeout: float = 10.0) -> bool:
        if hasattr(self._dht, "wait_for_bootstrap"):
            return await self._dht.wait_for_bootstrap(timeout=timeout)
        return True


class TrackerAdapter(TrackerClientProtocol):
    """Adapter to expose a concrete tracker client behind TrackerClientProtocol."""

    def __init__(self, tracker_client: Any) -> None:
        self._tracker = tracker_client

    async def start(self) -> None:
        if hasattr(self._tracker, "start"):
            await self._tracker.start()

    async def stop(self) -> None:
        if hasattr(self._tracker, "stop"):
            await self._tracker.stop()

    async def announce(
        self,
        torrent_data: dict[str, Any],
        port: int,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int | None = None,
        event: str = "started",
    ) -> Any:
        if hasattr(self._tracker, "announce"):
            return await self._tracker.announce(
                torrent_data,
                port=port,
                uploaded=uploaded,
                downloaded=downloaded,
                left=left,
                event=event,
            )
        return {}

    async def announce_to_multiple(
        self,
        torrent_data: dict[str, Any],
        tracker_urls: list[str],
        port: int,
        event: str = "started",
    ) -> list[Any]:
        if hasattr(self._tracker, "announce_to_multiple"):
            return await self._tracker.announce_to_multiple(
                torrent_data, tracker_urls, port=port, event=event
            )
        # Fallback: single announce path
        if hasattr(self._tracker, "announce"):
            result = await self._tracker.announce(torrent_data, port=port, event=event)
            return [result]
        return []

    async def scrape(self, torrent_data: dict[str, Any]) -> dict[str, Any]:
        if hasattr(self._tracker, "scrape"):
            return await self._tracker.scrape(torrent_data)
        return {}
