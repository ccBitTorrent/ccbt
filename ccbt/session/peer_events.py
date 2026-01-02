"""Peer event handling.

This module provides event binding and handling for peer-related events,
including connection events, message events, and state changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from ccbt.session.models import SessionContext
    from ccbt.session.types import PeerManagerProtocol, PieceManagerProtocol


class PeerEventsBinder:
    """Bind/unbind peer and piece events for a session."""

    def __init__(self, ctx: SessionContext) -> None:
        """Initialize the peer events binder with session context."""
        self._ctx = ctx

    def bind_peer_manager(
        self,
        peer_manager: PeerManagerProtocol,
        *,
        on_peer_connected: Optional[Callable[..., None]] = None,
        on_peer_disconnected: Optional[Callable[..., None]] = None,
        on_piece_received: Optional[Callable[..., None]] = None,
        on_bitfield_received: Optional[Callable[..., None]] = None,
    ) -> None:
        """Bind peer manager and event callbacks.

        Args:
            peer_manager: The peer manager protocol instance
            on_peer_connected: Optional callback for peer connection events
            on_peer_disconnected: Optional callback for peer disconnection events
            on_piece_received: Optional callback for piece received events
            on_bitfield_received: Optional callback for bitfield received events

        """
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
        on_piece_completed: Optional[Callable[[int], None]] = None,
        on_piece_verified: Optional[Callable[[int], None]] = None,
        on_download_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        """Bind piece manager and event callbacks.

        Args:
            piece_manager: The piece manager protocol instance
            on_piece_completed: Optional callback for piece completion events
            on_piece_verified: Optional callback for piece verification events
            on_download_complete: Optional callback for download completion

        """
        if on_piece_completed is not None:
            piece_manager.on_piece_completed = on_piece_completed  # type: ignore[attr-defined]
        if on_piece_verified is not None:
            piece_manager.on_piece_verified = on_piece_verified  # type: ignore[attr-defined]
        if on_download_complete is not None:
            piece_manager.on_download_complete = on_download_complete  # type: ignore[attr-defined]
        self._ctx.piece_manager = piece_manager
