"""Unit tests for disk I/O initialization functions.

Tests for get_disk_io_manager(), init_disk_io(), and shutdown_disk_io()
from ccbt.storage.disk_io_init module.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch

from ccbt.storage.disk_io import DiskIOManager
from ccbt.storage.disk_io_init import (
    get_disk_io_manager,
    init_disk_io,
    shutdown_disk_io,
)

pytestmark = [pytest.mark.unit, pytest.mark.storage]


class TestGetDiskIOManager:
    """Tests for get_disk_io_manager() singleton function."""

    def test_singleton_pattern(self):
        """Test that get_disk_io_manager() returns same instance."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Reset singleton
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        manager1 = get_disk_io_manager()
        manager2 = get_disk_io_manager()

        assert manager1 is manager2
        assert isinstance(manager1, DiskIOManager)

    def test_creates_new_instance_if_none(self):
        """Test that new instance is created if singleton is None."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Reset singleton
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        manager = get_disk_io_manager()
        assert manager is not None
        assert isinstance(manager, DiskIOManager)

    def test_uses_config_values(self, mock_config, monkeypatch):
        """Test that manager uses config values correctly."""
        import ccbt.storage.disk_io_init as disk_io_module
        from unittest.mock import Mock

        # Reset singleton
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Create a new mock config with different values
        test_config = Mock()
        test_disk = Mock()
        test_disk.disk_workers = 4
        test_disk.disk_queue_size = 300
        test_disk.cache_size_mb = 512
        test_config.disk = test_disk

        # Patch get_config in all places it's used
        from ccbt import config as config_module
        from ccbt.storage import disk_io as disk_io_module_internal

        monkeypatch.setattr(config_module, "get_config", lambda: test_config)
        monkeypatch.setattr(disk_io_module, "get_config", lambda: test_config)
        monkeypatch.setattr(disk_io_module_internal, "get_config", lambda: test_config)

        manager = get_disk_io_manager()

        assert manager.max_workers == 4
        assert manager.queue_size == 300
        assert manager.cache_size_mb == 512

    def test_uses_default_cache_size_if_not_set(self, mock_config):
        """Test that default cache_size_mb is used if not in config."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Reset singleton
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Remove cache_size_mb from config
        delattr(mock_config.disk, "cache_size_mb")

        manager = get_disk_io_manager()

        # Should use default 256
        assert manager.cache_size_mb == 256


class TestInitDiskIO:
    """Tests for init_disk_io() async function."""

    @pytest.mark.asyncio
    async def test_init_creates_and_starts_manager(self, mock_config):
        """Test initialization creates and starts global instance."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Ensure clean state
        await shutdown_disk_io()
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Set config values
        mock_config.disk.disk_workers = 2
        mock_config.disk.disk_queue_size = 200

        disk_io = await init_disk_io()

        assert disk_io is not None
        assert isinstance(disk_io, DiskIOManager)
        assert disk_io._running is True  # noqa: SLF001
        assert disk_io.max_workers == 2
        assert disk_io.queue_size == 200

        # Cleanup
        await shutdown_disk_io()

    @pytest.mark.asyncio
    async def test_init_idempotent(self, mock_config):
        """Test that init_disk_io() is idempotent (safe to call multiple times)."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Ensure clean state
        await shutdown_disk_io()
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # First init
        disk_io1 = await init_disk_io()
        assert disk_io1 is not None
        assert disk_io1._running is True  # noqa: SLF001

        # Second init (should return same instance, already running)
        disk_io2 = await init_disk_io()
        assert disk_io2 is not None
        assert disk_io2 is disk_io1  # Same instance
        assert disk_io2._running is True  # noqa: SLF001

        # Cleanup
        await shutdown_disk_io()

    @pytest.mark.asyncio
    async def test_init_handles_config_error(self, monkeypatch):
        """Test that init_disk_io() handles config errors gracefully."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Ensure clean state
        await shutdown_disk_io()
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Patch get_config to raise exception in the module where it's used
        def raise_error():
            raise RuntimeError("Config error")

        # Patch where it's imported (in disk_io_init module)
        monkeypatch.setattr(disk_io_module, "get_config", raise_error)

        # Should not raise, but return None
        result = await init_disk_io()
        assert result is None

    @pytest.mark.asyncio
    async def test_init_handles_start_error(self, mock_config, monkeypatch):
        """Test that init_disk_io() handles start() errors gracefully."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Ensure clean state
        await shutdown_disk_io()
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Get manager and patch start() to raise
        manager = get_disk_io_manager()

        async def raise_error():
            raise Exception("Start error")

        monkeypatch.setattr(manager, "start", raise_error)

        # Should return None, not raise
        result = await init_disk_io()
        assert result is None

    @pytest.mark.asyncio
    async def test_init_handles_general_exception(self, monkeypatch):
        """Test that init_disk_io() handles general exceptions gracefully."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Ensure clean state
        await shutdown_disk_io()
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Patch get_disk_io_manager to raise exception
        def raise_error():
            raise Exception("General error")

        monkeypatch.setattr(
            "ccbt.storage.disk_io_init.get_disk_io_manager", raise_error
        )

        # Should return None, not raise
        result = await init_disk_io()
        assert result is None

    @pytest.mark.asyncio
    async def test_background_tasks_started(self, mock_config):
        """Test that background tasks are started after init."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Ensure clean state
        await shutdown_disk_io()
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        disk_io = await init_disk_io()
        assert disk_io is not None

        # Check that background tasks exist
        assert disk_io._write_batcher_task is not None
        assert disk_io._cache_cleaner_task is not None

        # Cleanup
        await shutdown_disk_io()


