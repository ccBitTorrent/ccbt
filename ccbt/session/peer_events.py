from __future__ import annotations

from typing import Callable

from ccbt.session.models import SessionContext
from ccbt.session.types import PeerManagerProtocol, PieceManagerProtocol


class PeerEventsBinder:
    """Bind/unbind peer and piece events for a session."""

    def __init__(self, ctx: SessionContext) -> None:
        self._ctx = ctx

    def bind_peer_manager(
        self,
        peer_manager: PeerManagerProtocol,
        *,
        on_peer_connected: Callable[..., None] | None = None,
        on_peer_disconnected: Callable[..., None] | None = None,
        on_piece_received: Callable[..., None] | None = None,
        on_bitfield_received: Callable[..., None] | None = None,
    ) -> None:
        if on_peer_connected is not None:
            peer_manager.on_peer_connected = on_peer_connected  # type: ignore[attr-defined]
        if on_peer_disconnected is not None:
            peer_manager.on_peer_disconnected = on_peer_disconnected  # type: ignore[attr-defined]
        if on_piece_received is not None:
            peer_manager.on_piece_received = on_piece_received  # type: ignore[attr-defined]
        if on_bitfield_received is not None:
            peer_manager.on_bitfield_received = on_bitfield_received  # type: ignore[attr-defined]
        self._ctx.peer_manager = peer_manager

    def bind_piece_manager(
        self,
        piece_manager: PieceManagerProtocol,
        *,
        on_piece_completed: Callable[[int], None] | None = None,
        on_piece_verified: Callable[[int], None] | None = None,
        on_download_complete: Callable[[], None] | None = None,
    ) -> None:
        if on_piece_completed is not None:
            piece_manager.on_piece_completed = on_piece_completed  # type: ignore[attr-defined]
        if on_piece_verified is not None:
            piece_manager.on_piece_verified = on_piece_verified  # type: ignore[attr-defined]
        if on_download_complete is not None:
            piece_manager.on_download_complete = on_download_complete  # type: ignore[attr-defined]
        self._ctx.piece_manager = piece_manager
