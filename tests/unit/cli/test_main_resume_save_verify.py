"""Tests for resume save and verify commands in ccbt.cli.main.

Covers:
- Resume save command (lines 2084-2134)
- Resume verify command (lines 2137-2276)
- All error paths and edge cases
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

cli_main = importlib.import_module("ccbt.cli.main")

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _run_coro_locally(coro):
    """Helper to run a coroutine to completion without touching global loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_cfg():
    """Create a mock config object."""
    return SimpleNamespace(
        disk=SimpleNamespace(
            fast_resume_enabled=True,
            checkpoint_dir="/tmp",
            resume_verify_on_load=True,
        )
    )


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager."""
    cfg = _make_cfg()
    cm = MagicMock()
    cm.config = cfg
    return cm


class TestResumeSave:
    """Tests for resume save command (lines 2084-2134)."""

    def test_resume_save_with_active_torrent(self, monkeypatch, mock_config_manager):
        """Test resume save with active torrent (lines 2084-2130)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        # Mock AsyncSessionManager
        mock_torrent_session = AsyncMock()
        mock_torrent_session._save_checkpoint = AsyncMock()

        class MockSession:
            def __init__(self):
                self.torrents = {bytes.fromhex(info_hash): mock_torrent_session}
                self.lock = AsyncMock()
                self.lock.__aenter__ = AsyncMock(return_value=None)
                self.lock.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *args, **kwargs: MockSession())
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        # Create context with config
        ctx_obj = {"config": _make_cfg()}
        result = runner.invoke(cli_main.resume_cmd, ["save", info_hash], obj=ctx_obj)
        assert result.exit_code == 0
        assert "Saved resume data" in result.output
        mock_torrent_session._save_checkpoint.assert_called_once()

    def test_resume_save_with_fast_resume_disabled(self, monkeypatch, mock_config_manager):
        """Test resume save with fast resume disabled (lines 2095-2097)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        cfg = _make_cfg()
        cfg.disk.fast_resume_enabled = False
        mock_config_manager.config = cfg

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        ctx_obj = {"config": cfg}
        result = runner.invoke(cli_main.resume_cmd, ["save", info_hash], obj=ctx_obj)
        assert result.exit_code == 0
        assert "Fast resume is disabled" in result.output

    def test_resume_save_with_invalid_info_hash(self, monkeypatch, mock_config_manager):
        """Test resume save with invalid info hash format (lines 2100-2105)."""
        runner = CliRunner()

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)

        ctx_obj = {"config": _make_cfg()}
        result = runner.invoke(cli_main.resume_cmd, ["save", "invalid-hex"], obj=ctx_obj)
        assert result.exit_code != 0
        assert "Invalid info hash format" in result.output

    def test_resume_save_with_torrent_not_found(self, monkeypatch, mock_config_manager):
        """Test resume save with torrent not found (lines 2114-2128)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        class MockSession:
            def __init__(self):
                self.torrents = {}  # Empty - torrent not found
                self.lock = AsyncMock()
                self.lock.__aenter__ = AsyncMock(return_value=None)
                self.lock.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *args, **kwargs: MockSession())
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        ctx_obj = {"config": _make_cfg()}
        result = runner.invoke(cli_main.resume_cmd, ["save", info_hash], obj=ctx_obj)
        assert result.exit_code == 0
        assert "Torrent not found or not active" in result.output
        assert "automatically saved" in result.output

    def test_resume_save_error_handling(self, monkeypatch, mock_config_manager):
        """Test resume save error handling (lines 2132-2134)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        class MockSession:
            def __init__(self):
                self.torrents = {bytes.fromhex(info_hash): MagicMock()}
                self.lock = AsyncMock()
                self.lock.__aenter__ = AsyncMock(side_effect=RuntimeError("Test error"))
                self.lock.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *args, **kwargs: MockSession())
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        ctx_obj = {"config": _make_cfg()}
        result = runner.invoke(cli_main.resume_cmd, ["save", info_hash], obj=ctx_obj)
        assert result.exit_code != 0


class TestResumeVerify:
    """Tests for resume verify command (lines 2137-2276)."""

    def test_resume_verify_with_valid_checkpoint(self, monkeypatch, mock_config_manager):
        """Test resume verify with valid checkpoint (lines 2137-2211)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        # Mock checkpoint with resume data
        mock_checkpoint = SimpleNamespace(
            resume_data={"pieces": [True] * 100},
            info_hash=info_hash_bytes,
        )

        # Mock CheckpointManager - must accept config.disk in __init__
        class MockCheckpointManager:
            def __init__(self, config):
                pass
            
            async def load_checkpoint(self, ih):
                return mock_checkpoint

        # Mock session (torrent not active)
        class MockSession:
            def __init__(self):
                self.torrents = {}
                self.lock = AsyncMock()
                self.lock.__aenter__ = AsyncMock(return_value=None)
                self.lock.__aexit__ = AsyncMock(return_value=None)

        fake_fast_resume_mod = ModuleType("ccbt.session.fast_resume")
        fake_storage_checkpoint_mod = ModuleType("ccbt.storage.checkpoint")
        fake_storage_resume_mod = ModuleType("ccbt.storage.resume_data")

        class MockFastResumeLoader:
            def __init__(self, *args, **kwargs):
                pass

            def validate_resume_data(self, *args, **kwargs):
                return True, []

        class MockFastResumeData:
            def __init__(self, **kwargs):
                # Accept any kwargs for testing
                for key, value in kwargs.items():
                    setattr(self, key, value)

        fake_fast_resume_mod.FastResumeLoader = MockFastResumeLoader
        fake_storage_checkpoint_mod.CheckpointManager = MockCheckpointManager
        fake_storage_resume_mod.FastResumeData = MockFastResumeData

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *args, **kwargs: MockSession())
        monkeypatch.setitem(sys.modules, "ccbt.session.fast_resume", fake_fast_resume_mod)
        monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_storage_checkpoint_mod)
        monkeypatch.setitem(sys.modules, "ccbt.storage.resume_data", fake_storage_resume_mod)
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        ctx_obj = {"config": _make_cfg()}
        result = runner.invoke(cli_main.resume_cmd, ["verify", info_hash], obj=ctx_obj)
        assert result.exit_code == 0
        assert "Resume data structure is valid" in result.output

    def test_resume_verify_with_no_checkpoint(self, monkeypatch, mock_config_manager):
        """Test resume verify with no checkpoint found (lines 2167-2170)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        class MockCheckpointManager:
            def __init__(self, config):
                pass
            
            async def load_checkpoint(self, ih):
                return None

        fake_mod = ModuleType("ccbt.storage.checkpoint")
        fake_mod.CheckpointManager = MockCheckpointManager

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)
        monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_mod)
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        ctx_obj = {"config": _make_cfg()}
        result = runner.invoke(cli_main.resume_cmd, ["verify", info_hash], obj=ctx_obj)
        assert result.exit_code != 0
        assert "No checkpoint found" in result.output

    def test_resume_verify_with_no_resume_data(self, monkeypatch, mock_config_manager):
        """Test resume verify with no resume data (lines 2173-2175)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()

        mock_checkpoint = SimpleNamespace(resume_data=None)

        class MockCheckpointManager:
            def __init__(self, config):
                pass
            
            async def load_checkpoint(self, ih):
                return mock_checkpoint

        fake_mod = ModuleType("ccbt.storage.checkpoint")
        fake_mod.CheckpointManager = MockCheckpointManager

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)
        monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_mod)
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        ctx_obj = {"config": _make_cfg()}
        result = runner.invoke(cli_main.resume_cmd, ["verify", info_hash], obj=ctx_obj)
        assert result.exit_code == 0
        assert "No resume data found" in result.output

    def test_resume_verify_integrity_check(self, monkeypatch, mock_config_manager):
        """Test resume verify integrity check (lines 2214-2242)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        # Mock checkpoint with resume data
        mock_checkpoint = SimpleNamespace(resume_data={"pieces": [True] * 100})

        # Mock torrent session
        mock_torrent_session = MagicMock()
        mock_torrent_session.torrent_data = SimpleNamespace()

        class MockSession:
            def __init__(self):
                self.torrents = {info_hash_bytes: mock_torrent_session}
                self.lock = AsyncMock()
                self.lock.__aenter__ = AsyncMock(return_value=None)
                self.lock.__aexit__ = AsyncMock(return_value=None)

        # Mock CheckpointManager
        class MockCheckpointManager:
            def __init__(self, config):
                pass
            
            async def load_checkpoint(self, ih):
                return mock_checkpoint

        # Mock FastResumeLoader
        class MockFastResumeLoader:
            def __init__(self, *args, **kwargs):
                pass

            def validate_resume_data(self, *args, **kwargs):
                return True, []

            async def verify_integrity(self, *args, **kwargs):
                return {
                    "valid": True,
                    "verified_pieces": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                }

        class MockFastResumeData:
            def __init__(self, **kwargs):
                # Accept any kwargs for testing
                for key, value in kwargs.items():
                    setattr(self, key, value)

        fake_fast_resume_mod = ModuleType("ccbt.session.fast_resume")
        fake_storage_checkpoint_mod = ModuleType("ccbt.storage.checkpoint")
        fake_storage_resume_mod = ModuleType("ccbt.storage.resume_data")

        fake_fast_resume_mod.FastResumeLoader = MockFastResumeLoader
        fake_storage_checkpoint_mod.CheckpointManager = MockCheckpointManager
        fake_storage_resume_mod.FastResumeData = MockFastResumeData

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *args, **kwargs: MockSession())
        monkeypatch.setitem(sys.modules, "ccbt.session.fast_resume", fake_fast_resume_mod)
        monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_storage_checkpoint_mod)
        monkeypatch.setitem(sys.modules, "ccbt.storage.resume_data", fake_storage_resume_mod)
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        ctx_obj = {"config": _make_cfg()}
        result = runner.invoke(cli_main.resume_cmd, ["verify", info_hash, "--verify-pieces", "10"], obj=ctx_obj)
        assert result.exit_code == 0
        assert "Integrity verification passed" in result.output
        assert "10 pieces verified" in result.output

    def test_resume_verify_integrity_failure(self, monkeypatch, mock_config_manager):
        """Test resume verify integrity failure (lines 2237-2242)."""
        runner = CliRunner()
        info_hash = (b"\x00" * 20).hex()
        info_hash_bytes = bytes.fromhex(info_hash)

        mock_checkpoint = SimpleNamespace(resume_data={"pieces": [True] * 100})
        mock_torrent_session = MagicMock()
        mock_torrent_session.torrent_data = SimpleNamespace()

        class MockSession:
            def __init__(self):
                self.torrents = {info_hash_bytes: mock_torrent_session}
                self.lock = AsyncMock()
                self.lock.__aenter__ = AsyncMock(return_value=None)
                self.lock.__aexit__ = AsyncMock(return_value=None)

        class MockCheckpointManager:
            def __init__(self, config):
                pass
            
            async def load_checkpoint(self, ih):
                return mock_checkpoint

        class MockFastResumeLoader:
            def __init__(self, *args, **kwargs):
                pass

            def validate_resume_data(self, *args, **kwargs):
                return True, []

            async def verify_integrity(self, *args, **kwargs):
                return {
                    "valid": False,
                    "failed_pieces": [5, 6, 7],
                }

        class MockFastResumeData:
            def __init__(self, **kwargs):
                # Accept any kwargs for testing
                for key, value in kwargs.items():
                    setattr(self, key, value)

        fake_fast_resume_mod = ModuleType("ccbt.session.fast_resume")
        fake_storage_checkpoint_mod = ModuleType("ccbt.storage.checkpoint")
        fake_storage_resume_mod = ModuleType("ccbt.storage.resume_data")

        fake_fast_resume_mod.FastResumeLoader = MockFastResumeLoader
        fake_storage_checkpoint_mod.CheckpointManager = MockCheckpointManager
        fake_storage_resume_mod.FastResumeData = MockFastResumeData

        monkeypatch.setattr(cli_main, "ConfigManager", lambda *args, **kwargs: mock_config_manager)
        monkeypatch.setattr(cli_main, "AsyncSessionManager", lambda *args, **kwargs: MockSession())
        monkeypatch.setitem(sys.modules, "ccbt.session.fast_resume", fake_fast_resume_mod)
        monkeypatch.setitem(sys.modules, "ccbt.storage.checkpoint", fake_storage_checkpoint_mod)
        monkeypatch.setitem(sys.modules, "ccbt.storage.resume_data", fake_storage_resume_mod)
        monkeypatch.setattr(cli_main.asyncio, "run", _run_coro_locally)

        ctx_obj = {"config": _make_cfg()}
        result = runner.invoke(cli_main.resume_cmd, ["verify", info_hash, "--verify-pieces", "10"], obj=ctx_obj)
        assert result.exit_code == 0
        assert "Integrity verification failed" in result.output
        assert "3 pieces failed" in result.output