class TestShutdownDiskIO:
    """Tests for shutdown_disk_io() async function."""

    @pytest.mark.asyncio
    async def test_shutdown_when_running(self, mock_config):
        """Test graceful shutdown when disk I/O is running."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Reset singleton
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Start disk I/O
        disk_io = await init_disk_io()
        assert disk_io is not None
        assert disk_io._running is True  # noqa: SLF001

        # Shutdown
        await shutdown_disk_io()

        # Disk I/O should be stopped
        assert disk_io._running is False  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_shutdown_when_not_running(self, mock_config):
        """Test shutdown is no-op when disk I/O not running."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Reset singleton
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Get manager but don't start it
        manager = get_disk_io_manager()
        assert manager._running is False  # noqa: SLF001

        # Should not raise
        await shutdown_disk_io()

        # Still not running
        assert manager._running is False  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_shutdown_when_not_initialized(self):
        """Test shutdown when disk I/O manager not initialized."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Ensure singleton is None
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Should not raise
        await shutdown_disk_io()

    @pytest.mark.asyncio
    async def test_shutdown_handles_exceptions(self, mock_config, monkeypatch):
        """Test that shutdown_disk_io() handles exceptions gracefully."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Reset singleton
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Start disk I/O
        disk_io = await init_disk_io()
        assert disk_io is not None

        # Patch stop() to raise exception
        original_stop = disk_io.stop

        async def raise_error():
            raise Exception("Stop error")

        monkeypatch.setattr(disk_io, "stop", raise_error)

        # Should not raise, but log warning
        await shutdown_disk_io()

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, mock_config):
        """Test that shutdown_disk_io() is idempotent."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Reset singleton
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Start disk I/O
        disk_io = await init_disk_io()
        assert disk_io is not None

        # First shutdown
        await shutdown_disk_io()
        assert disk_io._running is False  # noqa: SLF001

        # Second shutdown (should be no-op)
        await shutdown_disk_io()
        assert disk_io._running is False  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_background_tasks_stopped(self, mock_config):
        """Test that background tasks are stopped after shutdown."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Reset singleton
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Start disk I/O
        disk_io = await init_disk_io()
        assert disk_io is not None
        assert disk_io._write_batcher_task is not None

        # Shutdown
        await shutdown_disk_io()

        # Tasks should be cancelled
        assert disk_io._write_batcher_task.cancelled() or disk_io._write_batcher_task.done()


class TestDiskIOLifecycle:
    """Integration tests for full disk I/O lifecycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_config):
        """Test full lifecycle: init -> use -> shutdown."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Ensure clean state
        await shutdown_disk_io()
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # Init
        disk_io = await init_disk_io()
        assert disk_io is not None
        assert disk_io._running is True  # noqa: SLF001

        # Use (verify it's accessible via get_disk_io_manager)
        manager = get_disk_io_manager()
        assert manager is disk_io
        assert manager._running is True  # noqa: SLF001

        # Shutdown
        await shutdown_disk_io()
        assert disk_io._running is False  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_multiple_init_shutdown_cycles(self, mock_config):
        """Test multiple init/shutdown cycles."""
        import ccbt.storage.disk_io_init as disk_io_module

        # Ensure clean state
        await shutdown_disk_io()
        disk_io_module._GLOBAL_DISK_IO_MANAGER = None

        # First cycle
        disk_io1 = await init_disk_io()
        assert disk_io1 is not None
        assert disk_io1._running is True  # noqa: SLF001
        await shutdown_disk_io()
        assert disk_io1._running is False  # noqa: SLF001

        # Second cycle
        disk_io2 = await init_disk_io()
        assert disk_io2 is not None
        # Should be same singleton instance
        assert disk_io2 is disk_io1
        assert disk_io2._running is True  # noqa: SLF001
        await shutdown_disk_io()
        assert disk_io2._running is False  # noqa: SLF001


@pytest.fixture
def mock_config(monkeypatch):
    """Mock config for disk I/O tests."""
    from unittest.mock import Mock
    import ccbt.storage.disk_io_init as disk_io_module

    # Reset disk I/O singleton before each test
    disk_io_module._GLOBAL_DISK_IO_MANAGER = None

    mock_config = Mock()
    mock_disk = Mock()
    mock_disk.disk_workers = 2
    mock_disk.disk_queue_size = 200
    mock_disk.cache_size_mb = 256
    mock_config.disk = mock_disk

    from ccbt import config as config_module

    monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

    return mock_config

