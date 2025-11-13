"""State models for daemon state persistence.

Defines Pydantic models for serializing daemon state to msgpack format.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

# State version for migration
STATE_VERSION = "1.0"


class ComponentState(BaseModel):
    """Component state (DHT, NAT, etc.)."""

    dht_enabled: bool = Field(False, description="DHT enabled")
    dht_nodes: int = Field(0, description="Number of DHT nodes")
    nat_enabled: bool = Field(False, description="NAT traversal enabled")
    nat_mapped_ports: dict[str, int] = Field(
        default_factory=dict,
        description="NAT mapped ports (tcp, udp, dht)",
    )


class TorrentState(BaseModel):
    """Per-torrent state."""

    info_hash: str = Field(..., description="Torrent info hash (hex)")
    name: str = Field(..., description="Torrent name")
    status: str = Field(..., description="Torrent status")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Download progress")
    output_dir: str = Field(..., description="Output directory")
    added_at: float = Field(
        default_factory=time.time, description="When torrent was added"
    )
    paused: bool = Field(False, description="Whether torrent is paused")
    download_rate: float = Field(0.0, description="Download rate in bytes/sec")
    upload_rate: float = Field(0.0, description="Upload rate in bytes/sec")
    num_peers: int = Field(0, description="Number of connected peers")
    total_size: int = Field(0, description="Total size in bytes")
    downloaded: int = Field(0, description="Downloaded bytes")
    uploaded: int = Field(0, description="Uploaded bytes")
    torrent_file_path: str | None = Field(None, description="Path to torrent file")
    magnet_uri: str | None = Field(None, description="Magnet URI if added via magnet")


class SessionState(BaseModel):
    """Session-level state."""

    started_at: float = Field(
        default_factory=time.time, description="Session start time"
    )
    total_downloaded: int = Field(0, description="Total downloaded bytes")
    total_uploaded: int = Field(0, description="Total uploaded bytes")
    global_download_rate: float = Field(0.0, description="Global download rate")
    global_upload_rate: float = Field(0.0, description="Global upload rate")


class DaemonState(BaseModel):
    """Root daemon state model."""

    version: str = Field(STATE_VERSION, description="State format version")
    created_at: float = Field(
        default_factory=time.time, description="State creation time"
    )
    updated_at: float = Field(default_factory=time.time, description="Last update time")
    torrents: dict[str, TorrentState] = Field(
        default_factory=dict,
        description="Torrent states by info_hash (hex)",
    )
    session: SessionState = Field(
        default_factory=SessionState,
        description="Session-level state",
    )
    components: ComponentState = Field(
        default_factory=ComponentState,
        description="Component states",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    def model_dump_for_msgpack(self) -> dict[str, Any]:
        """Dump model for msgpack serialization.

        Converts model to dict suitable for msgpack (handles nested models).
        """
        return self.model_dump(mode="json")

    @classmethod
    def model_validate_from_msgpack(cls, data: dict[str, Any]) -> DaemonState:
        """Validate model from msgpack deserialization.

        Args:
            data: Dictionary from msgpack deserialization

        Returns:
            Validated DaemonState instance

        """
        # Convert nested dicts to models
        if "torrents" in data and isinstance(data["torrents"], dict):
            data["torrents"] = {
                k: TorrentState(**v) if isinstance(v, dict) else v
                for k, v in data["torrents"].items()
            }

        if "session" in data and isinstance(data["session"], dict):
            data["session"] = SessionState(**data["session"])

        if "components" in data and isinstance(data["components"], dict):
            data["components"] = ComponentState(**data["components"])

        return cls(**data)
