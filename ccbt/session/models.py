from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class TorrentStatus(str, Enum):
    """Typed torrent lifecycle status to avoid string drift."""

    STOPPED = "stopped"
    STARTING = "starting"
    DOWNLOADING = "downloading"
    SEEDING = "seeding"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class SessionContext:
    """Shared session context for controllers (composition root for a torrent session)."""

    config: Any
    torrent_data: dict[str, Any]
    output_dir: Path

    # Optional references populated during lifecycle
    info: Any | None = None  # TorrentSessionInfo
    session_manager: Any | None = None
    logger: Any | None = None

    piece_manager: Any | None = None
    peer_manager: Any | None = None
    tracker: Any | None = None
    dht_client: Any | None = None
    checkpoint_manager: Any | None = None
    download_manager: Any | None = None
    file_selection_manager: Any | None = None
