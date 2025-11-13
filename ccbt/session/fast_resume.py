"""Fast Resume Loader for ccBitTorrent.

Provides loading, validation, migration, and integrity verification
for fast resume data.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from ccbt.storage.checkpoint import TorrentCheckpoint

from ccbt.storage.resume_data import FastResumeData
from ccbt.utils.logging_config import get_logger

if TYPE_CHECKING:  # pragma: no cover - type checking only, not executed at runtime
    from ccbt.models import TorrentInfo as TorrentInfoModel


class FastResumeLoader:
    """Loads and validates fast resume data."""

    def __init__(self, config: Any) -> None:
        """Initialize fast resume loader.

        Args:
            config: Disk configuration with resume settings

        """
        self.config = config
        self.logger = get_logger(__name__)

    def validate_resume_data(
        self,
        resume_data: FastResumeData,
        torrent_info: TorrentInfoModel | dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """Validate resume data against torrent metadata.

        Args:
            resume_data: Resume data to validate
            torrent_info: Torrent metadata

        Returns:
            Tuple of (is_valid, list_of_errors)

        """
        errors: list[str] = []

        # Check info hash matches
        if isinstance(torrent_info, dict):
            expected_hash = torrent_info.get("info_hash")
        else:
            expected_hash = getattr(torrent_info, "info_hash", None)

        if expected_hash and resume_data.info_hash != expected_hash:
            errors.append("Info hash mismatch")

        # Check piece count matches
        if isinstance(torrent_info, dict):
            pieces_data = torrent_info.get("pieces", b"")
            total_pieces = len(pieces_data) // 20 if pieces_data else 0
        else:
            total_pieces = getattr(torrent_info, "total_pieces", 0)

        # Decode bitmap and verify piece count
        verified_pieces = FastResumeData.decode_piece_bitmap(
            resume_data.piece_completion_bitmap,
            total_pieces,
        )

        if len(verified_pieces) > total_pieces:
            errors.append(
                f"Verified pieces ({len(verified_pieces)}) > total ({total_pieces})",
            )

        if total_pieces > 0:
            invalid_pieces = {p for p in verified_pieces if p < 0 or p >= total_pieces}
            if invalid_pieces:
                errors.append(f"Invalid piece indices: {sorted(invalid_pieces)}")

        return (len(errors) == 0, errors)

    def migrate_resume_data(
        self,
        resume_data: FastResumeData,
        target_version: int,
    ) -> FastResumeData:
        """Migrate resume data to target version.

        Args:
            resume_data: Resume data to migrate
            target_version: Target version to migrate to

        Returns:
            Migrated resume data

        """
        if resume_data.version >= target_version:
            return resume_data

        self.logger.info(
            "Migrating resume data from version %d to %d",
            resume_data.version,
            target_version,
        )

        # Version 1 -> 2 migration example
        current_version = resume_data.version
        while current_version < target_version:
            if current_version == 1 and target_version >= 2:
                # Add new fields with defaults if not present
                if (
                    not hasattr(resume_data, "queue_position")
                    or resume_data.queue_position is None
                ):
                    resume_data.queue_position = None
                if (
                    not hasattr(resume_data, "queue_priority")
                    or resume_data.queue_priority is None
                ):
                    resume_data.queue_priority = None
                current_version = 2
                resume_data.version = 2
            else:
                # Unknown migration path
                self.logger.warning(
                    "Unknown migration path from version %d to %d",
                    current_version,
                    target_version,
                )
                break

        self.logger.info(
            "Resume data migration complete: version %d", resume_data.version
        )
        return resume_data

    async def verify_integrity(
        self,
        resume_data: FastResumeData,
        torrent_info: TorrentInfoModel | dict[str, Any],
        file_assembler: Any | None,
        num_pieces_to_verify: int = 10,
    ) -> dict[str, Any]:
        """Verify integrity of critical pieces.

        Args:
            resume_data: Resume data to verify
            torrent_info: Torrent metadata
            file_assembler: File assembler for piece verification
            num_pieces_to_verify: Number of random pieces to verify (0 = disable)

        Returns:
            Dictionary with 'valid', 'verified_pieces', 'failed_pieces'

        """
        if num_pieces_to_verify <= 0:
            return {
                "valid": True,
                "verified_pieces": [],
                "failed_pieces": [],
            }

        # Get piece hashes
        if isinstance(torrent_info, dict):
            pieces_data = torrent_info.get("pieces", b"")
            piece_hashes = [
                pieces_data[i : i + 20] for i in range(0, len(pieces_data), 20)
            ]
        else:
            # Get from TorrentInfoModel
            piece_hashes = getattr(torrent_info, "piece_hashes", [])

        if not piece_hashes:
            return {
                "valid": False,
                "verified_pieces": [],
                "failed_pieces": [],
                "error": "No piece hashes available",
            }

        total_pieces = len(piece_hashes)

        # Decode verified pieces
        verified_pieces = FastResumeData.decode_piece_bitmap(
            resume_data.piece_completion_bitmap,
            total_pieces,
        )

        if not verified_pieces:
            # No pieces to verify, consider valid
            return {
                "valid": True,
                "verified_pieces": [],
                "failed_pieces": [],
            }

        # Select random pieces to verify
        pieces_to_check = random.sample(
            list(verified_pieces),
            min(num_pieces_to_verify, len(verified_pieces)),
        )

        # Verify pieces
        failed_pieces: list[int] = []
        for piece_idx in pieces_to_check:
            if 0 <= piece_idx < len(piece_hashes):
                expected_hash = piece_hashes[piece_idx]
                if file_assembler and hasattr(file_assembler, "verify_piece_hash"):
                    try:
                        is_valid = await file_assembler.verify_piece_hash(
                            piece_idx,
                            expected_hash,
                        )
                        if not is_valid:
                            failed_pieces.append(piece_idx)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to verify piece %d: %s",
                            piece_idx,
                            e,
                        )
                        failed_pieces.append(piece_idx)
                else:
                    # Cannot verify without file assembler
                    self.logger.debug(
                        "Skipping piece %d verification (no file assembler)",
                        piece_idx,
                    )

        return {
            "valid": len(failed_pieces) == 0,
            "verified_pieces": pieces_to_check,
            "failed_pieces": failed_pieces,
        }

    async def handle_corrupted_resume(
        self,
        _resume_data: FastResumeData | None,
        error: Exception,
        checkpoint: TorrentCheckpoint | None,
    ) -> dict[str, Any]:
        """Handle corrupted resume data gracefully.

        Args:
            resume_data: Corrupted resume data (may be None)
            error: Exception that occurred
            checkpoint: Fallback checkpoint data

        Returns:
            Dictionary with fallback strategy

        """
        self.logger.warning(
            "Corrupted resume data detected: %s. Falling back to checkpoint.",
            error,
        )

        # Fallback strategy
        if checkpoint:
            self.logger.info("Using checkpoint as fallback")
            return {
                "strategy": "checkpoint",
                "checkpoint": checkpoint,
                "requires_full_recheck": True,
            }
        self.logger.warning("No checkpoint available, requiring full recheck")
        return {
            "strategy": "full_recheck",
            "requires_full_recheck": True,
        }

    def should_verify_on_load(self) -> bool:
        """Check if integrity verification should be performed on load.

        Returns:
            True if verification is enabled

        """
        # Handle both Config (has .disk) and DiskConfig directly
        disk_config = getattr(self.config, "disk", self.config)
        return getattr(disk_config, "resume_verify_on_load", True)

    def get_verify_pieces_count(self) -> int:
        """Get number of pieces to verify on resume.

        Returns:
            Number of pieces to verify (0 = disabled)

        """
        # Handle both Config (has .disk) and DiskConfig directly
        disk_config = getattr(self.config, "disk", self.config)
        return getattr(disk_config, "resume_verify_pieces", 10)
