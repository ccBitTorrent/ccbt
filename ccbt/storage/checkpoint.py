"""Checkpoint management for ccBitTorrent.

from __future__ import annotations

Provides comprehensive checkpointing functionality for download resume,
including JSON and binary checkpoint_formats, validation, and cleanup.
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import hashlib
import json
import os
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import zstandard as zstd  # type: ignore[unresolved-import]

    HAS_ZSTD = True
except Exception:  # pragma: no cover - zstandard import error, fallback to gzip, tested via conditional import
    HAS_ZSTD = False
    zstd = None  # type: ignore[assignment]

try:
    import msgpack

    HAS_MSGPACK = True
except Exception:  # pragma: no cover - Import exception handling, tested via mocking
    HAS_MSGPACK = False
    msgpack = None  # type: ignore[assignment]

from ccbt.models import (
    CheckpointFormat,
    DiskConfig,
    DownloadStats,
    FileCheckpoint,
    GlobalCheckpoint,
    PieceState,
    TorrentCheckpoint,
)
from ccbt.utils.exceptions import (
    CheckpointCorruptedError,
    CheckpointError,
    CheckpointNotFoundError,
    CheckpointVersionError,
)
from ccbt.utils.logging_config import get_logger

# Re-export TorrentCheckpoint and GlobalCheckpointManager for convenience
__all__ = [
    "CheckpointFileInfo",
    "CheckpointManager",
    "GlobalCheckpointManager",
    "TorrentCheckpoint",
]


@dataclass
class CheckpointFileInfo:
    """Incheckpoint_formation about a checkpoint file."""

    path: Path
    info_hash: bytes
    created_at: float
    updated_at: float
    size: int
    checkpoint_format: CheckpointFormat


class CheckpointManager:
    """Manages torrent download checkpoints with JSON and binary checkpoint_formats."""

    # Binary checkpoint_format constants
    MAGIC_BYTES = b"CCBT"
    VERSION = 1

    def __init__(self, config: DiskConfig | None = None):
        """Initialize checkpoint manager.

        Args:
            config: Disk configuration with checkpoint settings

        """
        self.config = config or DiskConfig()
        self.logger = get_logger(__name__)

        # Determine checkpoint directory
        if self.config.checkpoint_dir:
            self.checkpoint_dir = Path(self.config.checkpoint_dir)
        else:
            # Default to download_dir/.ccbt/checkpoints
            self.checkpoint_dir = Path(".ccbt/checkpoints")

        # Ensure checkpoint directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Track last checkpoint state for incremental saves and deduplication
        self._last_checkpoint_hash: bytes | None = None
        self._last_checkpoint: TorrentCheckpoint | None = None

        self.logger.info(
            "Checkpoint manager initialized with directory: %s",
            self.checkpoint_dir,
        )

    def _get_checkpoint_path(
        self, info_hash: bytes, checkpoint_format: CheckpointFormat
    ) -> Path:
        """Get checkpoint file path for given info hash and checkpoint_format."""
        info_hash_hex = info_hash.hex()

        if checkpoint_format == CheckpointFormat.JSON:
            return self.checkpoint_dir / f"{info_hash_hex}.checkpoint.json"
        if checkpoint_format == CheckpointFormat.BINARY:
            # Determine extension based on compression algorithm
            if self.config.checkpoint_compression:
                algo = self.config.checkpoint_compression_algorithm.lower()
                if algo == "zstd" and HAS_ZSTD:
                    ext = ".checkpoint.bin.zst"
                else:  # pragma: no cover - gzip fallback path, zstd is default when available
                    ext = ".checkpoint.bin.gz"
            else:  # pragma: no cover - Non-compressed checkpoint path, compression is default
                ext = ".checkpoint.bin"
            return self.checkpoint_dir / f"{info_hash_hex}{ext}"
        msg = f"Invalid checkpoint checkpoint_format: {checkpoint_format}"
        raise ValueError(
            msg
        )  # pragma: no cover - Invalid checkpoint format validation, defensive error handling

    def _calculate_checkpoint_hash(self, checkpoint: TorrentCheckpoint) -> bytes:
        """Calculate hash of checkpoint state for deduplication.

        Args:
            checkpoint: Checkpoint to hash

        Returns:
            SHA-256 hash of checkpoint state

        """
        # Create a deterministic representation of the checkpoint
        # Include key fields that indicate meaningful changes
        key_data = {
            "info_hash": checkpoint.info_hash.hex(),
            "verified_pieces": sorted(checkpoint.verified_pieces),
            "total_pieces": checkpoint.total_pieces,
            "piece_states": {
                str(k): v.value if hasattr(v, "value") else str(v)
                for k, v in checkpoint.piece_states.items()
            },
            "updated_at": checkpoint.updated_at,
        }
        # Serialize to JSON for hashing
        json_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).digest()

    async def save_checkpoint(
        self,
        checkpoint: TorrentCheckpoint,
        checkpoint_format: CheckpointFormat | None = None,
    ) -> Path:
        """Save checkpoint to disk.

        Args:
            checkpoint: Checkpoint data to save
            checkpoint_format: Format to save in (uses config default if None)

        Returns:
            Path to saved checkpoint file

        Raises:
            CheckpointError: If saving fails

        """
        if not self.config.checkpoint_enabled:  # pragma: no cover - Checkpoint disabled path, tested but not all branches covered
            msg = "Checkpointing is disabled"
            raise CheckpointError(msg)

        # Check for deduplication
        if self.config.checkpoint_deduplication:
            current_hash = self._calculate_checkpoint_hash(checkpoint)
            if self._last_checkpoint_hash == current_hash:
                self.logger.debug("Checkpoint unchanged, skipping save")
                # Return existing path
                checkpoint_format = checkpoint_format or self.config.checkpoint_format
                return self._get_checkpoint_path(
                    checkpoint.info_hash, checkpoint_format
                )
            self._last_checkpoint_hash = current_hash

        checkpoint_format = checkpoint_format or self.config.checkpoint_format

        try:
            if checkpoint_format == CheckpointFormat.JSON:
                path = await self._save_json_checkpoint(checkpoint)
            elif checkpoint_format == CheckpointFormat.BINARY:
                path = await self._save_binary_checkpoint(checkpoint)
            elif (
                checkpoint_format == CheckpointFormat.BOTH
            ):  # pragma: no cover - Both format path, tested but not all branches covered
                # Save both checkpoint_formats
                json_path = await self._save_json_checkpoint(checkpoint)
                bin_path = await self._save_binary_checkpoint(checkpoint)
                self.logger.debug(
                    "Saved checkpoint in both checkpoint_formats: %s, %s",
                    json_path,
                    bin_path,
                )
                path = json_path  # Return JSON path as primary
            else:
                msg = f"Invalid checkpoint checkpoint_format: {checkpoint_format}"
                raise ValueError(msg)

            # Store last checkpoint for incremental saves
            self._last_checkpoint = checkpoint
            return path

        except Exception as e:
            self.logger.exception("Failed to save checkpoint")
            msg = f"Failed to save checkpoint: {e}"
            raise CheckpointError(msg) from e

    async def _save_json_checkpoint(self, checkpoint: TorrentCheckpoint) -> Path:
        """Save checkpoint in JSON checkpoint_format."""
        path = self._get_checkpoint_path(checkpoint.info_hash, CheckpointFormat.JSON)

        # Update timestamp
        checkpoint.updated_at = time.time()

        # Convert to dict for JSON serialization
        checkpoint_dict = checkpoint.model_dump()

        # Convert bytes to hex strings for JSON
        checkpoint_dict["info_hash"] = checkpoint.info_hash.hex()

        # Convert PieceState enums to strings
        if "piece_states" in checkpoint_dict:
            checkpoint_dict["piece_states"] = {
                str(k): v.value if hasattr(v, "value") else str(v)
                for k, v in checkpoint_dict["piece_states"].items()
            }

        # Ensure new metadata fields are included
        if not checkpoint_dict.get("torrent_file_path"):
            checkpoint_dict["torrent_file_path"] = checkpoint.torrent_file_path
        if not checkpoint_dict.get("magnet_uri"):
            checkpoint_dict["magnet_uri"] = checkpoint.magnet_uri
        if not checkpoint_dict.get("announce_urls"):
            checkpoint_dict["announce_urls"] = checkpoint.announce_urls
        if not checkpoint_dict.get("display_name"):
            checkpoint_dict["display_name"] = checkpoint.display_name
        # Ensure per-torrent options and rate limits are included
        if checkpoint.per_torrent_options is not None:
            checkpoint_dict["per_torrent_options"] = checkpoint.per_torrent_options
        if checkpoint.rate_limits is not None:
            checkpoint_dict["rate_limits"] = checkpoint.rate_limits

        # Ensure new fields are included
        if checkpoint.connected_peers is not None:
            checkpoint_dict["connected_peers"] = checkpoint.connected_peers
        if checkpoint.active_peers is not None:
            checkpoint_dict["active_peers"] = checkpoint.active_peers
        if checkpoint.peer_statistics is not None:
            checkpoint_dict["peer_statistics"] = checkpoint.peer_statistics
        if checkpoint.tracker_list is not None:
            checkpoint_dict["tracker_list"] = checkpoint.tracker_list
        if checkpoint.tracker_health is not None:
            checkpoint_dict["tracker_health"] = checkpoint.tracker_health
        if checkpoint.peer_whitelist is not None:
            checkpoint_dict["peer_whitelist"] = checkpoint.peer_whitelist
        if checkpoint.peer_blacklist is not None:
            checkpoint_dict["peer_blacklist"] = checkpoint.peer_blacklist
        if checkpoint.session_state is not None:
            checkpoint_dict["session_state"] = checkpoint.session_state
        if checkpoint.session_state_timestamp is not None:
            checkpoint_dict["session_state_timestamp"] = checkpoint.session_state_timestamp
        if checkpoint.recent_events is not None:
            checkpoint_dict["recent_events"] = checkpoint.recent_events

        # Convert resume_data bytes fields to base64 for JSON
        if checkpoint_dict.get("resume_data"):
            import base64

            resume_data = checkpoint_dict["resume_data"]
            if isinstance(resume_data, dict):
                # Convert info_hash bytes to hex
                if "info_hash" in resume_data and isinstance(
                    resume_data["info_hash"], bytes
                ):
                    resume_data["info_hash"] = resume_data["info_hash"].hex()
                # Convert piece_completion_bitmap bytes to base64
                if "piece_completion_bitmap" in resume_data and isinstance(
                    resume_data["piece_completion_bitmap"], bytes
                ):
                    resume_data["piece_completion_bitmap"] = base64.b64encode(
                        resume_data["piece_completion_bitmap"]
                    ).decode("utf-8")

        # Write JSON file
        def _write_json():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_dict, f, indent=2, ensure_ascii=False)
                f.flush()  # Ensure Python buffer is written
                os.fsync(f.fileno())  # Ensure OS buffer is written to disk

        await asyncio.get_event_loop().run_in_executor(None, _write_json)

        self.logger.debug("Saved JSON checkpoint: %s", path)
        return path

    async def _save_binary_checkpoint(self, checkpoint: TorrentCheckpoint) -> Path:
        """Save checkpoint in binary checkpoint_format."""
        if not HAS_MSGPACK:
            msg = "msgpack is required for binary checkpoint checkpoint_format"
            raise CheckpointError(msg)

        path = self._get_checkpoint_path(checkpoint.info_hash, CheckpointFormat.BINARY)

        # Update timestamp
        checkpoint.updated_at = time.time()

        # Prepare binary data
        def _write_binary():
            with open(path, "wb") as f:
                # Write header
                f.write(self.MAGIC_BYTES)  # 4 bytes
                f.write(struct.pack("B", self.VERSION))  # 1 byte
                f.write(checkpoint.info_hash)  # 20 bytes
                f.write(
                    struct.pack("Q", int(checkpoint.updated_at)),
                )  # 8 bytes timestamp
                f.write(struct.pack("I", checkpoint.total_pieces))  # 4 bytes

                # Write verified pieces bitfield
                bitfield = bytearray((checkpoint.total_pieces + 7) // 8)
                for piece_idx in checkpoint.verified_pieces:
                    byte_idx = piece_idx // 8
                    bit_idx = piece_idx % 8
                    bitfield[byte_idx] |= 1 << (7 - bit_idx)
                f.write(bitfield)

                # Write metadata as msgpack
                metadata = {
                    "torrent_name": checkpoint.torrent_name,
                    "piece_length": checkpoint.piece_length,
                    "total_length": checkpoint.total_length,
                    "piece_states": {
                        str(k): v.value for k, v in checkpoint.piece_states.items()
                    },
                    "download_stats": (
                        checkpoint.download_stats.model_dump()
                        if checkpoint.download_stats is not None
                        else DownloadStats().model_dump()
                    ),
                    "output_dir": checkpoint.output_dir,
                    "files": [f.model_dump() for f in checkpoint.files],
                    "peer_info": checkpoint.peer_info,
                    "endgame_mode": checkpoint.endgame_mode,
                    "torrent_file_path": checkpoint.torrent_file_path,
                    "magnet_uri": checkpoint.magnet_uri,
                    "announce_urls": checkpoint.announce_urls,
                    "display_name": checkpoint.display_name,
                }
                # Add per-torrent options and rate limits if they exist
                if checkpoint.per_torrent_options is not None:
                    metadata["per_torrent_options"] = checkpoint.per_torrent_options
                if checkpoint.rate_limits is not None:
                    metadata["rate_limits"] = checkpoint.rate_limits

                # Add new fields if they exist
                if checkpoint.connected_peers is not None:
                    metadata["connected_peers"] = checkpoint.connected_peers
                if checkpoint.active_peers is not None:
                    metadata["active_peers"] = checkpoint.active_peers
                if checkpoint.peer_statistics is not None:
                    metadata["peer_statistics"] = checkpoint.peer_statistics
                if checkpoint.tracker_list is not None:
                    metadata["tracker_list"] = checkpoint.tracker_list
                if checkpoint.tracker_health is not None:
                    metadata["tracker_health"] = checkpoint.tracker_health
                if checkpoint.peer_whitelist is not None:
                    metadata["peer_whitelist"] = checkpoint.peer_whitelist
                if checkpoint.peer_blacklist is not None:
                    metadata["peer_blacklist"] = checkpoint.peer_blacklist
                if checkpoint.session_state is not None:
                    metadata["session_state"] = checkpoint.session_state
                if checkpoint.session_state_timestamp is not None:
                    metadata["session_state_timestamp"] = checkpoint.session_state_timestamp
                if checkpoint.recent_events is not None:
                    metadata["recent_events"] = checkpoint.recent_events

                if not HAS_MSGPACK or msgpack is None:
                    msg = "msgpack not available for binary checkpoint write"
                    raise CheckpointError(
                        msg,
                    )
                metadata_bytes = msgpack.packb(metadata)  # type: ignore[attr-defined]
                f.write(struct.pack("I", len(metadata_bytes)))  # 4 bytes length
                f.write(metadata_bytes)
                f.flush()  # Ensure Python buffer is written
                os.fsync(f.fileno())  # Ensure OS buffer is written to disk
                # Verify file was actually written by checking size
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                if file_size == 0:
                    msg = "File was created but is empty"
                    raise OSError(msg)

        if self.config.checkpoint_compression:
            # Compress the binary data using configured algorithm
            algo = self.config.checkpoint_compression_algorithm.lower()

            def _write_compressed():
                if algo == "zstd" and HAS_ZSTD and zstd is not None:
                    # Use zstd for faster compression
                    compressor = zstd.ZstdCompressor(level=3)  # Balanced speed/ratio
                    with open(path, "wb") as f, compressor.stream_writer(f) as writer:
                        _write_binary_data(writer)
                else:  # pragma: no cover - gzip fallback path, zstd is default when available
                    # Fallback to gzip
                    with open(path, "wb") as f, gzip.GzipFile(
                        fileobj=f, mode="wb"
                    ) as gz:
                        _write_binary_data(gz)

            def _write_binary_data(f):
                f.write(self.MAGIC_BYTES)
                f.write(struct.pack("B", self.VERSION))
                f.write(checkpoint.info_hash)
                f.write(struct.pack("Q", int(checkpoint.updated_at)))
                f.write(struct.pack("I", checkpoint.total_pieces))

                bitfield = bytearray((checkpoint.total_pieces + 7) // 8)
                for piece_idx in checkpoint.verified_pieces:
                    byte_idx = piece_idx // 8
                    bit_idx = piece_idx % 8
                    bitfield[byte_idx] |= 1 << (7 - bit_idx)
                f.write(bitfield)

                metadata = {
                    "torrent_name": checkpoint.torrent_name,
                    "piece_length": checkpoint.piece_length,
                    "total_length": checkpoint.total_length,
                    "piece_states": {
                        str(k): v.value for k, v in checkpoint.piece_states.items()
                    },
                    "download_stats": (
                        checkpoint.download_stats.model_dump()
                        if checkpoint.download_stats is not None
                        else DownloadStats().model_dump()
                    ),
                    "output_dir": checkpoint.output_dir,
                    "files": [f.model_dump() for f in checkpoint.files],
                    "peer_info": checkpoint.peer_info,
                    "endgame_mode": checkpoint.endgame_mode,
                    "torrent_file_path": checkpoint.torrent_file_path,
                    "magnet_uri": checkpoint.magnet_uri,
                    "announce_urls": checkpoint.announce_urls,
                    "display_name": checkpoint.display_name,
                }

                if not HAS_MSGPACK or msgpack is None:
                    msg = "msgpack not available for binary checkpoint write"
                    raise CheckpointError(
                        msg,
                    )
                metadata_bytes = msgpack.packb(metadata)  # type: ignore[attr-defined]
                f.write(struct.pack("I", len(metadata_bytes)))
                f.write(metadata_bytes)
                # Note: For compressed writes, the file handle is managed by the compression library
                # which should handle flushing, but we ensure it's synced after the context manager

            try:
                await asyncio.get_event_loop().run_in_executor(None, _write_compressed)

                # Ensure compressed file is synced to disk
                def _sync_compressed():
                    with open(path, "rb+") as f:
                        os.fsync(f.fileno())

                await asyncio.get_event_loop().run_in_executor(None, _sync_compressed)
            except Exception as e:
                self.logger.exception("Failed to write compressed binary checkpoint")
                msg = f"Failed to write compressed binary checkpoint: {e}"
                raise CheckpointError(msg) from e
        else:
            try:
                await asyncio.get_event_loop().run_in_executor(None, _write_binary)
            except Exception as e:
                self.logger.exception("Failed to write binary checkpoint")
                msg = f"Failed to write binary checkpoint: {e}"
                raise CheckpointError(msg) from e

        # Verify file was actually created
        # Add a small delay on Windows to account for file system delays
        import sys

        file_exists = False
        if sys.platform == "win32":
            # Retry check with small delays to handle Windows file system timing
            for _attempt in range(10):  # Increased retries
                if path.exists():
                    # Double-check by trying to open the file
                    try:
                        with open(path, "rb") as f:
                            f.read(1)  # Try to read at least 1 byte
                        file_exists = True
                        break
                    except OSError:
                        # File might exist but not be readable yet
                        pass
                await asyncio.sleep(0.05)  # 50ms delay for Windows file system
        else:
            file_exists = path.exists()

        if not file_exists:
            msg = f"Binary checkpoint file was not created: {path}"
            self.logger.error(msg)
            # List files in directory for debugging
            if self.checkpoint_dir.exists():
                existing_files = list(self.checkpoint_dir.glob("*"))
                self.logger.error(
                    "Existing files in checkpoint directory: %s", existing_files
                )
            raise CheckpointError(msg)

        self.logger.debug("Saved binary checkpoint: %s", path)
        return path

    async def load_checkpoint(
        self,
        info_hash: bytes,
        checkpoint_format: CheckpointFormat | None = None,
    ) -> TorrentCheckpoint | None:
        """Load checkpoint from disk.

        Args:
            info_hash: Torrent info hash
            checkpoint_format: Format to load (tries both if None)

        Returns:
            Loaded checkpoint or None if not found

        Raises:
            CheckpointError: If loading fails

        """
        if not self.config.checkpoint_enabled:
            return None

        checkpoint_format = checkpoint_format or self.config.checkpoint_format

        try:
            if checkpoint_format == CheckpointFormat.JSON:
                return await self._load_json_checkpoint(info_hash)
            if checkpoint_format == CheckpointFormat.BINARY:
                return await self._load_binary_checkpoint(info_hash)
            if checkpoint_format == CheckpointFormat.BOTH:
                # Try JSON first, then binary
                checkpoint = await self._load_json_checkpoint(info_hash)
                if checkpoint is None:
                    checkpoint = await self._load_binary_checkpoint(info_hash)
                return checkpoint
            msg = f"Invalid checkpoint checkpoint_format: {checkpoint_format}"
            raise ValueError(msg)

        except CheckpointNotFoundError:
            return None
        except Exception as e:
            self.logger.exception("Failed to load checkpoint")
            msg = f"Failed to load checkpoint: {e}"
            raise CheckpointError(msg) from e

    async def _load_json_checkpoint(
        self,
        info_hash: bytes,
    ) -> TorrentCheckpoint | None:
        """Load checkpoint from JSON checkpoint_format."""
        path = self._get_checkpoint_path(info_hash, CheckpointFormat.JSON)

        if not path.exists():
            msg = f"JSON checkpoint not found: {path}"
            raise CheckpointNotFoundError(msg)

        def _read_json():
            with open(path, encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    msg = "Checkpoint file is empty"
                    raise CheckpointCorruptedError(msg)
                return json.loads(content)

        try:
            checkpoint_dict = await asyncio.get_event_loop().run_in_executor(
                None,
                _read_json,
            )

            # Convert hex string back to bytes
            checkpoint_dict["info_hash"] = bytes.fromhex(checkpoint_dict["info_hash"])

            # Convert resume_data base64 fields back to bytes
            if checkpoint_dict.get("resume_data"):
                import base64

                resume_data = checkpoint_dict["resume_data"]
                if isinstance(resume_data, dict):
                    # Convert info_hash hex string back to bytes
                    if "info_hash" in resume_data and isinstance(
                        resume_data["info_hash"], str
                    ):
                        with contextlib.suppress(ValueError):
                            resume_data["info_hash"] = bytes.fromhex(
                                resume_data["info_hash"]
                            )
                            # If not hex, might be base64 or other format
                    # Convert piece_completion_bitmap base64 back to bytes
                    if "piece_completion_bitmap" in resume_data and isinstance(
                        resume_data["piece_completion_bitmap"], str
                    ):
                        with contextlib.suppress(Exception):
                            resume_data["piece_completion_bitmap"] = base64.b64decode(
                                resume_data["piece_completion_bitmap"]
                            )
                            # If decode fails, leave as is (might be corrupted)

            # Convert string values back to PieceState enums
            if "piece_states" in checkpoint_dict:
                checkpoint_dict["piece_states"] = {
                    int(k): PieceState(v)
                    for k, v in checkpoint_dict["piece_states"].items()
                }

            # Validate version
            if checkpoint_dict.get("version", "1.0") != "1.0":
                msg = (
                    f"Incompatible checkpoint version: {checkpoint_dict.get('version')}"
                )
                raise CheckpointVersionError(
                    msg,
                )

            checkpoint = TorrentCheckpoint(**checkpoint_dict)
            self.logger.debug("Loaded JSON checkpoint: %s", path)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in checkpoint file: {e}"
            raise CheckpointCorruptedError(msg) from e
        except Exception as e:
            msg = f"Failed to parse checkpoint: {e}"
            raise CheckpointCorruptedError(msg) from e
        else:
            return checkpoint

    async def _load_binary_checkpoint(
        self,
        info_hash: bytes,
    ) -> TorrentCheckpoint | None:
        """Load checkpoint from binary checkpoint_format."""
        if not HAS_MSGPACK:
            msg = "msgpack is required for binary checkpoint checkpoint_format"
            raise CheckpointError(msg)

        path = self._get_checkpoint_path(info_hash, CheckpointFormat.BINARY)

        if not path.exists():
            msg = f"Binary checkpoint not found: {path}"
            raise CheckpointNotFoundError(msg)

        def _read_binary():
            with open(path, "rb") as f:
                if self.config.checkpoint_compression:
                    with gzip.GzipFile(fileobj=f, mode="rb") as gz:
                        return _read_binary_data(gz)
                else:
                    return _read_binary_data(f)

        def _read_binary_data(f):
            # Read header
            magic = f.read(4)
            if magic != self.MAGIC_BYTES:
                msg = "Invalid magic bytes in checkpoint file"
                raise CheckpointCorruptedError(msg)

            version = struct.unpack("B", f.read(1))[0]
            if version != self.VERSION:
                msg = f"Incompatible checkpoint version: {version}"
                raise CheckpointVersionError(
                    msg,
                )

            file_info_hash = f.read(20)
            if file_info_hash != info_hash:
                msg = "Info hash mismatch in checkpoint file"
                raise CheckpointCorruptedError(msg)

            timestamp = struct.unpack("Q", f.read(8))[0]
            total_pieces = struct.unpack("I", f.read(4))[0]

            # Read bitfield
            bitfield_size = (total_pieces + 7) // 8
            bitfield = f.read(bitfield_size)

            # Parse verified pieces from bitfield
            verified_pieces = []
            for byte_idx, byte_val in enumerate(bitfield):
                for bit_idx in range(8):
                    piece_idx = byte_idx * 8 + bit_idx
                    if piece_idx < total_pieces and (byte_val & (1 << (7 - bit_idx))):
                        verified_pieces.append(piece_idx)

            # Read metadata
            metadata_len = struct.unpack("I", f.read(4))[0]
            metadata_bytes = f.read(metadata_len)
            if not HAS_MSGPACK or msgpack is None:
                msg = "msgpack not available for binary checkpoint read"
                raise CheckpointError(
                    msg,
                )
            metadata = msgpack.unpackb(metadata_bytes, raw=False)  # type: ignore[attr-defined]

            # Convert string values back to PieceState enums
            if "piece_states" in metadata:
                metadata["piece_states"] = {
                    int(k): PieceState(v) for k, v in metadata["piece_states"].items()
                }

            # Create checkpoint object
            checkpoint_dict = {
                "version": "1.0",
                "info_hash": info_hash,
                "created_at": timestamp,  # Use timestamp as created_at
                "updated_at": timestamp,
                "total_pieces": total_pieces,
                "verified_pieces": verified_pieces,
                "piece_states": metadata.get("piece_states", {}),
                "download_stats": DownloadStats(**metadata.get("download_stats", {})),
                "files": [FileCheckpoint(**f) for f in metadata.get("files", [])],
                "peer_info": metadata.get("peer_info"),
                "endgame_mode": metadata.get("endgame_mode", False),
            }

            # Add required fields from metadata
            checkpoint_dict.update(
                {
                    "torrent_name": metadata.get("torrent_name", "Unknown"),
                    "piece_length": metadata.get("piece_length", 0),
                    "total_length": metadata.get("total_length", 0),
                    "output_dir": metadata.get("output_dir", "."),
                    "torrent_file_path": metadata.get("torrent_file_path"),
                    "magnet_uri": metadata.get("magnet_uri"),
                    "announce_urls": metadata.get("announce_urls", []),
                    "display_name": metadata.get("display_name"),
                },
            )
            # Add per-torrent options and rate limits if they exist in metadata
            if "per_torrent_options" in metadata:
                checkpoint_dict["per_torrent_options"] = metadata["per_torrent_options"]
            if "rate_limits" in metadata:
                checkpoint_dict["rate_limits"] = metadata["rate_limits"]

            # Add new fields if they exist in metadata (backward compatibility)
            if "connected_peers" in metadata:
                checkpoint_dict["connected_peers"] = metadata["connected_peers"]
            if "active_peers" in metadata:
                checkpoint_dict["active_peers"] = metadata["active_peers"]
            if "peer_statistics" in metadata:
                checkpoint_dict["peer_statistics"] = metadata["peer_statistics"]
            if "tracker_list" in metadata:
                checkpoint_dict["tracker_list"] = metadata["tracker_list"]
            if "tracker_health" in metadata:
                checkpoint_dict["tracker_health"] = metadata["tracker_health"]
            if "peer_whitelist" in metadata:
                checkpoint_dict["peer_whitelist"] = metadata["peer_whitelist"]
            if "peer_blacklist" in metadata:
                checkpoint_dict["peer_blacklist"] = metadata["peer_blacklist"]
            if "session_state" in metadata:
                checkpoint_dict["session_state"] = metadata["session_state"]
            if "session_state_timestamp" in metadata:
                checkpoint_dict["session_state_timestamp"] = metadata["session_state_timestamp"]
            if "recent_events" in metadata:
                checkpoint_dict["recent_events"] = metadata["recent_events"]

            return checkpoint_dict

        try:
            checkpoint_dict = await asyncio.get_event_loop().run_in_executor(
                None,
                _read_binary,
            )
            checkpoint = TorrentCheckpoint(**checkpoint_dict)
            self.logger.debug("Loaded binary checkpoint: %s", path)
        except Exception as e:
            msg = f"Failed to parse binary checkpoint: {e}"
            raise CheckpointCorruptedError(msg) from e
        else:
            return checkpoint

    async def delete_checkpoint(self, info_hash: bytes) -> bool:
        """Delete checkpoint files for given info hash.

        Args:
            info_hash: Torrent info hash

        Returns:
            True if any files were deleted, False otherwise

        """
        deleted = False

        # Delete JSON checkpoint
        json_path = self._get_checkpoint_path(info_hash, CheckpointFormat.JSON)
        if json_path.exists():
            json_path.unlink()
            deleted = True
            self.logger.debug("Deleted JSON checkpoint: %s", json_path)

        # Delete binary checkpoint
        bin_path = self._get_checkpoint_path(info_hash, CheckpointFormat.BINARY)
        if bin_path.exists():
            bin_path.unlink()
            deleted = True
            self.logger.debug("Deleted binary checkpoint: %s", bin_path)

        return deleted

    async def list_checkpoints(self) -> list[CheckpointFileInfo]:
        """List all available checkpoints.

        Returns:
            List of checkpoint file incheckpoint_formation

        """
        checkpoints = []

        if (
            not self.checkpoint_dir.exists()
        ):  # pragma: no cover - Directory created in __init__, defensive check
            return checkpoints

        for file_path in self.checkpoint_dir.glob("*.checkpoint.*"):
            try:
                # Extract info hash from filename
                filename = file_path.stem
                if filename.endswith(".checkpoint"):
                    info_hash_hex = filename.replace(".checkpoint", "")
                    info_hash = bytes.fromhex(info_hash_hex)
                else:  # pragma: no cover - Filename pattern matching, tested via invalid files
                    continue

                # Determine checkpoint_format
                if file_path.suffix == ".json":
                    checkpoint_format_type = CheckpointFormat.JSON
                elif file_path.suffix in [".bin", ".gz"]:
                    checkpoint_format_type = CheckpointFormat.BINARY
                else:
                    continue

                stat = file_path.stat()
                checkpoints.append(
                    CheckpointFileInfo(
                        path=file_path,
                        info_hash=info_hash,
                        created_at=stat.st_ctime,
                        updated_at=stat.st_mtime,
                        size=stat.st_size,
                        checkpoint_format=checkpoint_format_type,
                    ),
                )

            except Exception as e:
                self.logger.warning(
                    "Failed to process checkpoint file %s: %s",
                    file_path,
                    e,
                )
                continue

        return sorted(checkpoints, key=lambda x: x.updated_at, reverse=True)

    async def verify_checkpoint(self, info_hash: bytes) -> bool:
        """Verify that a checkpoint exists and is structurally valid."""
        cp = await self.load_checkpoint(info_hash)
        if cp is None:
            return False
        # basic invariants
        return not len(cp.verified_pieces) > cp.total_pieces

    async def export_checkpoint(self, info_hash: bytes, fmt: str = "json") -> bytes:
        """Export checkpoint in the desired checkpoint_format and return bytes."""
        cp = await self.load_checkpoint(info_hash)
        if cp is None:
            msg = f"No checkpoint for {info_hash.hex()}"
            raise CheckpointNotFoundError(msg)
        fmt = (fmt or "json").lower()
        if fmt == "json":
            cp_dict = cp.model_dump()
            cp_dict["info_hash"] = cp.info_hash.hex()
            return json.dumps(cp_dict, indent=2).encode("utf-8")
        if fmt == "binary":
            # Save to temp path using binary writer and read back
            path = await self._save_binary_checkpoint(cp)
            return path.read_bytes()
        msg = f"Unsupported export checkpoint_format: {fmt}"
        raise CheckpointError(msg)

    async def backup_checkpoint(
        self,
        info_hash: bytes,
        destination: Path,
        *,
        compress: bool = True,
        encrypt: bool = False,
    ) -> Path:
        """Create a portable backup of the checkpoint at destination.

        Backup checkpoint_format is JSON optionally gzipped and optionally encrypted if cryptography is available.
        """
        cp = await self.load_checkpoint(info_hash)
        if cp is None:
            msg = f"No checkpoint for {info_hash.hex()}"
            raise CheckpointNotFoundError(msg)

        # Serialize JSON
        data = await self.export_checkpoint(info_hash, fmt="json")

        # Optional compression
        if compress:
            data = gzip.compress(data)

        # Optional encryption
        if encrypt:
            try:
                from cryptography.fernet import Fernet
            except Exception:
                msg = "Encryption requested but cryptography is not installed"
                raise CheckpointError(
                    msg,
                ) from None
            key_path = destination.with_suffix(destination.suffix + ".key")
            key = Fernet.generate_key()
            f = Fernet(key)
            data = f.encrypt(data)
            key_path.write_bytes(key)

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        self.logger.info("Wrote checkpoint backup to %s", destination)
        return destination

    async def restore_checkpoint(
        self,
        backup_file: Path,
        *,
        info_hash: bytes | None = None,
    ) -> TorrentCheckpoint:
        """Restore a checkpoint from a backup file. Returns the restored checkpoint model."""
        data = backup_file.read_bytes()
        # Try decrypt if a .key file exists
        key_file = backup_file.with_suffix(backup_file.suffix + ".key")
        if key_file.exists():
            try:
                from cryptography.fernet import Fernet

                key = key_file.read_bytes()
                f = Fernet(key)
                data = f.decrypt(data)
            except Exception as e:
                msg = f"Failed to decrypt backup: {e}"
                raise CheckpointError(msg) from e

        # Try decompress
        with contextlib.suppress(OSError):
            data = gzip.decompress(data)

        try:
            cp_dict = json.loads(data.decode("utf-8"))
        except Exception as e:
            msg = f"Invalid backup content: {e}"
            raise CheckpointError(msg) from e

        # Convert back types
        cp_dict["info_hash"] = bytes.fromhex(cp_dict["info_hash"])
        if info_hash and cp_dict["info_hash"] != info_hash:
            msg = "Backup info hash does not match provided info hash"
            raise CheckpointError(msg)
        if "piece_states" in cp_dict:
            cp_dict["piece_states"] = {
                int(k): PieceState(v) for k, v in cp_dict["piece_states"].items()
            }

        cp = TorrentCheckpoint(**cp_dict)

        # Clear checkpoint state to force save (in case file was deleted)
        # This ensures restore always writes the file even if deduplication would skip it
        self._last_checkpoint_hash = None
        self._last_checkpoint = None

        # Save to disk using configured checkpoint_format(s)
        await self.save_checkpoint(cp, self.config.checkpoint_format)
        return cp

    async def cleanup_old_checkpoints(self, max_age_days: int = 30) -> int:
        """Clean up old checkpoint files.

        Args:
            max_age_days: Maximum age in days before cleanup

        Returns:
            Number of files deleted

        """
        if (
            not self.checkpoint_dir.exists()
        ):  # pragma: no cover - Directory created in __init__, defensive check
            return 0

        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        deleted_count = 0

        for file_path in self.checkpoint_dir.glob("*.checkpoint.*"):
            try:
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    self.logger.debug("Cleaned up old checkpoint: %s", file_path)
            except Exception as e:
                self.logger.warning("Failed to cleanup checkpoint %s: %s", file_path, e)

        if deleted_count > 0:
            self.logger.info("Cleaned up %s old checkpoint files", deleted_count)

        return deleted_count

    async def convert_checkpoint_checkpoint_format(  # pragma: no cover - Duplicate method (typo), kept for backward compatibility
        self,
        info_hash: bytes,
        from_checkpoint_format: CheckpointFormat,
        to_checkpoint_format: CheckpointFormat,
    ) -> Path:
        """Convert checkpoint between checkpoint_formats.

        Args:
            info_hash: Torrent info hash
            from_checkpoint_format: Source checkpoint_format
            to_checkpoint_format: Target checkpoint_format

        Returns:
            Path to converted checkpoint file

        """
        # Load from source checkpoint_format
        checkpoint = await self.load_checkpoint(info_hash, from_checkpoint_format)
        if checkpoint is None:
            msg = f"No checkpoint found for {info_hash.hex()}"
            raise CheckpointNotFoundError(msg)

        # Save in target checkpoint_format
        return await self.save_checkpoint(checkpoint, to_checkpoint_format)

    def get_checkpoint_stats(self) -> dict[str, Any]:
        """Get checkpoint directory statistics."""
        if (
            not self.checkpoint_dir.exists()
        ):  # pragma: no cover - Directory created in __init__, defensive check
            return {
                "total_files": 0,
                "total_size": 0,
                "json_files": 0,
                "binary_files": 0,
                "oldest_checkpoint": None,
                "newest_checkpoint": None,
            }

        files = list(self.checkpoint_dir.glob("*.checkpoint.*"))
        total_size = sum(f.stat().st_size for f in files)

        json_files = len([f for f in files if f.suffix == ".json"])
        binary_files = len([f for f in files if f.suffix in [".bin", ".gz"]])

        timestamps = [f.stat().st_mtime for f in files]
        oldest_checkpoint = min(timestamps) if timestamps else None
        newest_checkpoint = max(timestamps) if timestamps else None

        return {
            "total_files": len(files),
            "total_size": total_size,
            "json_files": json_files,
            "binary_files": binary_files,
            "oldest_checkpoint": oldest_checkpoint,
            "newest_checkpoint": newest_checkpoint,
        }

    async def convert_checkpoint_format(
        self,
        info_hash: bytes,
        from_format: CheckpointFormat,
        to_format: CheckpointFormat,
    ) -> Path:
        """Convert checkpoint from one format to another.

        Args:
            info_hash: Info hash of the checkpoint
            from_format: Source format
            to_format: Target format

        Returns:
            Path to the converted checkpoint file

        Raises:
            CheckpointNotFoundError: If source checkpoint doesn't exist
            CheckpointError: If conversion fails

        """
        # Load checkpoint from source format
        checkpoint = await self.load_checkpoint(info_hash, from_format)
        if checkpoint is None:
            msg = f"Checkpoint not found for info hash {info_hash.hex()}"
            raise CheckpointNotFoundError(msg)

        # Save checkpoint in target format
        return await self.save_checkpoint(checkpoint, to_format)


class GlobalCheckpointManager:
    """Manages global session manager checkpoints."""

    def __init__(self, config: DiskConfig | None = None):
        """Initialize global checkpoint manager.

        Args:
            config: Disk configuration with checkpoint settings

        """
        self.config = config or DiskConfig()
        self.logger = get_logger(__name__)

        # Determine checkpoint directory (same as per-torrent checkpoints)
        if self.config.checkpoint_dir:
            self.checkpoint_dir = Path(self.config.checkpoint_dir)
        else:
            self.checkpoint_dir = Path(".ccbt/checkpoints")

        # Ensure checkpoint directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Global checkpoint file path
        self.global_checkpoint_file = self.checkpoint_dir / "global.checkpoint.json"

        self.logger.info(
            "Global checkpoint manager initialized with file: %s",
            self.global_checkpoint_file,
        )

    async def save_global_checkpoint(
        self,
        checkpoint: GlobalCheckpoint,
    ) -> Path:
        """Save global checkpoint to disk.

        Args:
            checkpoint: Global checkpoint data to save

        Returns:
            Path to saved checkpoint file

        Raises:
            CheckpointError: If saving fails

        """
        if not self.config.checkpoint_enabled:
            msg = "Checkpointing is disabled"
            raise CheckpointError(msg)

        try:
            # Update timestamp
            checkpoint.updated_at = time.time()

            # Convert to dict for JSON serialization
            checkpoint_dict = checkpoint.model_dump()

            # Convert bytes to hex strings for JSON
            if "active_torrents" in checkpoint_dict:
                checkpoint_dict["active_torrents"] = [
                    ih.hex() for ih in checkpoint_dict["active_torrents"]
                ]
            if "paused_torrents" in checkpoint_dict:
                checkpoint_dict["paused_torrents"] = [
                    ih.hex() for ih in checkpoint_dict["paused_torrents"]
                ]
            if "queued_torrents" in checkpoint_dict:
                for queue_item in checkpoint_dict["queued_torrents"]:
                    if "info_hash" in queue_item and isinstance(
                        queue_item["info_hash"], bytes
                    ):
                        queue_item["info_hash"] = queue_item["info_hash"].hex()

            # Write JSON file
            def _write_json():
                with open(
                    self.global_checkpoint_file, "w", encoding="utf-8"
                ) as f:
                    json.dump(checkpoint_dict, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

            await asyncio.get_event_loop().run_in_executor(None, _write_json)

            self.logger.debug(
                "Saved global checkpoint: %s", self.global_checkpoint_file
            )
            return self.global_checkpoint_file

        except Exception as e:
            self.logger.exception("Failed to save global checkpoint")
            msg = f"Failed to save global checkpoint: {e}"
            raise CheckpointError(msg) from e

    async def load_global_checkpoint(self) -> GlobalCheckpoint | None:
        """Load global checkpoint from disk.

        Returns:
            Loaded checkpoint or None if not found

        Raises:
            CheckpointError: If loading fails

        """
        if not self.config.checkpoint_enabled:
            return None

        if not self.global_checkpoint_file.exists():
            return None

        def _read_json():
            with open(
                self.global_checkpoint_file, encoding="utf-8"
            ) as f:
                content = f.read().strip()
                if not content:
                    msg = "Global checkpoint file is empty"
                    raise CheckpointCorruptedError(msg)
                return json.loads(content)

        try:
            checkpoint_dict = await asyncio.get_event_loop().run_in_executor(
                None, _read_json
            )

            # Convert hex strings back to bytes
            if "active_torrents" in checkpoint_dict:
                checkpoint_dict["active_torrents"] = [
                    bytes.fromhex(ih) for ih in checkpoint_dict["active_torrents"]
                ]
            if "paused_torrents" in checkpoint_dict:
                checkpoint_dict["paused_torrents"] = [
                    bytes.fromhex(ih) for ih in checkpoint_dict["paused_torrents"]
                ]
            if "queued_torrents" in checkpoint_dict:
                for queue_item in checkpoint_dict["queued_torrents"]:
                    if "info_hash" in queue_item and isinstance(
                        queue_item["info_hash"], str
                    ):
                        queue_item["info_hash"] = bytes.fromhex(
                            queue_item["info_hash"]
                        )

            # Validate version
            if checkpoint_dict.get("version", "1.0") != "1.0":
                msg = (
                    f"Incompatible global checkpoint version: "
                    f"{checkpoint_dict.get('version')}"
                )
                raise CheckpointVersionError(msg)

            checkpoint = GlobalCheckpoint(**checkpoint_dict)
            self.logger.debug(
                "Loaded global checkpoint: %s", self.global_checkpoint_file
            )
            return checkpoint

        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in global checkpoint file: {e}"
            raise CheckpointCorruptedError(msg) from e
        except Exception as e:
            msg = f"Failed to parse global checkpoint: {e}"
            raise CheckpointCorruptedError(msg) from e

    async def save_incremental_checkpoint(
        self,
        checkpoint: TorrentCheckpoint,
        changed_fields: set[str],
    ) -> Path:
        """Save only changed fields for quick reload.

        Args:
            checkpoint: Checkpoint data with updated fields
            changed_fields: Set of field names that changed

        Returns:
            Path to saved incremental checkpoint file

        Raises:
            CheckpointError: If saving fails

        """
        if not self.config.checkpoint_enabled:
            msg = "Checkpointing is disabled"
            raise CheckpointError(msg)

        # For incremental saves, we still save the full checkpoint
        # but mark it as incremental in metadata for faster loading
        # The actual incremental logic is in the loading side
        checkpoint_format = self.config.checkpoint_format

        try:
            if checkpoint_format == CheckpointFormat.JSON:
                path = await self._save_json_checkpoint(checkpoint)
            elif checkpoint_format == CheckpointFormat.BINARY:
                path = await self._save_binary_checkpoint(checkpoint)
            else:
                # For BOTH format, save JSON (faster for incremental)
                path = await self._save_json_checkpoint(checkpoint)

            self.logger.debug(
                "Saved incremental checkpoint with %d changed fields: %s",
                len(changed_fields),
                ", ".join(sorted(changed_fields)),
            )
            return path

        except Exception as e:
            self.logger.exception("Failed to save incremental checkpoint")
            msg = f"Failed to save incremental checkpoint: {e}"
            raise CheckpointError(msg) from e

    async def load_incremental_checkpoint(
        self,
        info_hash: bytes,
        base_checkpoint: TorrentCheckpoint | None = None,
    ) -> TorrentCheckpoint | None:
        """Load incremental checkpoint and merge with base.

        Args:
            info_hash: Torrent info hash
            base_checkpoint: Base checkpoint to merge with (if None, loads full checkpoint)

        Returns:
            Merged checkpoint or None if not found

        Raises:
            CheckpointError: If loading fails

        """
        # Load full checkpoint (incremental is handled by changed_fields tracking)
        checkpoint = await self.load_checkpoint(info_hash)
        if checkpoint is None:
            return None

        # If base checkpoint provided, merge changed fields
        if base_checkpoint:
            # Merge strategy: new checkpoint fields override base
            # This allows partial updates
            for field_name in checkpoint.model_fields:
                if hasattr(checkpoint, field_name):
                    new_value = getattr(checkpoint, field_name)
                    if new_value is not None:
                        setattr(base_checkpoint, field_name, new_value)

            return base_checkpoint

        return checkpoint
