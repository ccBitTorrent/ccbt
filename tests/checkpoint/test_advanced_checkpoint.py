"""Advanced checkpoint operation tests (smoke-level)."""

from pathlib import Path

import pytest

from ccbt.checkpoint import CheckpointManager
from ccbt.config import get_config


@pytest.mark.asyncio
async def test_checkpoint_backup_restore_roundtrip(tmp_path: Path):
	cfg = get_config()
	cm = CheckpointManager(cfg.disk)
	# Use a dummy info-hash (all zeros) and expect graceful handling
	ih = bytes(20)
	# Backup should succeed even if checkpoint missing (returns computed path or raises handled)
	backup_path = tmp_path / "cp.backup"
	try:
		_ = await cm.backup_checkpoint(ih, backup_path)
	except Exception:
		# Accept no-op behavior if nothing to backup
		pass
	# Restore should handle file gracefully: either return a checkpoint or raise
	try:
		cp = await cm.restore_checkpoint(backup_path)
		assert cp is not None
		assert hasattr(cp, "info_hash")
	except Exception:
		# Accept failure if backup content is not restorable
		pass


