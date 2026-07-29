"""Session data models.

This module defines data models and structures used throughout the session
management system, including session context and state models.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from pathlib import Path


class TorrentStatus(str, Enum):
    """Typed torrent lifecycle status to avoid string drift."""

    STOPPED = "stopped"
    STARTING = "starting"
    DOWNLOADING = "downloading"
    SEEDING = "seeding"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class SessionContext:
    """Shared session context for controllers (composition root for a torrent session)."""

    config: Any
    torrent_data: dict[str, Any]
    output_dir: Path

    # Optional references populated during lifecycle
    info: Optional[Any] = None  # TorrentSessionInfo
    session_manager: Optional[Any] = None
    logger: Optional[Any] = None

    piece_manager: Optional[Any] = None
    peer_manager: Optional[Any] = None
    tracker: Optional[Any] = None
    dht_client: Optional[Any] = None
    checkpoint_manager: Optional[Any] = None
    download_manager: Optional[Any] = None
    file_selection_manager: Optional[Any] = None
