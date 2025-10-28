"""Enhanced end-to-end integration tests for config overrides, checkpoint ops, and monitoring wiring."""

from pathlib import Path

import pytest
import pytest_asyncio

from ccbt.checkpoint import CheckpointManager
from ccbt.config import ConfigManager, init_config
from ccbt.models import DownloadStats, TorrentCheckpoint
from ccbt.session import AsyncSessionManager


@pytest_asyncio.fixture
async def session_manager(tmp_path: Path):
    # Initialize config with a temp working directory
    init_config(None)
    sm = AsyncSessionManager(str(tmp_path))
    try:
        await sm.start()
        yield sm
    finally:
        await sm.stop()


@pytest.mark.asyncio
async def test_config_override_and_session(session_manager: AsyncSessionManager):
    # Override a few runtime settings via ConfigManager
    cm = ConfigManager(None)
    cm.config.network.listen_port = 7005
    cm.config.disk.write_buffer_kib = 256
    # No torrent run here; just assert we can get global stats without error
    stats = await session_manager.get_global_stats()
    assert "num_torrents" in stats


@pytest.mark.asyncio
async def test_checkpoint_migration_and_resume(
    tmp_path: Path,
    session_manager: AsyncSessionManager,
):
    # Create a minimal checkpoint object and save it (JSON), then migrate to binary and back
    info_hash = b"\x00" * 20
    cp = TorrentCheckpoint(
        info_hash=info_hash,
        torrent_name="enhanced",
        created_at=0.0,
        updated_at=0.0,
        total_pieces=1,
        piece_length=16384,
        total_length=16384,
        verified_pieces=[],
        piece_states={},
        download_stats=DownloadStats(),
        output_dir=str(tmp_path),
        files=[],
    )
    cm = CheckpointManager()

    # Save checkpoint in JSON format explicitly
    from ccbt.models import CheckpointFormat
    json_path = await cm.save_checkpoint(cp, CheckpointFormat.JSON)

    # Verify the JSON file was created and has content
    assert json_path.exists()
    assert json_path.stat().st_size > 0

    # Verify we can load the checkpoint
    loaded_checkpoint = await cm.load_checkpoint(info_hash)
    assert loaded_checkpoint is not None
    assert loaded_checkpoint.torrent_name == "enhanced"

    # Migrate JSON -> BINARY and back
    path_bin = await cm.convert_checkpoint_format(
        info_hash,
        CheckpointFormat.JSON,
        CheckpointFormat.BINARY,
    )
    assert path_bin.exists()
    assert path_bin.stat().st_size > 0

    path_json = await cm.convert_checkpoint_format(
        info_hash,
        CheckpointFormat.BINARY,
        CheckpointFormat.JSON,
    )
    assert path_json.exists()
    assert path_json.stat().st_size > 0

    # Attempt resume_from_checkpoint; should raise due to missing sources but not crash
    checkpoint = await cm.load_checkpoint(info_hash)
    assert checkpoint is not None
    with pytest.raises(Exception):
        await session_manager.resume_from_checkpoint(info_hash, checkpoint)


@pytest.mark.asyncio
async def test_monitoring_alerts_integration_smoke():
    # Ensure alert manager can process a simple rule evaluation quickly
    from ccbt.monitoring import get_alert_manager

    am = get_alert_manager()
    # Add a simple rule and process a value
    from ccbt.monitoring.alert_manager import AlertRule, AlertSeverity

    am.add_alert_rule(
        AlertRule(
            name="cpu_test",
            metric_name="system.cpu",
            condition="value > 10",
            severity=AlertSeverity.WARNING,
            description="cpu test",
        ),
    )
    await am.process_alert("system.cpu", 50)
    # Should have at least one active alert
    assert getattr(am, "active_alerts", {})
    # Clear alerts
    for aid in list(getattr(am, "active_alerts", {}).keys()):
        await am.resolve_alert(aid)
    assert not getattr(am, "active_alerts", {})
