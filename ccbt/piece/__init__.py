"""Piece management and metadata exchange.

This module handles piece selection, metadata exchange, and piece state management.
"""

from __future__ import annotations

from ccbt.piece.async_metadata_exchange import AsyncMetadataExchange
from ccbt.piece.async_metadata_exchange import (
    fetch_metadata_from_peers as fetch_metadata_from_peers_async,
)
from ccbt.piece.async_piece_manager import AsyncPieceManager
from ccbt.piece.metadata_exchange import fetch_metadata_from_peers
from ccbt.piece.piece_manager import PieceManager

__all__ = [
    "AsyncMetadataExchange",
    "AsyncPieceManager",
    "PieceManager",
    "fetch_metadata_from_peers",
    "fetch_metadata_from_peers_async",
]
