"""Pytest configuration and shared fixtures for ccBitTorrent tests."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Any

import pytest


def pytest_configure(config):
    """Register all project markers to avoid warnings when ini isn't loaded."""
    markers = [
        ("asyncio", "marks tests as async (deselect with '-m \"not asyncio\"')"),
        ("slow", "marks tests as slow (deselect with '-m \"not slow\"')"),
        ("timeout", "marks tests with timeout requirements"),
        ("integration", "marks tests as integration tests"),
        ("unit", "marks tests as unit tests"),
        ("core", "marks tests as core functionality tests"),
        ("peer", "marks tests as peer protocol tests"),
        ("piece", "marks tests as piece management tests"),
        ("tracker", "marks tests as tracker tests"),
        ("network", "marks tests as network optimization tests"),
        ("metadata", "marks tests as metadata exchange tests"),
        ("disk", "marks tests as disk I/O tests"),
        ("file", "marks tests as file assembly tests"),
        ("storage", "marks tests as storage/buffer tests"),
        ("session", "marks tests as session management tests"),
        ("resilience", "marks tests as resilience pattern tests"),
        ("connection", "marks tests as connection pool tests"),
        ("checkpoint", "marks tests as checkpoint tests"),
        ("cli", "marks tests as CLI tests"),
        ("extensions", "marks tests as extension tests"),
        ("ml", "marks tests as machine learning tests"),
        ("monitoring", "marks tests as monitoring tests"),
        ("observability", "marks tests as observability tests"),
        ("protocols", "marks tests as protocol tests"),
        ("security", "marks tests as security tests"),
        ("performance", "marks tests as performance/benchmark tests"),
        ("benchmark", "marks tests as benchmark tests (pytest-benchmark)"),
        ("chaos", "marks tests as chaos tests"),
        ("property", "marks tests as property-based tests"),
        ("queue", "marks tests as queue management tests"),
        ("compatibility", "marks tests as compatibility/live tests (run in CI only)"),
        ("consensus", "marks tests as consensus mechanism tests"),
    ]
    for name, desc in markers:
        config.addinivalue_line("markers", f"{name}: {desc}")


@pytest.fixture(autouse=True)
def _set_ccbt_test_mode_env(monkeypatch):
    """Ensure test mode is enabled so config resets don't touch repo files.

    The CLI `config reset` command includes safeguards that respect
    `CCBT_TEST_MODE`. Setting it here prevents accidental writes to
    project-local `ccbt.toml` during tests.
    """
    monkeypatch.setenv("CCBT_TEST_MODE", "1")


@pytest.fixture(autouse=True)
def cleanup_logging():
    """Clean up logging handlers after each test to prevent closed file errors."""
    yield
    # Clean up all handlers to prevent "I/O operation on closed file" errors
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    # Also clean up root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)


@pytest.fixture(autouse=True)
def cleanup_async_resources():
    """Clean up async resources after each test to prevent event loop issues.

    Implemented as a sync fixture to avoid PytestRemovedIn9Warning; it performs
    best-effort cleanup only when an event loop is available and not running.
    """
    yield

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop available (common for pure sync tests)
        return

    # Check if loop is closed or running before attempting cleanup
    try:
        if loop.is_closed():
            # Loop already closed by pytest-asyncio, skip cleanup
            return
        if loop.is_running():
            # When a loop is running (async tests), pytest-asyncio manages teardown.
            # Avoid interfering with the running loop here.
            return
    except RuntimeError:
        # Loop might be closed or in invalid state, skip cleanup
        return

    async def _cleanup() -> None:
        try:
            current_task = asyncio.current_task()
            all_tasks = [t for t in asyncio.all_tasks() if t is not current_task]
            for t in all_tasks:
                if not t.done():
                    t.cancel()
            if all_tasks:
                await asyncio.gather(*all_tasks, return_exceptions=True)
            await asyncio.sleep(0)
        except RuntimeError:
            # Loop may have been closed during cleanup, ignore
            pass

    try:
        loop.run_until_complete(_cleanup())
    except RuntimeError:
        # Loop closed before cleanup could complete, ignore
        pass

    # Clean up network optimizer threads to prevent timeouts
    try:
        from ccbt.utils.network_optimizer import reset_network_optimizer

        reset_network_optimizer()
    except Exception:
        # Best effort cleanup - ignore errors
        pass


