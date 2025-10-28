# ccbt/session.py
"""High-performance async session manager for ccBitTorrent.

Manages multiple torrents (file or magnet), coordinates tracker announces,
DHT, PEX, and provides status aggregation with async event loop management.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ccbt.checkpoint import CheckpointManager
from ccbt.config import get_config
from ccbt.dht import AsyncDHTClient
from ccbt.exceptions import ValidationError
from ccbt.file_assembler import AsyncDownloadManager
from ccbt.logging_config import get_logger
from ccbt.magnet import build_minimal_torrent_data, parse_magnet
from ccbt.metrics import Metrics
from ccbt.models import PieceState, TorrentCheckpoint
from ccbt.models import TorrentInfo as TorrentInfoModel
from ccbt.pex import PEXManager
from ccbt.services.peer_service import PeerService
from ccbt.torrent import TorrentParser
from ccbt.tracker import AsyncTrackerClient

# Constants
INFO_HASH_LENGTH = 20  # SHA-1 hash length in bytes


@dataclass
class TorrentSessionInfo:
    """Information about a torrent session."""

    info_hash: bytes
    name: str
    output_dir: str
    added_time: float
    status: str = "starting"  # starting, downloading, seeding, stopped, error


class AsyncTorrentSession:
    """Represents one active torrent's lifecycle with async operations."""

    def __init__(
        self,
        torrent_data: dict[str, Any] | TorrentInfoModel,
        output_dir: str | Path = ".",
        session_manager: AsyncSessionManager | None = None,
    ) -> None:
        """Initialize TorrentSession with torrent data and output directory."""
        self.config = get_config()
        self.torrent_data = torrent_data
        self.output_dir = Path(output_dir)
        self.session_manager = session_manager

        # Core components
        self.download_manager = AsyncDownloadManager(torrent_data, str(output_dir))

        # Create a proper piece manager for checkpoint operations
        from ccbt.async_piece_manager import AsyncPieceManager

        self._normalized_td = self._normalize_torrent_data(torrent_data)
        self.piece_manager = AsyncPieceManager(self._normalized_td)

        # Set the piece manager on the download manager for compatibility
        self.download_manager.piece_manager = self.piece_manager

        self.tracker = AsyncTrackerClient()
        self.pex_manager: PEXManager | None = None
        self.checkpoint_manager = CheckpointManager(self.config.disk)

        # Session state
        if isinstance(torrent_data, TorrentInfoModel):
            name = torrent_data.name
            info_hash = torrent_data.info_hash
        else:
            name = torrent_data.get("name") or torrent_data.get("file_info", {}).get(
                "name",
                "Unknown",
            )
            info_hash = torrent_data["info_hash"]

        self.info = TorrentSessionInfo(
            info_hash=info_hash,
            name=name,
            output_dir=str(output_dir),
            added_time=time.time(),
        )

        # Source tracking for checkpoint metadata
        self.torrent_file_path: str | None = None
        self.magnet_uri: str | None = None

        # Background tasks
        self._announce_task: asyncio.Task[None] | None = None
        self._status_task: asyncio.Task[None] | None = None
        self._checkpoint_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Checkpoint state
        self.checkpoint_loaded = False
        self.resume_from_checkpoint = False

        # Callbacks
        self.on_status_update: Callable[[dict[str, Any]], None] | None = None
        self.on_complete: Callable[[], None] | None = None
        self.on_error: Callable[[Exception], None] | None = None

        self.logger = get_logger(__name__)

    def _normalize_torrent_data(
        self,
        td: dict[str, Any] | TorrentInfoModel,
    ) -> dict[str, Any]:
        """Convert TorrentInfoModel or legacy dict into a normalized dict expected by piece manager.

        Returns a dict with keys: 'file_info', 'pieces_info', and minimal metadata.
        """
        if isinstance(td, dict):
            # Assume already using legacy dict shape or at least includes needed fields
            # Best-effort fill pieces_info / file_info if missing
            pieces_info = td.get("pieces_info")
            file_info = td.get("file_info")
            result: dict[str, Any] = dict(td)
            if (
                not pieces_info
                and "pieces" in td
                and "piece_length" in td
                and "num_pieces" in td
            ):
                result["pieces_info"] = {
                    "piece_hashes": td.get("pieces", []),
                    "piece_length": td.get("piece_length", 0),
                    "num_pieces": td.get("num_pieces", 0),
                    "total_length": td.get("total_length", 0),
                }
            if not file_info:
                result.setdefault(
                    "file_info",
                    {"total_length": td.get("total_length", 0)},
                )
            return result
        # TorrentInfoModel
        return {
            "name": td.name,
            "info_hash": td.info_hash,
            "pieces_info": {
                "piece_hashes": list(td.pieces),
                "piece_length": td.piece_length,
                "num_pieces": td.num_pieces,
                "total_length": td.total_length,
            },
            "file_info": {
                "total_length": td.total_length,
            },
        }

    def _should_prompt_for_resume(self) -> bool:
        """Determine if we should prompt user for resume."""
        # Only prompt if auto_resume is disabled and we're in interactive mode
        return not self.config.disk.auto_resume

    async def start(self, resume: bool = False) -> None:
        """Start the async torrent session."""
        try:
            self.info.status = "starting"

            # Check for existing checkpoint only if resuming
            checkpoint = None
            if self.config.disk.checkpoint_enabled and (
                resume or self.config.disk.auto_resume
            ):
                try:
                    checkpoint = await self.checkpoint_manager.load_checkpoint(
                        self.info.info_hash,
                    )
                    if checkpoint:
                        self.logger.info("Found checkpoint for %s", self.info.name)
                        self.resume_from_checkpoint = True
                        self.logger.info("Resuming from checkpoint")
                except Exception as e:
                    self.logger.warning("Failed to load checkpoint: %s", e)
                    checkpoint = None

            # Start tracker client
            await self.tracker.start()

            # Start piece manager
            await self.piece_manager.start()

            # Set up callbacks
            self.download_manager.on_download_complete = self._on_download_complete
            self.download_manager.on_piece_verified = self._on_piece_verified

            # Set up checkpoint callback
            if self.config.disk.checkpoint_enabled:
                self.download_manager.piece_manager.on_checkpoint_save = (
                    self._save_checkpoint
                )

            # Handle resume from checkpoint
            if self.resume_from_checkpoint and checkpoint:
                await self._resume_from_checkpoint(checkpoint)

            # Start PEX manager if enabled
            if self.config.discovery.enable_pex:
                self.pex_manager = PEXManager()
                await self.pex_manager.start()

            # Start background tasks
            self._announce_task = asyncio.create_task(self._announce_loop())
            self._status_task = asyncio.create_task(self._status_loop())

            # Start checkpoint task if enabled
            if self.config.disk.checkpoint_enabled:
                self._checkpoint_task = asyncio.create_task(self._checkpoint_loop())

            self.info.status = "downloading"
            self.logger.info("Started torrent session: %s", self.info.name)

        except Exception as e:
            self.info.status = "error"
            self.logger.exception("Failed to start torrent session")
            if self.on_error:
                await self.on_error(e)
            raise

    async def stop(self) -> None:
        """Stop the async torrent session."""
        self._stop_event.set()

        # Cancel background tasks
        if self._announce_task:
            self._announce_task.cancel()
        if self._status_task:
            self._status_task.cancel()
        if self._checkpoint_task:
            self._checkpoint_task.cancel()

        # Save final checkpoint before stopping
        if (
            self.config.disk.checkpoint_enabled
            and not self.download_manager.download_complete
        ):
            try:
                await self._save_checkpoint()
            except Exception as e:
                self.logger.warning("Failed to save final checkpoint: %s", e)

        # Stop components
        if self.pex_manager:
            await self.pex_manager.stop()

        await self.download_manager.stop()
        await self.piece_manager.stop()
        await self.tracker.stop()

        self.info.status = "stopped"
        self.logger.info("Stopped torrent session: %s", self.info.name)

    async def pause(self) -> None:
        """Pause the torrent session by stopping background work and saving a checkpoint.

        Resume will restart the session using existing state.
        """
        try:
            # Save checkpoint before pausing
            if self.config.disk.checkpoint_enabled:
                try:
                    await self._save_checkpoint()
                except Exception as e:
                    self.logger.warning("Failed to save checkpoint on pause: %s", e)

            # Stop background tasks
            self._stop_event.set()
            if self._announce_task:
                self._announce_task.cancel()
            if self._status_task:
                self._status_task.cancel()
            if self._checkpoint_task:
                self._checkpoint_task.cancel()

            # Stop heavy components
            if self.pex_manager:
                await self.pex_manager.stop()
            await self.tracker.stop()
            await self.download_manager.stop()

            self.info.status = "paused"
            self.logger.info("Paused torrent session: %s", self.info.name)
        except Exception:
            self.logger.exception("Failed to pause torrent")
            raise

    async def resume(self) -> None:
        """Resume a previously paused torrent session."""
        try:
            await self.start(resume=True)
            self.info.status = "downloading"
            self.logger.info("Resumed torrent session: %s", self.info.name)
        except Exception:
            self.logger.exception("Failed to resume torrent")
            raise

    async def _announce_loop(self) -> None:
        """Background task for periodic tracker announces."""
        announce_interval = self.config.network.announce_interval

        while not self._stop_event.is_set():
            try:
                # Announce to tracker
                td: dict[str, Any]
                if isinstance(self.torrent_data, TorrentInfoModel):
                    td = {
                        "info_hash": self.torrent_data.info_hash,
                        "name": self.torrent_data.name,
                        "announce": getattr(self.torrent_data, "announce", ""),
                    }
                else:
                    td = self.torrent_data
                response = await self.tracker.announce(td)

                if response.peers:
                    # Update peer list in download manager
                    # TODO: Implement peer connection for file_assembler AsyncDownloadManager
                    pass

                # Wait for next announce
                await asyncio.sleep(announce_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning("Tracker announce failed: %s", e)
                await asyncio.sleep(60)  # Retry in 1 minute on error

    async def _status_loop(self) -> None:
        """Background task for status monitoring."""
        while not self._stop_event.is_set():
            try:
                # Get current status
                status = await self.get_status()

                # Notify callback
                if self.on_status_update:
                    await self.on_status_update(status)

                # Update session manager metrics
                if self.session_manager:
                    # TODO: Implement metrics update for file_assembler AsyncDownloadManager
                    pass

                # Wait before next status check
                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Status loop error")
                await asyncio.sleep(5)

    async def _on_download_complete(self) -> None:
        """Handle download completion."""
        self.info.status = "seeding"
        self.logger.info("Download complete, now seeding: %s", self.info.name)

        # Clean up checkpoint if configured to do so
        if (
            self.config.disk.checkpoint_enabled
            and self.config.disk.auto_delete_checkpoint_on_complete
        ):
            try:
                await self.delete_checkpoint()
                self.logger.info(
                    "Deleted checkpoint for completed download: %s",
                    self.info.name,
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to delete checkpoint after completion: %s",
                    e,
                )

        if self.on_complete:
            await self.on_complete()

    async def _on_piece_verified(self, _piece_index: int) -> None:
        """Handle piece verification."""
        # Update PEX manager if available
        if self.pex_manager:
            # PEX manager will handle peer discovery
            pass

        # Save checkpoint after piece verification if enabled
        if self.config.disk.checkpoint_enabled and self.config.disk.checkpoint_on_piece:
            try:
                await self._save_checkpoint()
            except Exception as e:
                self.logger.warning(
                    "Failed to save checkpoint after piece verification: %s",
                    e,
                )

    async def get_status(self) -> dict[str, Any]:
        """Get current torrent status."""
        status = self.download_manager.get_status()
        status.update(
            {
                "info_hash": self.info.info_hash.hex(),
                "name": self.info.name,
                "status": self.info.status,
                "added_time": self.info.added_time,
                "uptime": time.time() - self.info.added_time,
            },
        )
        return status

    async def _resume_from_checkpoint(self, checkpoint: TorrentCheckpoint) -> None:
        """Resume download from checkpoint."""
        try:
            self.logger.info(
                "Resuming download from checkpoint: %s",
                checkpoint.torrent_name,
            )

            # Validate existing files
            if (
                hasattr(self.download_manager, "file_assembler")
                and self.download_manager.file_assembler
            ):
                validation_results = (
                    await self.download_manager.file_assembler.verify_existing_pieces(
                        checkpoint,
                    )
                )

                if not validation_results["valid"]:
                    self.logger.warning(
                        "File validation failed, some files may need to be re-downloaded",
                    )
                    if validation_results.get("missing_files"):
                        self.logger.warning(
                            "Missing files: %s",
                            validation_results["missing_files"],
                        )
                    if validation_results.get("corrupted_pieces"):
                        self.logger.warning(
                            "Corrupted pieces: %s",
                            validation_results["corrupted_pieces"],
                        )

            # Skip preallocation for existing files
            if (
                hasattr(self.download_manager, "file_assembler")
                and self.download_manager.file_assembler
            ):
                # Mark pieces as already written if they exist
                written_pieces = (
                    self.download_manager.file_assembler.get_written_pieces()
                )
                for piece_idx in checkpoint.verified_pieces:
                    if piece_idx not in written_pieces:
                        written_pieces.add(piece_idx)

            # Restore piece manager state
            if self.piece_manager:
                await self.piece_manager.restore_from_checkpoint(checkpoint)
                self.logger.info("Restored piece manager state from checkpoint")

            self.checkpoint_loaded = True
            self.logger.info(
                "Successfully resumed from checkpoint: %s pieces verified",
                len(checkpoint.verified_pieces),
            )

        except Exception:
            self.logger.exception("Failed to resume from checkpoint")
            raise

    async def _save_checkpoint(self) -> None:
        """Save current download state to checkpoint."""
        try:
            # Get checkpoint state from piece manager
            checkpoint = await self.piece_manager.get_checkpoint_state(
                self.info.name,
                self.info.info_hash,
                str(self.output_dir),
            )

            # Add torrent source metadata to checkpoint
            if hasattr(self, "torrent_file_path") and self.torrent_file_path:
                checkpoint.torrent_file_path = self.torrent_file_path
            elif hasattr(self, "magnet_uri") and self.magnet_uri:
                checkpoint.magnet_uri = self.magnet_uri

            # Add announce URLs from torrent data
            if isinstance(self.torrent_data, dict):
                announce_urls = []
                if "announce" in self.torrent_data:
                    announce_urls.append(self.torrent_data["announce"])
                if "announce_list" in self.torrent_data:
                    for tier in self.torrent_data["announce_list"]:
                        announce_urls.extend(tier)
                checkpoint.announce_urls = announce_urls

                # Add display name
                checkpoint.display_name = self.torrent_data.get("name", self.info.name)

            await self.checkpoint_manager.save_checkpoint(checkpoint)
            self.logger.debug("Saved checkpoint for %s", self.info.name)

        except Exception:
            self.logger.exception("Failed to save checkpoint")
            raise

    async def _checkpoint_loop(self) -> None:
        """Background task for periodic checkpoint saving."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.config.disk.checkpoint_interval)

                if not self._stop_event.is_set():
                    await self._save_checkpoint()

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error in checkpoint loop")

    async def delete_checkpoint(self) -> bool:
        """Delete checkpoint files for this torrent."""
        try:
            return await self.checkpoint_manager.delete_checkpoint(self.info.info_hash)
        except Exception:
            self.logger.exception("Failed to delete checkpoint")
            return False


class AsyncSessionManager:
    """High-performance async session manager for multiple torrents."""

    def __init__(self, output_dir: str = "."):
        """Initialize async session manager."""
        self.config = get_config()
        self.output_dir = output_dir
        self.torrents: dict[bytes, AsyncTorrentSession] = {}
        self.lock = asyncio.Lock()

        # Global components
        self.dht_client: AsyncDHTClient | None = None
        self.metrics = Metrics()
        self.peer_service: PeerService | None = PeerService(
            max_peers=self.config.network.max_global_peers,
            connection_timeout=self.config.network.connection_timeout,
        )

        # Background tasks
        self._cleanup_task: asyncio.Task | None = None
        self._metrics_task: asyncio.Task | None = None

        # Callbacks
        self.on_torrent_added: Callable[[bytes, str], None] | None = None
        self.on_torrent_removed: Callable[[bytes], None] | None = None
        self.on_torrent_complete: Callable[[bytes, str], None] | None = None

        self.logger = logging.getLogger(__name__)

        # Simple per-torrent rate limits (not enforced yet, stored for reporting)
        self._per_torrent_limits: dict[bytes, dict[str, int]] = {}

    async def start(self) -> None:
        """Start the async session manager."""
        # Start DHT client if enabled
        if self.config.discovery.enable_dht:
            self.dht_client = AsyncDHTClient()
            await self.dht_client.start()
        # Start peer service
        try:
            if self.peer_service:
                await self.peer_service.start()
        except Exception:
            # Best-effort: log and continue
            self.logger.debug("Peer service start failed", exc_info=True)

        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._metrics_task = asyncio.create_task(self._metrics_loop())

        self.logger.info("Async session manager started")

    async def stop(self) -> None:
        """Stop the async session manager."""
        # Stop all torrents
        async with self.lock:
            for session in self.torrents.values():
                await session.stop()
            self.torrents.clear()

        # Stop background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()

        # Stop DHT client
        if self.dht_client:
            await self.dht_client.stop()
        # Stop peer service
        try:
            if self.peer_service:
                await self.peer_service.stop()
        except Exception:
            # Best-effort: log and continue
            self.logger.debug("Peer service stop failed", exc_info=True)

        self.logger.info("Async session manager stopped")

    async def pause_torrent(self, info_hash_hex: str) -> bool:
        """Pause a torrent download by info hash.

        Returns True if paused, False otherwise.
        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
        if not session:
            return False
        await session.pause()
        return True

    async def resume_torrent(self, info_hash_hex: str) -> bool:
        """Resume a paused torrent by info hash."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        async with self.lock:
            session = self.torrents.get(info_hash)
        if not session:
            return False
        await session.resume()
        return True

    async def set_rate_limits(
        self,
        info_hash_hex: str,
        download_kib: int,
        upload_kib: int,
    ) -> bool:
        """Set per-torrent rate limits (stored for reporting).

        Currently not enforced at I/O level.
        """
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        async with self.lock:
            if info_hash not in self.torrents:
                return False
            self._per_torrent_limits[info_hash] = {
                "down_kib": max(0, int(download_kib)),
                "up_kib": max(0, int(upload_kib)),
            }
        return True

    async def get_global_stats(self) -> dict[str, Any]:
        """Aggregate global statistics across all torrents."""
        stats: dict[str, Any] = {
            "num_torrents": 0,
            "num_active": 0,
            "num_paused": 0,
            "num_seeding": 0,
            "download_rate": 0.0,
            "upload_rate": 0.0,
            "average_progress": 0.0,
        }
        aggregate_progress = 0.0
        async with self.lock:
            stats["num_torrents"] = len(self.torrents)
            for sess in self.torrents.values():
                st = await sess.get_status()
                s = st.get("status", "")
                if s == "paused":
                    stats["num_paused"] += 1
                elif s == "seeding":
                    stats["num_seeding"] += 1
                else:
                    stats["num_active"] += 1
                stats["download_rate"] += float(st.get("download_rate", 0.0))
                stats["upload_rate"] += float(st.get("upload_rate", 0.0))
                aggregate_progress += float(st.get("progress", 0.0))
        if stats["num_torrents"]:
            stats["average_progress"] = aggregate_progress / stats["num_torrents"]
        return stats

    async def export_session_state(self, path: Path) -> None:
        """Export current session state to a JSON file."""
        import json

        data: dict[str, Any] = {
            "torrents": {},
            "config": self.config.model_dump(mode="json"),
        }
        async with self.lock:
            for ih, sess in self.torrents.items():
                data["torrents"][ih.hex()] = await sess.get_status()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def import_session_state(self, path: Path) -> dict[str, Any]:
        """Import session state from a JSON file. Returns the parsed state.

        This does not automatically start torrents.
        """
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    async def add_torrent(
        self,
        path: str | dict[str, Any],
        resume: bool = False,
    ) -> str:
        """Add a torrent file or torrent data to the session."""
        try:
            # Handle both file paths and torrent dictionaries
            if isinstance(path, dict):
                td = path  # Already parsed torrent data
                info_hash = td.get("info_hash") if isinstance(td, dict) else None
                if not info_hash:
                    error_msg = "Missing info_hash in torrent data"
                    raise ValueError(error_msg)
            else:
                parser = TorrentParser()
                td_model = parser.parse(path)
                # Accept both model objects and plain dicts from mocked parsers in tests
                if isinstance(td_model, dict):
                    name = (
                        td_model.get("name")
                        or td_model.get("torrent_name")
                        or "unknown"
                    )
                    ih = td_model.get("info_hash")
                    if isinstance(ih, str):
                        ih = bytes.fromhex(ih)
                    if not isinstance(ih, (bytes, bytearray)):
                        error_msg = "info_hash must be bytes"
                        raise TypeError(error_msg)
                    td = {
                        "name": name,
                        "info_hash": bytes(ih),
                        "pieces_info": td_model.get("pieces_info", {}),
                        "file_info": td_model.get(
                            "file_info",
                            {
                                "total_length": td_model.get("total_length", 0),
                            },
                        ),
                    }
                else:
                    td = {
                        "name": td_model.name,
                        "info_hash": td_model.info_hash,
                        "pieces_info": {
                            "piece_hashes": list(td_model.pieces),
                            "piece_length": td_model.piece_length,
                            "num_pieces": td_model.num_pieces,
                            "total_length": td_model.total_length,
                        },
                        "file_info": {
                            "total_length": td_model.total_length,
                        },
                    }
                info_hash = td["info_hash"]
                if isinstance(info_hash, str):
                    info_hash = bytes.fromhex(info_hash)
                if not isinstance(info_hash, bytes):
                    error_msg = "info_hash must be bytes"
                    raise TypeError(error_msg)

            # Check if already exists
            async with self.lock:
                if isinstance(info_hash, bytes) and info_hash in self.torrents:
                    msg = f"Torrent {info_hash.hex()} already exists"
                    raise ValueError(msg)

                # Create session
                session = AsyncTorrentSession(td, self.output_dir, self)

                # Set source information for checkpoint metadata
                if isinstance(path, str):
                    session.torrent_file_path = path

                self.torrents[info_hash] = session

            # Start session
            await session.start(resume=resume)

            # Notify callback
            if self.on_torrent_added:
                await self.on_torrent_added(info_hash, session.info.name)

            self.logger.info("Added torrent: %s", session.info.name)
            return info_hash.hex()

        except Exception:
            path_desc = (
                getattr(path, "name", str(path)) if hasattr(path, "name") else str(path)
            )
            self.logger.exception("Failed to add torrent %s", path_desc)
            raise

    async def add_magnet(self, uri: str, resume: bool = False) -> str:
        """Add a magnet link to the session."""
        try:
            mi = parse_magnet(uri)
            td = build_minimal_torrent_data(mi.info_hash, mi.display_name, mi.trackers)
            info_hash = td["info_hash"]
            if isinstance(info_hash, str):
                info_hash = bytes.fromhex(info_hash)
            if not isinstance(info_hash, bytes):
                error_msg = "info_hash must be bytes"
                raise TypeError(error_msg)

            # Check if already exists
            async with self.lock:
                if isinstance(info_hash, bytes) and info_hash in self.torrents:
                    msg = f"Magnet {info_hash.hex()} already exists"
                    raise ValueError(msg)

                # Create session
                session = AsyncTorrentSession(td, self.output_dir, self)

                # Set source information for checkpoint metadata
                session.magnet_uri = uri

                self.torrents[info_hash] = session

            # Start session
            await session.start(resume=resume)

            # Notify callback
            if self.on_torrent_added:
                await self.on_torrent_added(info_hash, session.info.name)

            self.logger.info("Added magnet: %s", session.info.name)
            return info_hash.hex()

        except Exception:
            self.logger.exception("Failed to add magnet %s", uri)
            raise

    async def remove(self, info_hash_hex: str) -> bool:
        """Remove a torrent from the session."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False

        async with self.lock:
            session = self.torrents.pop(info_hash, None)

        if session:
            await session.stop()

            # Notify callback
            if self.on_torrent_removed:
                await self.on_torrent_removed(info_hash)

            self.logger.info("Removed torrent: %s", session.info.name)
            return True

        return False

    async def get_peers_for_torrent(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Return list of peers for a torrent (placeholder).

        Returns an empty list until peer tracking is wired.
        """
        try:
            _ = bytes.fromhex(info_hash_hex)
        except ValueError:
            return []
        if not self.peer_service:
            return []
        try:
            peers = await self.peer_service.list_peers()
            return [
                {
                    "ip": p.peer_info.ip,
                    "port": p.peer_info.port,
                    "download_rate": 0.0,
                    "upload_rate": 0.0,
                    "choked": False,
                    "client": "?",
                }
                for p in peers
            ]
        except Exception:
            return []

    async def force_announce(self, info_hash_hex: str) -> bool:
        """Force a tracker announce for a given torrent if possible."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        async with self.lock:
            sess = self.torrents.get(info_hash)
        if not sess:
            return False
        try:
            td: dict[str, Any]
            if isinstance(sess.torrent_data, dict):
                td = sess.torrent_data  # type: ignore[assignment]
            else:
                td = {
                    "info_hash": sess.info.info_hash,
                    "announce": "",
                    "name": sess.info.name,
                }
            await sess.tracker.announce(td)
        except Exception:
            return False
        else:
            return True

    async def checkpoint_backup_torrent(
        self,
        info_hash_hex: str,
        destination: Path,
        compress: bool = True,
        encrypt: bool = False,
    ) -> bool:
        """Create a checkpoint backup for a torrent to the destination path."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        try:
            cp = CheckpointManager(self.config.disk)
            await cp.backup_checkpoint(
                info_hash,
                destination,
                compress=compress,
                encrypt=encrypt,
            )
        except Exception:
            return False
        else:
            return True

    async def rehash_torrent(self, info_hash_hex: str) -> bool:
        """Rehash all pieces (placeholder)."""
        try:
            _ = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        # TODO: integrate with piece manager to re-verify data
        return True

    async def force_scrape(self, info_hash_hex: str) -> bool:
        """Force tracker scrape (placeholder)."""
        try:
            _ = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        return True

    async def refresh_pex(self, info_hash_hex: str) -> bool:
        """Refresh Peer Exchange (placeholder)."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return False
        async with self.lock:
            sess = self.torrents.get(info_hash)
        if not sess or not sess.pex_manager:
            return False
        try:
            if hasattr(sess.pex_manager, "refresh"):
                await sess.pex_manager.refresh()  # type: ignore[attr-defined]
        except Exception:
            return False
        else:
            return True

    async def get_status(self) -> dict[str, Any]:
        """Get status of all torrents."""
        status = {}
        async with self.lock:
            for info_hash, session in self.torrents.items():
                status[info_hash.hex()] = await session.get_status()
        return status

    async def get_torrent_status(self, info_hash_hex: str) -> dict[str, Any] | None:
        """Get status of a specific torrent."""
        try:
            info_hash = bytes.fromhex(info_hash_hex)
        except ValueError:
            return None

        async with self.lock:
            session = self.torrents.get(info_hash)

        if session:
            return await session.get_status()

        return None

    async def _cleanup_loop(self) -> None:
        """Background task for cleanup operations."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Clean up stopped sessions
                async with self.lock:
                    to_remove = []
                    for info_hash, session in self.torrents.items():
                        if session.info.status == "stopped":
                            to_remove.append(info_hash)

                    for info_hash in to_remove:
                        session = self.torrents.pop(info_hash)
                        await session.stop()
                        if self.on_torrent_removed:
                            await self.on_torrent_removed(info_hash)

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Cleanup loop error")

    async def _metrics_loop(self) -> None:
        """Background task for metrics collection."""
        while True:
            try:
                await asyncio.sleep(10)  # Update every 10 seconds

                # Collect global metrics
                # TODO: Implement global status update for metrics

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Metrics loop error")

    async def resume_from_checkpoint(
        self,
        info_hash: bytes,
        checkpoint: TorrentCheckpoint,
        torrent_path: str | None = None,
    ) -> str:
        """Resume download from checkpoint.

        Args:
            info_hash: Torrent info hash
            checkpoint: Checkpoint data
            torrent_path: Optional explicit torrent file path

        Returns:
            Info hash hex string of resumed torrent

        Raises:
            ValueError: If torrent source cannot be determined
            FileNotFoundError: If torrent file doesn't exist
            ValidationError: If checkpoint is invalid
        """
        try:
            # Validate checkpoint
            if not await self.validate_checkpoint(checkpoint):
                error_msg = "Invalid checkpoint data"
                raise ValidationError(error_msg)

            # Priority order: explicit path -> stored file path -> magnet URI
            torrent_source = None
            source_type = None

            if torrent_path and Path(torrent_path).exists():
                torrent_source = torrent_path
                source_type = "file"
                self.logger.info("Using explicit torrent file: %s", torrent_path)
            elif (
                checkpoint.torrent_file_path
                and Path(checkpoint.torrent_file_path).exists()
            ):
                torrent_source = checkpoint.torrent_file_path
                source_type = "file"
                self.logger.info(
                    "Using stored torrent file: %s",
                    checkpoint.torrent_file_path,
                )
            elif checkpoint.magnet_uri:
                torrent_source = checkpoint.magnet_uri
                source_type = "magnet"
                self.logger.info("Using stored magnet URI: %s", checkpoint.magnet_uri)
            else:
                error_msg = (
                    f"Cannot resume torrent {info_hash.hex()}: "
                    "No valid torrent source found in checkpoint. "
                    "Please provide torrent file or magnet link."
                )
                raise ValueError(error_msg)

            # Validate info hash matches if using explicit torrent file
            if source_type == "file" and torrent_source:
                parser = TorrentParser()
                torrent_data_model = parser.parse(torrent_source)
                if isinstance(torrent_data_model, dict):
                    torrent_info_hash = torrent_data_model.get("info_hash")
                else:
                    torrent_info_hash = getattr(torrent_data_model, "info_hash", None)
                torrent_data = {
                    "info_hash": torrent_info_hash,
                }
                if torrent_data["info_hash"] != info_hash:
                    torrent_hash_hex = (
                        torrent_data["info_hash"].hex()
                        if torrent_data["info_hash"] is not None
                        else "None"
                    )
                    error_msg = (
                        f"Info hash mismatch: checkpoint is for {info_hash.hex()}, "
                        f"but torrent file is for {torrent_hash_hex}"
                    )
                    raise ValueError(error_msg)

            # Add torrent/magnet with resume=True
            if source_type == "file":
                return await self.add_torrent(torrent_source, resume=True)
            return await self.add_magnet(torrent_source, resume=True)

        except Exception:
            self.logger.exception("Failed to resume from checkpoint")
            raise

    async def list_resumable_checkpoints(self) -> list[TorrentCheckpoint]:
        """List all checkpoints that can be auto-resumed."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoints = await checkpoint_manager.list_checkpoints()

        resumable = []
        for checkpoint_info in checkpoints:
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    checkpoint_info.info_hash,
                )
                if checkpoint and (
                    checkpoint.torrent_file_path or checkpoint.magnet_uri
                ):
                    resumable.append(checkpoint)
            except Exception as e:
                self.logger.warning(
                    "Failed to load checkpoint %s: %s",
                    checkpoint_info.info_hash.hex(),
                    e,
                )
                continue

        return resumable

    async def find_checkpoint_by_name(self, name: str) -> TorrentCheckpoint | None:
        """Find checkpoint by torrent name."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoints = await checkpoint_manager.list_checkpoints()

        for checkpoint_info in checkpoints:
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    checkpoint_info.info_hash,
                )
                if checkpoint and checkpoint.torrent_name == name:
                    return checkpoint
            except Exception as e:
                self.logger.warning(
                    "Failed to load checkpoint %s: %s",
                    checkpoint_info.info_hash.hex(),
                    e,
                )
                continue

        return None

    async def get_checkpoint_info(self, info_hash: bytes) -> dict[str, Any] | None:
        """Get checkpoint summary information."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoint = await checkpoint_manager.load_checkpoint(info_hash)

        if not checkpoint:
            return None

        return {
            "info_hash": info_hash.hex(),
            "name": checkpoint.torrent_name,
            "progress": len(checkpoint.verified_pieces) / checkpoint.total_pieces
            if checkpoint.total_pieces > 0
            else 0,
            "verified_pieces": len(checkpoint.verified_pieces),
            "total_pieces": checkpoint.total_pieces,
            "total_size": checkpoint.total_length,
            "created_at": checkpoint.created_at,
            "updated_at": checkpoint.updated_at,
            "can_resume": bool(checkpoint.torrent_file_path or checkpoint.magnet_uri),
            "torrent_file_path": checkpoint.torrent_file_path,
            "magnet_uri": checkpoint.magnet_uri,
        }

    async def validate_checkpoint(self, checkpoint: TorrentCheckpoint) -> bool:
        """Validate checkpoint integrity."""
        try:
            # Basic validation
            if (
                not checkpoint.info_hash
                or len(checkpoint.info_hash) != INFO_HASH_LENGTH
            ):
                return False

            if checkpoint.total_pieces <= 0 or checkpoint.piece_length <= 0:
                return False

            if checkpoint.total_length <= 0:
                return False

            # Validate verified pieces are within bounds
            for piece_idx in checkpoint.verified_pieces:
                if piece_idx < 0 or piece_idx >= checkpoint.total_pieces:
                    return False

            # Validate piece states
            for piece_idx, state in checkpoint.piece_states.items():
                if piece_idx < 0 or piece_idx >= checkpoint.total_pieces:
                    return False
                if not isinstance(state, PieceState):
                    return False

        except Exception:
            return False
        else:
            return True

    async def cleanup_completed_checkpoints(self) -> int:
        """Remove checkpoints for completed downloads."""
        checkpoint_manager = CheckpointManager(self.config.disk)
        checkpoints = await checkpoint_manager.list_checkpoints()

        cleaned = 0

        async def process_checkpoint(checkpoint_info):
            """Process a single checkpoint."""
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    checkpoint_info.info_hash,
                )
                if (
                    checkpoint
                    and len(checkpoint.verified_pieces) == checkpoint.total_pieces
                ):
                    # Download is complete, delete checkpoint
                    await checkpoint_manager.delete_checkpoint(
                        checkpoint_info.info_hash,
                    )
                    self.logger.info(
                        "Cleaned up completed checkpoint: %s",
                        checkpoint.torrent_name,
                    )
                    return True
            except Exception as e:
                self.logger.warning(
                    "Failed to process checkpoint %s: %s",
                    checkpoint_info.info_hash.hex(),
                    e,
                )
            return False

        for checkpoint_info in checkpoints:
            if await process_checkpoint(checkpoint_info):
                cleaned += 1

        return cleaned

    def load_torrent(self, torrent_path: str | Path) -> dict[str, Any] | None:
        """Load torrent file and return parsed data."""
        try:
            parser = TorrentParser()
            tdm = parser.parse(str(torrent_path))
            return {
                "name": tdm.name,
                "info_hash": tdm.info_hash,
                "pieces_info": {
                    "piece_hashes": list(tdm.pieces),
                    "piece_length": tdm.piece_length,
                    "num_pieces": tdm.num_pieces,
                    "total_length": tdm.total_length,
                },
                "file_info": {
                    "total_length": tdm.total_length,
                },
                "announce": getattr(tdm, "announce", ""),
            }
        except Exception:
            self.logger.exception("Failed to load torrent %s", torrent_path)
            return None

    def parse_magnet_link(self, magnet_uri: str) -> dict[str, Any] | None:
        """Parse magnet link and return torrent data."""
        try:
            magnet_info = parse_magnet(magnet_uri)
            return build_minimal_torrent_data(
                magnet_info.info_hash,
                magnet_info.display_name,
                magnet_info.trackers,
            )
        except Exception:
            self.logger.exception("Failed to parse magnet link")
            return None

    async def start_web_interface(
        self,
        host: str = "localhost",
        port: int = 9090,
    ) -> None:
        """Start web interface (placeholder implementation)."""
        self.logger.info("Web interface would start on http://%s:%s", host, port)
        # TODO: Implement actual web interface
        await asyncio.sleep(1)  # Placeholder to prevent immediate exit

    @property
    def peers(self) -> list[dict[str, Any]]:
        """Get list of connected peers (placeholder)."""
        return []

    @property
    def dht(self) -> Any | None:
        """Get DHT instance (placeholder)."""
        return None


# Backward compatibility
class SessionManager(AsyncSessionManager):
    """Backward compatibility wrapper for SessionManager."""

    def __init__(self, output_dir: str = "."):
        """Initialize SessionManager with output directory."""
        super().__init__(output_dir)
        self._session_started = False

    def add_torrent(self, path: str | dict[str, Any]) -> str:
        """Synchronous add_torrent for backward compatibility."""
        if not self._session_started:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.start())
            self._session_started = True

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(super().add_torrent(path))

    def add_magnet(self, uri: str) -> str:
        """Synchronous add_magnet for backward compatibility."""
        if not self._session_started:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.start())
            self._session_started = True

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(super().add_magnet(uri))

    def remove(self, info_hash_hex: str) -> bool:
        """Synchronous remove for backward compatibility."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(super().remove(info_hash_hex))

    def status(self) -> dict[str, Any]:
        """Synchronous status for backward compatibility."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(super().get_status())
