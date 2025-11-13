from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class DHTClientProtocol(Protocol):
    """Protocol for DHT client interactions used by the session layer."""

    def add_peer_callback(
        self,
        callback: Callable[[list[tuple[str, int]]], None],
        info_hash: bytes | None = None,
    ) -> None: ...

    async def get_peers(
        self, info_hash: bytes, max_peers: int = 50
    ) -> list[tuple[str, int]]: ...

    async def wait_for_bootstrap(
        self, timeout: float = 10.0
    ) -> bool:  # optional in implementations
        ...


@runtime_checkable
class TrackerClientProtocol(Protocol):
    """Protocol for tracker client interactions."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def announce(  # pragma: no cover - protocol definition only
        self,
        torrent_data: dict[str, Any],
        port: int,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int | None = None,
        event: str = "started",
    ) -> Any: ...

    async def announce_to_multiple(  # pragma: no cover - protocol definition only
        self,
        torrent_data: dict[str, Any],
        tracker_urls: list[str],
        port: int,
        event: str = "started",
    ) -> list[Any]: ...

    async def scrape(self, torrent_data: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class PeerManagerProtocol(Protocol):
    """Protocol for peer connection manager."""

    async def start(self) -> None: ...

    async def connect_to_peers(self, peers: list[dict[str, Any]]) -> None: ...

    async def broadcast_have(self, piece_index: int) -> Any: ...

    # Event hooks (settable attributes in concrete implementations)
    on_peer_connected: Any
    on_peer_disconnected: Any
    on_piece_received: Any
    on_bitfield_received: Any


@runtime_checkable
class PieceManagerProtocol(Protocol):
    """Protocol for piece manager."""

    async def start(self) -> None: ...

    async def start_download(self, peer_manager: Any) -> None: ...

    async def get_checkpoint_state(
        self, name: str, info_hash: bytes, output_dir: str
    ) -> Any: ...

    # Optional callbacks the session/binder may set
    on_piece_completed: Any
    on_piece_verified: Any
    on_download_complete: Any
    on_checkpoint_save: Any


@runtime_checkable
class CheckpointStoreProtocol(Protocol):
    """Protocol for checkpoint storage/manager."""

    async def save_checkpoint(self, checkpoint: Any) -> None: ...

    async def load_checkpoint(self, info_hash: bytes) -> Any: ...

    async def backup_checkpoint(
        self,
        info_hash: bytes,
        destination: Any,
        compress: bool = True,
        encrypt: bool = False,
    ) -> Any: ...
