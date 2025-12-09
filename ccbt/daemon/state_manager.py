"""State manager for daemon state persistence.

from __future__ import annotations

Manages serialization and persistence of daemon state using msgpack format.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False
    msgpack = None  # type: ignore[assignment]

from ccbt.daemon.state_models import (
    STATE_VERSION,
    DaemonState,
    SessionState,
    TorrentState,
)
from ccbt.utils.logging_config import get_logger

logger = get_logger(__name__)


class StateManager:
    """Manages daemon state persistence using msgpack format."""

    def __init__(self, state_dir: str | Path | None = None):
        """Initialize state manager.

        Args:
            state_dir: Directory for state files (default: ~/.ccbt/daemon)

        """
        if state_dir is None:
            # CRITICAL FIX: Use consistent path resolution helper to match daemon
            from ccbt.daemon.daemon_manager import _get_daemon_home_dir
            home_dir = _get_daemon_home_dir()
            state_dir = home_dir / ".ccbt" / "daemon"
        elif isinstance(state_dir, str):
            state_dir = Path(state_dir).expanduser()

        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.state_dir / "state.msgpack"
        self.backup_file = self.state_dir / "state.msgpack.backup"
        self.json_export_file = self.state_dir / "state.json.export"

        self._lock = asyncio.Lock()

        if not HAS_MSGPACK:
            msg = "msgpack is required for state persistence. Install with: pip install msgpack"
            raise ImportError(msg)

    async def save_state(self, session_manager: Any) -> None:
        """Save session manager state to msgpack file.

        Args:
            session_manager: AsyncSessionManager instance

        """
        async with self._lock:
            try:
                # Build state from session manager
                state = await self._build_state(session_manager)

                # Create backup of existing state
                if self.state_file.exists():
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        self._create_backup,
                    )

                # Serialize to msgpack
                state_dict = state.model_dump_for_msgpack()

                # Write atomically (write to temp, then rename)
                temp_file = self.state_file.with_suffix(".tmp")
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._write_msgpack,
                    temp_file,
                    state_dict,
                )

                # Atomic rename
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    temp_file.replace,
                    self.state_file,
                )

                logger.debug("State saved to %s", self.state_file)

            except Exception:
                logger.exception("Error saving state")
                raise

    async def load_state(self) -> DaemonState | None:
        """Load state from msgpack file.

        Returns:
            DaemonState instance or None if not found

        """
        async with self._lock:
            if not self.state_file.exists():
                return None

            try:
                # Read msgpack file
                state_dict = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._read_msgpack,
                    self.state_file,
                )

                # Validate and create state object
                state = DaemonState.model_validate_from_msgpack(state_dict)

                # Check if migration is needed
                if state.version != STATE_VERSION:
                    try:
                        state_version_parts = [int(x) for x in state.version.split(".")]
                        current_version_parts = [
                            int(x) for x in STATE_VERSION.split(".")
                        ]

                        if state_version_parts < current_version_parts:
                            # Older version - attempt migration
                            logger.info(
                                "Migrating state from version %s to %s",
                                state.version,
                                STATE_VERSION,
                            )
                            migrated_state = await self._migrate_state(
                                state, state.version
                            )
                            if migrated_state:
                                state = migrated_state
                            else:
                                logger.warning(
                                    "Migration failed, but continuing with original state"
                                )
                    except (ValueError, AttributeError):
                        logger.warning(
                            "Could not parse version numbers, continuing with load"
                        )

                # Validate state integrity
                if not await self.validate_state(state):
                    logger.warning("State validation failed, attempting recovery")
                    # Try backup
                    if self.backup_file.exists():
                        logger.info("Attempting to load from backup")
                        state_dict = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self._read_msgpack,
                            self.backup_file,
                        )
                        state = DaemonState.model_validate_from_msgpack(state_dict)
                        # Try migration on backup too
                        if state.version != STATE_VERSION:
                            try:
                                state_version_parts = [
                                    int(x) for x in state.version.split(".")
                                ]
                                current_version_parts = [
                                    int(x) for x in STATE_VERSION.split(".")
                                ]
                                if state_version_parts < current_version_parts:
                                    migrated_state = await self._migrate_state(
                                        state, state.version
                                    )
                                    if migrated_state:
                                        state = migrated_state
                            except (ValueError, AttributeError):
                                pass

                logger.debug("State loaded from %s", self.state_file)
                return state

            except Exception as e:
                logger.exception("Error loading state: %s", e)
                # Try backup
                if self.backup_file.exists():
                    try:
                        logger.info("Attempting to load from backup")
                        state_dict = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self._read_msgpack,
                            self.backup_file,
                        )
                        return DaemonState.model_validate_from_msgpack(state_dict)
                    except Exception:
                        logger.exception("Error loading backup state")

                return None

    async def _build_state(self, session_manager: Any) -> DaemonState:
        """Build DaemonState from session manager.

        Args:
            session_manager: AsyncSessionManager instance

        Returns:
            DaemonState instance

        """
        # Get session status
        status_dict = await session_manager.get_status()
        global_stats = await session_manager.get_global_stats()

        # Build torrent states
        torrents = {}
        for info_hash_hex, status in status_dict.items():
            # Extract per-torrent options and rate limits from session
            per_torrent_options = None
            rate_limits = None

            try:
                info_hash_bytes = bytes.fromhex(info_hash_hex)
                async with session_manager.lock:
                    torrent_session = session_manager.torrents.get(info_hash_bytes)
                    if torrent_session and hasattr(torrent_session, "options"):
                        if torrent_session.options:
                            per_torrent_options = dict(torrent_session.options)

                # Get rate limits from session manager
                if (
                    hasattr(session_manager, "_per_torrent_limits")
                    and info_hash_bytes in session_manager._per_torrent_limits
                ):
                    limits = session_manager._per_torrent_limits[info_hash_bytes]
                    rate_limits = {
                        "down_kib": limits.get("down_kib", 0),
                        "up_kib": limits.get("up_kib", 0),
                    }
            except Exception as e:
                logger.debug("Failed to extract per-torrent config for %s: %s", info_hash_hex[:12], e)

            torrents[info_hash_hex] = TorrentState(
                info_hash=info_hash_hex,
                name=status.get("name", "Unknown"),
                status=status.get("status", "unknown"),
                progress=status.get("progress", 0.0),
                output_dir=status.get("output_dir", "."),
                added_at=status.get("added_time", time.time()),
                paused=status.get("status") == "paused",
                download_rate=status.get("download_rate", 0.0),
                upload_rate=status.get("upload_rate", 0.0),
                num_peers=status.get("num_peers", 0),
                total_size=status.get("total_size", 0),
                downloaded=status.get("downloaded", 0),
                uploaded=status.get("uploaded", 0),
                torrent_file_path=status.get("torrent_file_path"),
                magnet_uri=status.get("magnet_uri"),
                per_torrent_options=per_torrent_options,
                rate_limits=rate_limits,
            )

        # Build session state
        session = SessionState(
            started_at=time.time(),  # Will be updated on load
            total_downloaded=global_stats.get("total_downloaded", 0),
            total_uploaded=global_stats.get("total_uploaded", 0),
            global_download_rate=global_stats.get("download_rate", 0.0),
            global_upload_rate=global_stats.get("upload_rate", 0.0),
        )

        # Build component state
        from ccbt.daemon.state_models import ComponentState

        # Collect NAT port mappings
        nat_mapped_ports = {}
        if session_manager.nat_manager and hasattr(
            session_manager.nat_manager, "port_mapping_manager"
        ):
            try:
                mappings = await session_manager.nat_manager.port_mapping_manager.get_all_mappings()
                nat_mapped_ports = {m.protocol: m.external_port for m in mappings}
            except Exception as e:
                logger.warning("Failed to get NAT mappings: %s", e)

        components = ComponentState(
            dht_enabled=session_manager.config.discovery.enable_dht
            if session_manager.config
            else False,
            dht_nodes=len(session_manager.dht_client.routing_table.nodes)
            if session_manager.dht_client
            and hasattr(session_manager.dht_client, "routing_table")
            else 0,
            nat_enabled=session_manager.config.nat.auto_map_ports
            if session_manager.config
            else False,
            nat_mapped_ports=nat_mapped_ports,
        )

        # Create state
        return DaemonState(
            version=STATE_VERSION,
            created_at=time.time(),
            updated_at=time.time(),
            torrents=torrents,
            session=session,
            components=components,
        )

    async def validate_state(self, state: DaemonState) -> bool:
        """Validate state integrity.

        Args:
            state: DaemonState to validate

        Returns:
            True if valid, False otherwise

        """
        try:
            # Check version (migration should have been done in load_state)
            if state.version != STATE_VERSION:
                # Try to parse version numbers for comparison
                try:
                    state_version_parts = [int(x) for x in state.version.split(".")]
                    current_version_parts = [int(x) for x in STATE_VERSION.split(".")]

                    if state_version_parts > current_version_parts:
                        # Newer version - reject (daemon too old)
                        logger.error(
                            "State version %s is newer than daemon version %s. "
                            "Please upgrade the daemon.",
                            state.version,
                            STATE_VERSION,
                        )
                        return False
                    # Older versions should have been migrated, but allow with warning
                    logger.warning(
                        "State version %s != %s (migration may have failed)",
                        state.version,
                        STATE_VERSION,
                    )
                except (ValueError, AttributeError):
                    # Version format not recognized, but allow load with warning
                    logger.warning(
                        "Could not parse version numbers, allowing load with warning"
                    )

            # Check torrent states
            for info_hash_hex, torrent_state in state.torrents.items():
                if torrent_state.progress < 0.0 or torrent_state.progress > 1.0:
                    logger.warning(
                        "Invalid progress for torrent %s: %f",
                        info_hash_hex,
                        torrent_state.progress,
                    )
                    return False

            return True

        except Exception:
            logger.exception("Error validating state")
            return False

    async def _migrate_state(
        self, state: DaemonState, from_version: str
    ) -> DaemonState | None:
        """Migrate state from an older version to current version.

        Args:
            state: DaemonState from older version
            from_version: Version string of the state

        Returns:
            Migrated DaemonState or None if migration failed

        """
        try:
            # For now, migration is a no-op (just log)
            # Future migrations can be added here as the format evolves
            logger.info(
                "Migrating state from version %s to %s (no-op for now)",
                from_version,
                STATE_VERSION,
            )

            # Update version to current
            state.version = STATE_VERSION
            state.updated_at = time.time()

            # Add any migration logic here as needed
            # Example: if from_version == "0.9":
            #     # Migrate from 0.9 to 1.0
            #     # Add new fields, transform data, etc.

            return state
        except Exception as e:
            logger.exception("Error migrating state: %s", e)
            return None

    async def export_to_json(self) -> Path:
        """Export state to JSON for debugging.

        Returns:
            Path to exported JSON file

        """
        async with self._lock:
            state = await self.load_state()
            if not state:
                msg = "No state to export"
                raise ValueError(msg)

            # Convert to JSON-serializable dict
            state_dict = state.model_dump(mode="json")

            # Write JSON file
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._write_json,
                self.json_export_file,
                state_dict,
            )

            logger.info("State exported to JSON: %s", self.json_export_file)
            return self.json_export_file

    def _create_backup(self) -> None:
        """Create backup of current state file."""
        if self.state_file.exists():
            import shutil

            shutil.copy2(self.state_file, self.backup_file)

    def _write_msgpack(self, path: Path, data: dict[str, Any]) -> None:
        """Write msgpack data to file.

        Args:
            path: File path
            data: Data to serialize

        """
        if not HAS_MSGPACK or msgpack is None:
            msg = "msgpack not available"
            raise RuntimeError(msg)

        with open(path, "wb") as f:
            msgpack.pack(data, f)  # type: ignore[attr-defined]
            f.flush()
            os.fsync(f.fileno())

    def _read_msgpack(self, path: Path) -> dict[str, Any]:
        """Read msgpack data from file.

        Args:
            path: File path

        Returns:
            Deserialized data

        """
        if not HAS_MSGPACK or msgpack is None:
            msg = "msgpack not available"
            raise RuntimeError(msg)

        with open(path, "rb") as f:
            return msgpack.unpack(f, raw=False)  # type: ignore[attr-defined]

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Write JSON data to file.

        Args:
            path: File path
            data: Data to serialize

        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