@pytest.fixture
def event_loop():
    """Create a new event loop for each test to ensure isolation."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def cleanup_singleton_resources():
    """Clean up singleton resources (NetworkOptimizer, MetricsCollector) after each test.

    This fixture ensures that background threads started by singletons are properly
    stopped between tests to prevent timeouts and resource leaks.

    Note: This fixture runs after each test. If tests need to avoid cleanup,
    they can use their own fixtures that manage the singleton lifecycle.
    """
    yield

    # Cleanup after test - only reset if singletons exist and have active threads
    try:
        import time
        from ccbt.monitoring import _GLOBAL_METRICS_COLLECTOR, reset_metrics_collector
        from ccbt.utils.network_optimizer import (
            _network_optimizer,
            reset_network_optimizer,
        )

        # Only reset NetworkOptimizer if it exists and has active cleanup thread
        if _network_optimizer is not None:
            pool = _network_optimizer.connection_pool
            if pool is not None and pool._cleanup_task is not None:
                # Check if thread is alive
                if pool._cleanup_task.is_alive():
                    # Call stop to properly shutdown the thread
                    try:
                        pool.stop()
                        # Give thread a moment to respond to shutdown signal
                        time.sleep(0.1)
                    except Exception:
                        # If stop fails, try reset anyway
                        pass
                # Always reset to clear the singleton
                reset_network_optimizer()

        # Always reset MetricsCollector if it exists (running or not)
        # This ensures clean state between tests to prevent state pollution
        if _GLOBAL_METRICS_COLLECTOR is not None:
            # Try to stop if running (async, but best effort)
            if _GLOBAL_METRICS_COLLECTOR.running:
                try:
                    import asyncio
                    # Try to get existing loop, create new one if needed
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_closed():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                    except RuntimeError:
                        # No event loop, create new one
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    if not loop.is_running():
                        try:
                            loop.run_until_complete(_GLOBAL_METRICS_COLLECTOR.stop())
                            # Give HTTP server time to fully shut down and release port
                            # This prevents port conflicts in subsequent tests
                            if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server") and _GLOBAL_METRICS_COLLECTOR._http_server is not None:
                                # Server might still be shutting down, wait a bit
                                time.sleep(0.2)
                        except (RuntimeError, Exception):
                            # If stop fails, try to force shutdown HTTP server
                            try:
                                if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server") and _GLOBAL_METRICS_COLLECTOR._http_server is not None:
                                    _GLOBAL_METRICS_COLLECTOR._http_server.shutdown()
                                    if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server_thread") and _GLOBAL_METRICS_COLLECTOR._http_server_thread is not None:
                                        _GLOBAL_METRICS_COLLECTOR._http_server_thread.join(timeout=1.0)
                                    _GLOBAL_METRICS_COLLECTOR._http_server = None
                                    _GLOBAL_METRICS_COLLECTOR._http_server_thread = None
                            except Exception:
                                pass
                            # Mark as not running and continue
                            _GLOBAL_METRICS_COLLECTOR.running = False
                    else:
                        # Loop is running, can't use run_until_complete
                        # Try to force shutdown HTTP server directly
                        try:
                            if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server") and _GLOBAL_METRICS_COLLECTOR._http_server is not None:
                                _GLOBAL_METRICS_COLLECTOR._http_server.shutdown()
                                if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server_thread") and _GLOBAL_METRICS_COLLECTOR._http_server_thread is not None:
                                    _GLOBAL_METRICS_COLLECTOR._http_server_thread.join(timeout=1.0)
                                _GLOBAL_METRICS_COLLECTOR._http_server = None
                                _GLOBAL_METRICS_COLLECTOR._http_server_thread = None
                        except Exception:
                            pass
                        # Mark as not running
                        _GLOBAL_METRICS_COLLECTOR.running = False
                except (RuntimeError, Exception):
                    # No event loop or other issue, try to force shutdown HTTP server
                    try:
                        if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server") and _GLOBAL_METRICS_COLLECTOR._http_server is not None:
                            _GLOBAL_METRICS_COLLECTOR._http_server.shutdown()
                            if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server_thread") and _GLOBAL_METRICS_COLLECTOR._http_server_thread is not None:
                                _GLOBAL_METRICS_COLLECTOR._http_server_thread.join(timeout=1.0)
                            _GLOBAL_METRICS_COLLECTOR._http_server = None
                            _GLOBAL_METRICS_COLLECTOR._http_server_thread = None
                    except Exception:
                        pass
                    # Mark as not running
                    _GLOBAL_METRICS_COLLECTOR.running = False
            else:
                # Not running, but might still have HTTP server from previous test
                # Force cleanup of any lingering HTTP server
                try:
                    if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server") and _GLOBAL_METRICS_COLLECTOR._http_server is not None:
                        _GLOBAL_METRICS_COLLECTOR._http_server.shutdown()
                        if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server_thread") and _GLOBAL_METRICS_COLLECTOR._http_server_thread is not None:
                            _GLOBAL_METRICS_COLLECTOR._http_server_thread.join(timeout=1.0)
                        _GLOBAL_METRICS_COLLECTOR._http_server = None
                        _GLOBAL_METRICS_COLLECTOR._http_server_thread = None
                except Exception:
                    pass
            # Always reset the singleton to None to prevent state pollution
            import ccbt.monitoring as monitoring_module
            monitoring_module._GLOBAL_METRICS_COLLECTOR = None
        
        # Also reset AlertManager singleton to prevent state pollution
        try:
            from ccbt.monitoring import _GLOBAL_ALERT_MANAGER
            import ccbt.monitoring as monitoring_module
            if _GLOBAL_ALERT_MANAGER is not None:
                # AlertManager doesn't have async cleanup, just reset
                monitoring_module._GLOBAL_ALERT_MANAGER = None
        except Exception:
            # Best-effort cleanup
            pass
        
        # Reset UTPSocketManager singleton to prevent state pollution in uTP tests
        try:
            from ccbt.transport.utp_socket import UTPSocketManager
            # Stop and reset the singleton if it exists
            if UTPSocketManager._instance is not None:
                instance = UTPSocketManager._instance
                # Try to stop if initialized
                if instance._initialized and instance.transport is not None:
                    try:
                        import asyncio
                        # Try to get existing loop, create new one if needed
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_closed():
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                        except RuntimeError:
                            # No event loop, create new one
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        if not loop.is_running():
                            try:
                                # Stop the socket manager
                                loop.run_until_complete(instance.stop())
                            except (RuntimeError, Exception):
                                # If stop fails, just mark as not initialized
                                instance._initialized = False
                                if instance.transport:
                                    try:
                                        instance.transport.close()
                                    except Exception:
                                        pass
                                    instance.transport = None
                    except (RuntimeError, Exception):
                        # Can't stop cleanly, just mark as not initialized
                        instance._initialized = False
                        if instance.transport:
                            try:
                                instance.transport.close()
                            except Exception:
                                pass
                            instance.transport = None
                # Always reset the singleton
                UTPSocketManager._instance = None
        except Exception:
            # Best-effort cleanup
            pass
        
        # Reset PluginManager singleton to prevent state pollution
        try:
            from ccbt.plugins.base import _plugin_manager
            import ccbt.plugins.base as plugins_module
            if _plugin_manager is not None:
                # PluginManager doesn't have async cleanup, just reset
                plugins_module._plugin_manager = None
        except Exception:
            # Best-effort cleanup
            pass
        
        # Reset DiskIOManager singleton to prevent state pollution
        try:
            from ccbt.storage.disk_io_init import _GLOBAL_DISK_IO_MANAGER
            import ccbt.storage.disk_io_init as disk_io_module
            if _GLOBAL_DISK_IO_MANAGER is not None:
                # Try to stop if running (async, but best effort)
                if _GLOBAL_DISK_IO_MANAGER._running:  # noqa: SLF001
                    try:
                        import asyncio
                        # Try to get existing loop, create new one if needed
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_closed():
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                        except RuntimeError:
                            # No event loop, create new one
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        if not loop.is_running():
                            try:
                                loop.run_until_complete(_GLOBAL_DISK_IO_MANAGER.stop())
                            except (RuntimeError, Exception):
                                # If stop fails, mark as not running
                                _GLOBAL_DISK_IO_MANAGER._running = False  # noqa: SLF001
                        else:
                            # Loop is running, can't use run_until_complete
                            _GLOBAL_DISK_IO_MANAGER._running = False  # noqa: SLF001
                    except (RuntimeError, Exception):
                        # No event loop or other issue, just mark as not running
                        _GLOBAL_DISK_IO_MANAGER._running = False  # noqa: SLF001
                # Always reset the singleton to None to prevent state pollution
                disk_io_module._GLOBAL_DISK_IO_MANAGER = None
        except Exception:
            # Best-effort cleanup
            pass
    except Exception:
        # Best-effort cleanup - don't fail tests if cleanup fails
        pass


@pytest.fixture(autouse=True)
def seed_rng() -> None:
    """Deterministically seed RNGs to make tests reproducible."""
    seed = int(os.environ.get("CCBT_TEST_SEED", "123456"))
    random.seed(seed)
    try:
        import numpy as _np  # type: ignore

        _np.random.seed(seed)
    except Exception:
        # Numpy is optional; ignore if unavailable
        pass


@pytest.fixture(autouse=True)
def reset_config_manager_encryption_cache():
    """Reset ConfigManager encryption key cache between tests for isolation.
    
    This ensures that tests that modify encryption-related state don't
    affect other tests. The global config manager is preserved, but
    the cached encryption key is cleared.
    """
    yield
    
    # Clear encryption key cache after each test
    try:
        from ccbt.config import config as config_module
        if config_module._config_manager is not None:
            config_module._config_manager._encryption_key = None
    except Exception:
        # Best-effort cleanup - don't fail tests if cleanup fails
        pass


@pytest.fixture
def tmp_storage(tmp_path):
    """Provide a temporary storage directory for file/disk tests."""
    return tmp_path


@pytest.fixture
def mock_dht_client():
    """Create a properly configured mock DHT client for tests.
    
    This fixture provides a mock AsyncDHTClient with all required methods
    to prevent AttributeError and timeout issues in tests.
    """
    from unittest.mock import AsyncMock, MagicMock
    
    mock_dht = MagicMock()
    mock_dht.start = AsyncMock()
    mock_dht.stop = AsyncMock()
    mock_dht.wait_for_bootstrap = AsyncMock(return_value=True)
    mock_dht.routing_table = MagicMock()
    mock_dht.routing_table.nodes = {}
    mock_dht.get_peers = AsyncMock(return_value=[])
    mock_dht.add_peer_callback = MagicMock()
    return mock_dht


def create_test_torrent_dict(
    name: str = "test_torrent",
    info_hash: bytes = b"\x00" * 20,
    announce: str = "http://tracker.example.com/announce",
    file_length: int = 1024,
    piece_length: int = 16384,
    num_pieces: int = 1,
) -> dict[str, Any]:
    """Create properly formatted torrent dictionary for tests.

    This helper creates torrent data that matches the expected format
    for both TorrentInfo models and dictionary-based components.

    Args:
        name: Torrent name
        info_hash: 20-byte info hash
        announce: Tracker announce URL
        file_length: Size of the test file in bytes
        piece_length: Size of each piece in bytes
        num_pieces: Number of pieces

    Returns:
        Properly formatted torrent dictionary with pieces_info and file_info
    """
    piece_hashes = [b"\x00" * 20 for _ in range(num_pieces)]

    return {
        "name": name,
        "info_hash": info_hash,
        "announce": announce,
        "files": [
            {
                "name": f"{name}.txt",
                "length": file_length,
                "path": [f"{name}.txt"],
            },
        ],
        "total_length": file_length,
        "piece_length": piece_length,
        "pieces": piece_hashes,
        "num_pieces": num_pieces,
        # Add pieces_info for compatibility with piece managers
        "pieces_info": {
            "piece_length": piece_length,
            "num_pieces": num_pieces,
            "piece_hashes": piece_hashes,
        },
        # Add file_info for compatibility with session management
        "file_info": {
            "type": "single",
            "name": name,
            "total_length": file_length,
            "files": [
                {
                    "name": f"{name}.txt",
                    "length": file_length,
                    "path": [f"{name}.txt"],
                },
            ],
        },
    }
