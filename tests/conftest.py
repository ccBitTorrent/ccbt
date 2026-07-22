"""Pytest configuration and shared fixtures for ccBitTorrent tests."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

import pytest
import pytest_asyncio


def make_torrent_data(
    *,
    num_pieces: int = 100,
    info_hash: Optional[bytes] = None,
) -> dict[str, Any]:
    """Build a fresh torrent dict for tests (avoids accidental cross-test mutation)."""
    ih = info_hash if info_hash is not None else os.urandom(20)
    return {
        "info_hash": ih,
        "piece_length": 16384,
        "num_pieces": num_pieces,
        "pieces_info": {"num_pieces": num_pieces},
    }


# Import network mock fixtures to make them available to all tests
# This ensures fixtures from tests/fixtures/network_mocks.py are discoverable
pytest_plugins = ["tests.fixtures.network_mocks", "tests.fixtures.config_mocks"]

# Import timeout hooks for per-test timeout management
# This applies timeout markers based on test categories
try:
    from tests.conftest_timeout import pytest_collection_modifyitems
except ImportError:
    # If timeout hooks module doesn't exist, continue without it
    pass

# #region agent log
# Debug logging helper
_DEBUG_LOG_PATH = Path(
    os.environ.get(
        "CCBT_TEST_DEBUG_LOG",
        str(Path(tempfile.gettempdir()) / "ccbt-test-debug.log"),
    )
)
def _debug_log(hypothesis_id: str, location: str, message: str, data: Optional[dict] = None):
    """Write debug log entry in NDJSON format."""
    try:
        # Ensure directory exists
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000)
        }
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()  # Ensure immediate write
            os.fsync(f.fileno())  # Force OS-level write
    except Exception as e:
        # Log to stderr so we can see if logging fails
        import sys
        print(f"DEBUG LOG ERROR: {e}", file=sys.stderr, flush=True)
        # Best effort - don't break tests

# Test log at module import time
try:
    _debug_log("E", "conftest.py:module", "conftest.py module imported", {})
except Exception:
    pass
# #endregion


def _ensure_unittest_patch_targets() -> None:
    """Register submodules on parent packages for unittest.patch on all platforms."""
    config_submodules = (
        "config",
        "config_backup",
        "config_capabilities",
        "config_conditional",
        "config_diff",
    )
    peer_submodules = (
        "async_peer_connection",
        "ssl_peer",
        "utp_peer",
        "peer",
        "connection_pool",
    )
    for submodule in config_submodules:
        module = importlib.import_module(f"ccbt.config.{submodule}")
        pkg = importlib.import_module("ccbt.config")
        if getattr(pkg, submodule, None) is not module:
            setattr(pkg, submodule, module)
    for submodule in peer_submodules:
        module = importlib.import_module(f"ccbt.peer.{submodule}")
        pkg = importlib.import_module("ccbt.peer")
        if getattr(pkg, submodule, None) is not module:
            setattr(pkg, submodule, module)
    cli_main = importlib.import_module("ccbt.cli.main")
    if sys.modules.get("ccbt.cli.main") is not cli_main:
        sys.modules["ccbt.cli.main"] = cli_main


def pytest_configure(config):
    """Register all project markers to avoid warnings when ini isn't loaded."""
    _ensure_unittest_patch_targets()
    # #region agent log
    _debug_log("E", "conftest.py:pytest_configure", "Pytest configuration started", {})
    # #endregion
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
        ("transport", "marks tests as transport layer tests"),
        ("discovery", "marks tests as discovery tests"),
        ("config", "marks tests as configuration tests"),
        ("plugins", "marks tests as plugins tests"),
        ("interface", "marks tests as interface tests"),
        ("daemon", "marks tests as daemon tests"),
        ("executor", "marks tests as executor tests"),
        ("models", "marks tests as model tests"),
        ("services", "marks tests as services tests"),
        ("nat", "marks tests as NAT tests"),
        ("proxy", "marks tests as proxy tests"),
    ]
    for name, desc in markers:
        config.addinivalue_line("markers", f"{name}: {desc}")
    # #region agent log
    _debug_log("E", "conftest.py:pytest_configure", "Pytest configuration completed", {})
    # #endregion


def pytest_runtest_setup(item):
    """Hook called before each test setup."""
    # #region agent log
    _debug_log("E", "conftest.py:pytest_runtest_setup", "Test setup starting", {"test_name": str(item.nodeid)})
    # #endregion


def pytest_runtest_logfinish(nodeid, location):
    """Hook called when test logging is finished."""
    # #region agent log
    _debug_log("E", "conftest.py:pytest_runtest_logfinish", "Test logging finished", {"test_name": str(nodeid), "location": str(location)})
    # #endregion


def pytest_runtest_call(item):
    """Hook called when test is about to be executed."""
    # #region agent log
    _debug_log("E", "conftest.py:pytest_runtest_call", "Test call starting", {"test_name": str(item.nodeid)})
    # #endregion


def pytest_runtest_makereport(item, call):
    """Hook called to create test report."""
    # #region agent log
    outcome = "passed"
    if call.excinfo:
        outcome = "failed" if call.excinfo.typename != "Skipped" else "skipped"
    _debug_log("E", "conftest.py:pytest_runtest_makereport", "Test report being created", {"test_name": str(item.nodeid), "when": call.when, "outcome": outcome, "has_excinfo": call.excinfo is not None})
    # #endregion


def pytest_runtest_teardown(item):
    """Hook called after each test teardown."""
    # #region agent log
    _debug_log("E", "conftest.py:pytest_runtest_teardown", "Test teardown starting", {"test_name": str(item.nodeid)})
    # #endregion


def pytest_collection_modifyitems(config, items):
    """Hook called after test collection."""
    # #region agent log
    _debug_log("E", "conftest.py:pytest_collection_modifyitems", "Test collection completed", {"test_count": len(items)})
    # #endregion


@pytest.fixture(autouse=True, scope="function")
def _set_ccbt_test_mode_env(monkeypatch):
    """Ensure test mode is enabled so config resets don't touch repo files.

    The CLI `config reset` command includes safeguards that respect
    `CCBT_TEST_MODE`. Setting it here prevents accidental writes to
    project-local `ccbt.toml` during tests.
    """
    monkeypatch.setenv("CCBT_TEST_MODE", "1")


@pytest.fixture(autouse=True, scope="function")
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


@pytest.fixture(autouse=True, scope="function")
def cleanup_async_resources():
    """Clean up async resources after each test to prevent event loop issues.

    Implemented as a sync fixture to avoid PytestRemovedIn9Warning; it performs
    best-effort cleanup only when an event loop is available and not running.
    """
    yield

    # #region agent log
    _debug_log("B", "conftest.py:cleanup_async_resources", "Fixture entry", {"test_name": os.environ.get("PYTEST_CURRENT_TEST", "unknown")})
    # #endregion

    try:
        loop = asyncio.get_event_loop()
        # #region agent log
        _debug_log("B", "conftest.py:cleanup_async_resources", "Got event loop", {"loop_closed": loop.is_closed() if hasattr(loop, "is_closed") else "unknown", "loop_running": loop.is_running() if hasattr(loop, "is_running") else "unknown", "loop_type": type(loop).__name__})
        # #endregion
    except RuntimeError as e:
        # #region agent log
        _debug_log("B", "conftest.py:cleanup_async_resources", "No event loop available", {"error": str(e)})
        # #endregion
        # No event loop available (common for pure sync tests)
        return

    # Check if loop is closed or running before attempting cleanup
    try:
        if loop.is_closed():
            # #region agent log
            _debug_log("B", "conftest.py:cleanup_async_resources", "Loop is closed, skipping cleanup", {})
            # #endregion
            # Loop already closed by pytest-asyncio, skip cleanup
            return
        if loop.is_running():
            # #region agent log
            _debug_log("B", "conftest.py:cleanup_async_resources", "Loop is running, skipping cleanup", {})
            # #endregion
            # When a loop is running (async tests), pytest-asyncio manages teardown.
            # Avoid interfering with the running loop here.
            return
    except RuntimeError:
        # #region agent log
        _debug_log("B", "conftest.py:cleanup_async_resources", "RuntimeError checking loop state", {})
        # #endregion
        # Loop might be closed or in invalid state, skip cleanup
        return

    async def _cleanup() -> None:
        try:
            # #region agent log
            _debug_log("B", "conftest.py:_cleanup", "Starting async cleanup", {})
            # #endregion
            current_task = asyncio.current_task()
            all_tasks = [t for t in asyncio.all_tasks() if t is not current_task]
            # #region agent log
            _debug_log("B", "conftest.py:_cleanup", "Found tasks to cancel", {"task_count": len(all_tasks)})
            # #endregion
            for t in all_tasks:
                if not t.done():
                    t.cancel()
            if all_tasks:
                # #region agent log
                _debug_log("B", "conftest.py:_cleanup", "Calling asyncio.gather", {"task_count": len(all_tasks)})
                # #endregion
                await asyncio.gather(*all_tasks, return_exceptions=True)
                # #region agent log
                _debug_log("B", "conftest.py:_cleanup", "asyncio.gather completed", {})
                # #endregion
            await asyncio.sleep(0)
        except RuntimeError as e:
            # #region agent log
            _debug_log("B", "conftest.py:_cleanup", "RuntimeError during cleanup", {"error": str(e)})
            # #endregion
            # Loop may have been closed during cleanup, ignore

    try:
        # #region agent log
        _debug_log("B", "conftest.py:cleanup_async_resources", "Calling run_until_complete", {})
        # #endregion
        loop.run_until_complete(_cleanup())
        # #region agent log
        _debug_log("B", "conftest.py:cleanup_async_resources", "run_until_complete completed", {})
        # #endregion
    except RuntimeError as e:
        # #region agent log
        _debug_log("B", "conftest.py:cleanup_async_resources", "RuntimeError in run_until_complete", {"error": str(e)})
        # #endregion
        # Loop closed before cleanup could complete, ignore

    # #region agent log
    # Check event loop state after cleanup
    try:
        loop_after = asyncio.get_event_loop()
        _debug_log("B", "conftest.py:cleanup_async_resources", "Event loop state after cleanup", {"loop_closed": loop_after.is_closed() if hasattr(loop_after, "is_closed") else "unknown", "loop_running": loop_after.is_running() if hasattr(loop_after, "is_running") else "unknown", "loop_type": type(loop_after).__name__})
    except RuntimeError:
        _debug_log("B", "conftest.py:cleanup_async_resources", "No event loop after cleanup", {})
    # #endregion

    # Clean up network optimizer threads to prevent timeouts
    try:
        from ccbt.utils.network_optimizer import reset_network_optimizer

        reset_network_optimizer()
    except Exception as e:
        # #region agent log
        _debug_log("B", "conftest.py:cleanup_async_resources", "Exception resetting network optimizer", {"error": str(e)})
        # #endregion
        # Best effort cleanup - ignore errors

    # #region agent log
    _debug_log("B", "conftest.py:cleanup_async_resources", "Fixture exit", {})
    # #endregion


# Removed custom event_loop fixture - pytest-asyncio with asyncio_mode=auto handles event loops automatically
# The custom fixture was causing conflicts with pytest-asyncio's automatic event loop management,
# leading to hangs where pytest_runtest_teardown was never called after test completion.


@pytest.fixture(autouse=True, scope="function")
def cleanup_singleton_resources():
    """Clean up singleton resources (NetworkOptimizer, MetricsCollector) after each test.

    This fixture ensures that background threads started by singletons are properly
    stopped between tests to prevent timeouts and resource leaks.

    Note: This fixture runs after each test. If tests need to avoid cleanup,
    they can use their own fixtures that manage the singleton lifecycle.
    """
    yield

    # #region agent log
    _debug_log("A", "conftest.py:cleanup_singleton_resources", "Fixture entry", {"test_name": os.environ.get("PYTEST_CURRENT_TEST", "unknown")})
    # #endregion

    # CRITICAL: Reset global config manager FIRST to ensure clean state
    # This prevents config modifications in one test from affecting others
    try:
        from ccbt.config.config import get_config, reset_config
        reset_config()
        # Explicitly reset scrape-related config to prevent state pollution
        config = get_config()
        if config and hasattr(config, "discovery"):
            config.discovery.tracker_auto_scrape = False
    except Exception:
        # If reset fails, continue - not critical for test execution
        pass

    # Cleanup after test - only reset if singletons exist and have active threads
    try:
        import time

        from ccbt.monitoring import _GLOBAL_METRICS_COLLECTOR
        from ccbt.utils.network_optimizer import (
            _network_optimizer,
            reset_network_optimizer,
        )

        # #region agent log
        _debug_log("A", "conftest.py:cleanup_singleton_resources", "Checking NetworkOptimizer", {"exists": _network_optimizer is not None})
        # #endregion

        # Only reset NetworkOptimizer if it exists and has active cleanup thread
        if _network_optimizer is not None:
            pool = _network_optimizer.connection_pool
            # Note: Check for connection_pool existence before accessing
            if pool is not None and pool._cleanup_task is not None:
                # #region agent log
                _debug_log("A", "conftest.py:cleanup_singleton_resources", "NetworkOptimizer has cleanup task", {"thread_alive": pool._cleanup_task.is_alive()})
                # #endregion
                # Check if thread is alive
                if pool._cleanup_task.is_alive():
                    # #region agent log
                    _debug_log("A", "conftest.py:cleanup_singleton_resources", "Calling pool.stop()", {})
                    # #endregion
                    # Call stop to properly shutdown the thread with timeout protection
                    try:
                        # Note: Add timeout wrapper to prevent hanging
                        import threading
                        stop_completed = threading.Event()
                        def stop_with_timeout():
                            try:
                                pool.stop()
                            finally:
                                stop_completed.set()

                        stop_thread = threading.Thread(target=stop_with_timeout, daemon=True)
                        stop_thread.start()
                        stop_thread.join(timeout=2.0)  # 2 second timeout

                        if not stop_completed.is_set():
                            # Timeout occurred, force cleanup
                            pool._shutdown_event.set()
                            pool._cleanup_task = None

                        # #region agent log
                        _debug_log("A", "conftest.py:cleanup_singleton_resources", "pool.stop() completed, sleeping 0.5s", {})
                        # #endregion
                        # Note: Increase sleep from 0.1s to 0.5s to ensure cleanup completes
                        time.sleep(0.5)
                        # #region agent log
                        _debug_log("A", "conftest.py:cleanup_singleton_resources", "Sleep completed", {})
                        # #endregion
                    except Exception as e:
                        # #region agent log
                        _debug_log("A", "conftest.py:cleanup_singleton_resources", "Exception in pool.stop()", {"error": str(e)})
                        # #endregion
                        # If stop fails, try reset anyway
                # Always reset to clear the singleton
                # #region agent log
                _debug_log("A", "conftest.py:cleanup_singleton_resources", "Resetting NetworkOptimizer", {})
                # #endregion
                reset_network_optimizer()
                # Note: Explicitly clear pool reference
                pool = None
                # #region agent log
                _debug_log("A", "conftest.py:cleanup_singleton_resources", "NetworkOptimizer reset completed", {})
                # #endregion

        # Note: Force cleanup all ConnectionPool instances (not just singleton)
        # This ensures any ConnectionPool instances created outside the singleton are also cleaned up
        try:
            from ccbt.utils.network_optimizer import force_cleanup_all_connection_pools
            force_cleanup_all_connection_pools()
        except Exception:
            # Best effort - if import or cleanup fails, continue
            pass

        # Always reset MetricsCollector if it exists (running or not)
        # This ensures clean state between tests to prevent state pollution
        if _GLOBAL_METRICS_COLLECTOR is not None:
            # #region agent log
            _debug_log("C", "conftest.py:cleanup_singleton_resources", "Checking MetricsCollector", {"running": _GLOBAL_METRICS_COLLECTOR.running, "has_http_server": hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server") and _GLOBAL_METRICS_COLLECTOR._http_server is not None})
            # #endregion
            # Try to stop if running (async, but best effort)
            if _GLOBAL_METRICS_COLLECTOR.running:
                try:
                    # Use a short-lived loop only when no loop is currently running.
                    # This avoids run_until_complete() against pytest-managed loops.
                    try:
                        asyncio.get_running_loop()
                        has_running_loop = True
                    except RuntimeError:
                        has_running_loop = False

                    if not has_running_loop:
                        try:
                            # #region agent log
                            _debug_log("C", "conftest.py:cleanup_singleton_resources", "Calling MetricsCollector.stop()", {})
                            # #endregion
                            asyncio.run(
                                asyncio.wait_for(_GLOBAL_METRICS_COLLECTOR.stop(), timeout=1.5)
                            )
                            # #region agent log
                            _debug_log("C", "conftest.py:cleanup_singleton_resources", "MetricsCollector.stop() completed", {})
                            # #endregion
                            # Give HTTP server time to fully shut down and release port
                            # This prevents port conflicts in subsequent tests
                            if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server") and _GLOBAL_METRICS_COLLECTOR._http_server is not None:
                                # #region agent log
                                _debug_log("C", "conftest.py:cleanup_singleton_resources", "HTTP server exists, sleeping 0.2s", {})
                                # #endregion
                                # Server might still be shutting down, wait a bit
                                time.sleep(0.2)
                                # #region agent log
                                _debug_log("C", "conftest.py:cleanup_singleton_resources", "Sleep 0.2s completed", {})
                                # #endregion
                        except (RuntimeError, Exception):
                            # If stop fails, try to force shutdown HTTP server
                            try:
                                if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server") and _GLOBAL_METRICS_COLLECTOR._http_server is not None:
                                    _GLOBAL_METRICS_COLLECTOR._http_server.shutdown()
                                    if hasattr(_GLOBAL_METRICS_COLLECTOR, "_http_server_thread") and _GLOBAL_METRICS_COLLECTOR._http_server_thread is not None:
                                        # #region agent log
                                        _debug_log("C", "conftest.py:cleanup_singleton_resources", "Joining HTTP server thread", {"timeout": 1.0})
                                        # #endregion
                                        _GLOBAL_METRICS_COLLECTOR._http_server_thread.join(timeout=1.0)
                                        # #region agent log
                                        _debug_log("C", "conftest.py:cleanup_singleton_resources", "HTTP server thread join completed", {"thread_alive": _GLOBAL_METRICS_COLLECTOR._http_server_thread.is_alive() if hasattr(_GLOBAL_METRICS_COLLECTOR._http_server_thread, "is_alive") else "unknown"})
                                        # #endregion
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
                                    # #region agent log
                                    _debug_log("C", "conftest.py:cleanup_singleton_resources", "Joining HTTP server thread (loop running path)", {"timeout": 1.0})
                                    # #endregion
                                    _GLOBAL_METRICS_COLLECTOR._http_server_thread.join(timeout=1.0)
                                    # #region agent log
                                    _debug_log("C", "conftest.py:cleanup_singleton_resources", "HTTP server thread join completed (loop running path)", {})
                                    # #endregion
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
                                # #region agent log
                                _debug_log("C", "conftest.py:cleanup_singleton_resources", "Joining HTTP server thread (exception path)", {"timeout": 1.0})
                                # #endregion
                                _GLOBAL_METRICS_COLLECTOR._http_server_thread.join(timeout=1.0)
                                # #region agent log
                                _debug_log("C", "conftest.py:cleanup_singleton_resources", "HTTP server thread join completed (exception path)", {})
                                # #endregion
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
                            # #region agent log
                            _debug_log("C", "conftest.py:cleanup_singleton_resources", "Joining HTTP server thread (not running path)", {"timeout": 1.0})
                            # #endregion
                            _GLOBAL_METRICS_COLLECTOR._http_server_thread.join(timeout=1.0)
                            # #region agent log
                            _debug_log("C", "conftest.py:cleanup_singleton_resources", "HTTP server thread join completed (not running path)", {})
                            # #endregion
                        _GLOBAL_METRICS_COLLECTOR._http_server = None
                        _GLOBAL_METRICS_COLLECTOR._http_server_thread = None
                except Exception:
                    pass
            # Always reset the singleton to None to prevent state pollution
            import ccbt.monitoring as monitoring_module
            monitoring_module._GLOBAL_METRICS_COLLECTOR = None

        # Also reset AlertManager singleton to prevent state pollution
        try:
            import ccbt.monitoring as monitoring_module
            from ccbt.monitoring import _GLOBAL_ALERT_MANAGER
            if _GLOBAL_ALERT_MANAGER is not None:
                # AlertManager doesn't have async cleanup, just reset
                monitoring_module._GLOBAL_ALERT_MANAGER = None
        except Exception:
            # Best-effort cleanup
            pass

        # UTPSocketManager singleton compatibility path removed.
        # Compatibility managers are now owned by sessions and must be cleaned up there.

        # Reset PluginManager singleton to prevent state pollution
        try:
            import ccbt.plugins.base as plugins_module
            from ccbt.plugins.base import _plugin_manager
            if _plugin_manager is not None:
                # PluginManager doesn't have async cleanup, just reset
                plugins_module._plugin_manager = None
        except Exception:
            # Best-effort cleanup
            pass

        # DiskIOManager is no longer stored as a global singleton.
        # Compatibility instances created via get_disk_io_manager() are session-owned in tests.
    except Exception as e:
        # #region agent log
        _debug_log("A", "conftest.py:cleanup_singleton_resources", "Exception in cleanup_singleton_resources outer try", {"error": str(e), "error_type": type(e).__name__})
        # #endregion
        # Best-effort cleanup - don't fail tests if cleanup fails

    # #region agent log
    _debug_log("A", "conftest.py:cleanup_singleton_resources", "Fixture exit", {})
    # #endregion


@pytest.fixture(autouse=True, scope="function")
def cleanup_network_ports():
    """Clean up network ports after each test to prevent conflicts.
    
    This fixture provides best-effort cleanup by waiting for ports to be released.
    Actual port cleanup happens in component stop() methods.
    
    Wait time is 0.2s by default so integration runs don't appear to hang (2s per
    test was causing 762 tests to take 25+ minutes in teardown alone). Set
    CCBT_TEST_PORT_RELEASE_DELAY=2.0 in CI if "Address already in use" appears.
    
    Also releases ports from port pool manager to prevent pool exhaustion.
    """
    yield

    import time
    delay = float(os.environ.get("CCBT_TEST_PORT_RELEASE_DELAY", "0.2"))
    if delay > 0:
        time.sleep(delay)

    # Release all ports from port pool after each test
    # This ensures the pool doesn't get exhausted over many tests
    try:
        from tests.utils.port_pool import PortPool
        pool = PortPool.get_instance()
        pool.release_all_ports()
    except Exception:
        # If port pool cleanup fails, continue - not critical
        pass


def get_free_port() -> int:
    """Get a free port for testing using port pool manager.
    
    Returns:
        int: A free port number from the port pool
    """
    from tests.utils.port_pool import get_free_port as pool_get_free_port
    return pool_get_free_port()


def find_port_in_use(port: int) -> bool:
    """Check if a port is in use.
    
    Args:
        port: Port number to check
        
    Returns:
        bool: True if port is in use, False otherwise
    """
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return False
    except OSError:
        return True


async def wait_for_port_release(port: int, timeout: float = 2.0) -> bool:
    """Wait for a port to be released.
    
    Args:
        port: Port number to wait for
        timeout: Maximum time to wait in seconds
        
    Returns:
        bool: True if port was released, False if timeout
    """
    import asyncio
    import time
    start = time.time()
    while time.time() - start < timeout:
        if not find_port_in_use(port):
            return True
        await asyncio.sleep(0.1)
    return False


@pytest.fixture(autouse=True, scope="function")
def verify_test_isolation():
    """Verify test isolation after each test.
    
    This fixture performs best-effort checks for:
    - Lingering background threads
    - Open file handles (if psutil available)
    - Port conflicts (basic check)
    
    Warnings are logged but tests are not failed to avoid false positives.
    """
    yield

    # Best-effort verification - don't fail tests on warnings
    import logging
    import sys
    import threading

    logger = logging.getLogger(__name__)
    warnings = []

    # Check for lingering background threads (excluding main thread)
    try:
        active_threads = [t for t in threading.enumerate() if t.is_alive() and t != threading.main_thread()]
        # Filter out known system threads (like pytest's own threads)
        test_threads = [
            t for t in active_threads
            if not t.name.startswith("MainThread")
            and not t.name.startswith("ThreadPoolExecutor")
            and "pytest" not in t.name.lower()
            and "asyncio" not in t.name.lower()
        ]
        if test_threads:
            thread_names = [t.name for t in test_threads]
            warnings.append(f"Lingering threads detected: {thread_names}")
    except Exception:
        pass  # Thread enumeration may fail, ignore

    # Check for open file handles (if psutil available).
    # Skip on Windows: psutil.Process.open_files() is very slow there (~2s per call)
    # and causes integration runs to appear to hang during teardown.
    if sys.platform != "win32":
        try:
            import os as os_module

            import psutil
            process = psutil.Process(os_module.getpid())
            open_files = process.open_files()
            # Filter out known system files and pytest files
            suspicious_files = [
                f.path for f in open_files
                if not any(
                    skip in f.path.lower()
                    for skip in ["/dev/", "/proc/", "pytest", ".pyc", "__pycache__", ".cursor"]
                )
            ]
            if suspicious_files and len(suspicious_files) > 5:  # Allow some files, warn on many
                warnings.append(f"Many open file handles detected: {len(suspicious_files)} files")
        except ImportError:
            # psutil not available, skip file handle check
            pass
        except Exception:
            pass  # File handle check may fail, ignore

    # Log warnings if any found
    if warnings:
        logger.warning(
            "Test isolation warnings (non-critical): %s",
            "; ".join(warnings)
        )


@pytest.fixture(autouse=True, scope="function")
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


@pytest.fixture(autouse=True, scope="function")
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
    mock_dht.bootstrap = AsyncMock()
    mock_dht.wait_for_bootstrap = AsyncMock(return_value=True)
    mock_dht.routing_table = MagicMock()
    mock_dht.routing_table.nodes = {}
    mock_dht.get_peers = AsyncMock(return_value=[])
    mock_dht.add_peer_callback = MagicMock()
    return mock_dht


def create_interactive_cli(session, console=None):
    """Helper function to create InteractiveCLI with proper dependencies.
    
    Args:
        session: Mock or real AsyncSessionManager
        console: Optional Console instance (creates Mock if not provided)
    
    Returns:
        InteractiveCLI instance with proper executor and adapter
    """
    from unittest.mock import Mock

    from rich.console import Console as RichConsole

    from ccbt.cli.interactive import InteractiveCLI
    from ccbt.executor.executor import UnifiedCommandExecutor
    from ccbt.executor.session_adapter import LocalSessionAdapter

    if console is None:
        console = Mock(spec=RichConsole)
        console.print = Mock()
        console.clear = Mock()
        console.print_json = Mock()
        # Note: Rich Progress requires console.get_time method
        import time
        console.get_time = Mock(return_value=time.time)

    adapter = LocalSessionAdapter(session)
    executor = UnifiedCommandExecutor(adapter)
    return InteractiveCLI(executor, adapter, console, session=session)


@pytest.fixture
def mock_config_manager():
    """Fixture to provide a mocked ConfigManager for interactive CLI tests.
    
    This fixture patches ConfigManager at the module level so that when
    commands call ConfigManager(None), they receive the mocked instance
    instead of creating a new one.
    
    Also ensures config state is reset after each test.
    """
    from unittest.mock import MagicMock, Mock, patch

    from ccbt.models import Config

    # Create mock config with proper structure
    mock_config = MagicMock(spec=Config)
    mock_config.model_dump.return_value = {"network": {"port": 6881}}
    # Create disk mock with backup_dir attribute
    mock_disk = Mock()
    mock_disk.backup_dir = "/tmp/backups"
    mock_config.disk = mock_disk
    mock_config.config_file = None

    mock_cm = MagicMock()
    mock_cm.config = mock_config
    mock_cm.config_file = None

    with patch("ccbt.cli.interactive.ConfigManager", return_value=mock_cm):
        yield mock_cm

    # Cleanup: reset config state after each test
    from ccbt.config.config import reset_config
    reset_config()


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


def create_mock_config():
    """Create a default mock configuration for testing.
    
    Returns:
        MagicMock: Mock config object with all required attributes
    """
    from unittest.mock import MagicMock

    from ccbt.models import CheckpointFormat

    config = MagicMock()
    config.discovery = MagicMock()
    config.discovery.tracker_auto_scrape = False
    config.discovery.tracker_scrape_interval = 300.0
    config.discovery.enable_dht = False
    config.nat = MagicMock()
    config.nat.auto_map_ports = False
    config.security = MagicMock()
    config.security.ip_filter = MagicMock()
    config.security.ip_filter.filter_update_interval = 3600.0
    config.queue = MagicMock()
    config.queue.auto_manage_queue = False
    config.disk = MagicMock()
    config.disk.checkpoint_interval = 30.0
    config.disk.resume_save_interval = 30.0
    config.disk.fast_resume_enabled = False
    config.disk.checkpoint_batch_interval = 0
    config.disk.checkpoint_batch_pieces = 0
    config.disk.checkpoint_format = CheckpointFormat.BINARY
    config.disk.checkpoint_enabled = True
    config.limits = MagicMock()
    config.limits.global_down_kib = 0
    config.limits.global_up_kib = 0
    config.network = MagicMock()
    config.network.max_global_peers = 100
    config.network.connection_timeout = 30.0
    return config


@pytest_asyncio.fixture(scope="function")
async def session_manager(tmp_path, request):
    """Create AsyncSessionManager instance for testing with proper cleanup.
    
    This fixture provides a standardized way to create and clean up
    AsyncSessionManager instances across all tests, ensuring proper
    resource cleanup and preventing resource leaks.
    
    Args:
        tmp_path: Pytest fixture providing temporary directory
        request: Pytest request object for accessing other fixtures
    
    Yields:
        AsyncSessionManager instance ready for testing
    
    Example:
        ```python
        async def test_something(session_manager):
            # session_manager is already started and ready
            await session_manager.add_torrent(torrent_data)
            # Cleanup is automatic
        ```
    """
    import asyncio
    from unittest.mock import patch

    from ccbt.session.session import AsyncSessionManager

    # Check if test requested a custom config via fixture parameter
    mock_config = None
    if hasattr(request, "param") and request.param:
        mock_config = request.param
    else:
        # Try to get custom_config or mock_config fixture if it exists
        try:
            mock_config = request.getfixturevalue("custom_config")
        except Exception:
            try:
                mock_config = request.getfixturevalue("mock_config")
            except Exception:
                # Use default config
                mock_config = create_mock_config()

    with patch("ccbt.session.session.get_config") as mock_get_config:
        mock_get_config.return_value = mock_config

        session = AsyncSessionManager(output_dir=str(tmp_path))
        await session.start()
        try:
            yield session
        finally:
            # CRITICAL: Ensure all background tasks are stopped before session.stop()
            # Cancel background tasks explicitly to ensure proper cleanup
            if hasattr(session, "_cleanup_task") and session._cleanup_task and not session._cleanup_task.done():
                try:
                    session._cleanup_task.cancel()
                    await asyncio.wait_for(session._cleanup_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass  # Expected when cancelling

            if hasattr(session, "_metrics_task") and session._metrics_task and not session._metrics_task.done():
                try:
                    session._metrics_task.cancel()
                    await asyncio.wait_for(session._metrics_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass  # Expected when cancelling

            # Ensure scrape_task is cancelled before stopping
            if hasattr(session, "scrape_task") and session.scrape_task and not session.scrape_task.done():
                try:
                    session.scrape_task.cancel()
                    await asyncio.wait_for(session.scrape_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass  # Expected when cancelling

            # CRITICAL: Ensure all background tasks are stopped
            await session.stop()

            # CRITICAL: Clean up all tracker clients to close aiohttp sessions
            async with session.lock:
                for torrent_session in session.torrents.values():
                    if hasattr(torrent_session, "tracker") and torrent_session.tracker:
                        try:
                            tracker = torrent_session.tracker

                            # Close aiohttp session if it exists (HTTP tracker)
                            if hasattr(tracker, "session"):
                                tracker_session = tracker.session
                                if tracker_session and not tracker_session.closed:
                                    try:
                                        await asyncio.wait_for(
                                            tracker_session.close(), timeout=1.0
                                        )
                                        # Note: Close connector explicitly to ensure complete cleanup
                                        if hasattr(tracker_session, "connector") and tracker_session.connector:
                                            connector = tracker_session.connector
                                            if not connector.closed:
                                                try:
                                                    await asyncio.wait_for(connector.close(), timeout=0.5)
                                                except (asyncio.TimeoutError, Exception):
                                                    pass  # Best effort connector cleanup
                                    except asyncio.TimeoutError:
                                        # Force close if timeout
                                        if not tracker_session.closed:
                                            # Try to close connector before clearing
                                            try:
                                                if hasattr(tracker_session, "connector") and tracker_session.connector:
                                                    connector = tracker_session.connector
                                                    if not connector.closed:
                                                        await connector.close()
                                            except Exception:
                                                pass
                                            # Clear connector to allow garbage collection
                                            if hasattr(tracker_session, "_connector"):
                                                tracker_session._connector = None
                                            if hasattr(tracker_session, "_connector_owner"):
                                                tracker_session._connector_owner = False

                            # Close UDP transport if it exists (UDP tracker)
                            if hasattr(tracker, "transport") and tracker.transport:
                                if not tracker.transport.is_closing():
                                    tracker.transport.close()

                            # Stop tracker client
                            if hasattr(tracker, "stop"):
                                try:
                                    await asyncio.wait_for(tracker.stop(), timeout=2.0)
                                except asyncio.TimeoutError:
                                    pass  # Best effort cleanup
                        except Exception:
                            pass  # Ignore errors during cleanup

            # CRITICAL: Clean up DHT client if it exists
            if hasattr(session, "dht") and session.dht:
                try:
                    # Stop DHT client
                    if hasattr(session.dht, "stop"):
                        try:
                            await asyncio.wait_for(session.dht.stop(), timeout=2.0)
                        except asyncio.TimeoutError:
                            pass  # Best effort cleanup

                    # Close UDP transport if it exists
                    if hasattr(session.dht, "transport") and session.dht.transport:
                        transport = session.dht.transport
                        if not transport.is_closing():
                            transport.close()
                        # Wait briefly for transport to close
                        try:
                            await asyncio.sleep(0.1)
                        except Exception:
                            pass

                    # Close socket if it exists
                    if hasattr(session.dht, "socket") and session.dht.socket:
                        try:
                            socket_obj = session.dht.socket
                            if not socket_obj._closed:
                                socket_obj.close()
                        except Exception:
                            pass
                except Exception:
                    pass  # Ignore errors during cleanup

            # Note: Stop TCP server explicitly before checking port release
            if hasattr(session, "tcp_server") and session.tcp_server:
                try:
                    # Stop TCP server if it has a stop method
                    if hasattr(session.tcp_server, "stop"):
                        try:
                            await asyncio.wait_for(session.tcp_server.stop(), timeout=2.0)
                        except (asyncio.TimeoutError, Exception):
                            pass  # Best effort cleanup

                    # Close server socket if it exists
                    if hasattr(session.tcp_server, "server") and session.tcp_server.server:
                        try:
                            server = session.tcp_server.server
                            if hasattr(server, "close"):
                                server.close()
                            if hasattr(server, "wait_closed"):
                                await asyncio.wait_for(server.wait_closed(), timeout=1.0)
                        except (asyncio.TimeoutError, Exception):
                            pass  # Best effort cleanup

                    # Get the port that was used and verify it's released
                    if hasattr(session.tcp_server, "port") and session.tcp_server.port:
                        port = session.tcp_server.port
                        # Wait up to 3.0s for port to be released (increased from 2.0s)
                        port_released = await wait_for_port_release(port, timeout=3.0)
                        if not port_released:
                            # Log warning but don't fail test - port may be released by OS later
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"TCP server port {port} not released within timeout, may cause conflicts")
                except Exception:
                    pass  # Best effort - port may already be released

            # Note: Verify DHT port is released
            if hasattr(session, "dht_client") and session.dht_client:
                try:
                    # Check if DHT client has a port attribute
                    if hasattr(session.dht_client, "port") and session.dht_client.port:
                        dht_port = session.dht_client.port
                        port_released = await wait_for_port_release(dht_port, timeout=3.0)
                        if not port_released:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"DHT port {dht_port} not released within timeout")
                except Exception:
                    pass  # Best effort

            # Give async cleanup time to complete (increased from 1.0s to 2.0s for better port release)
            await asyncio.sleep(2.0)

            # Verify all tasks are done
            if hasattr(session, "scrape_task") and session.scrape_task:
                assert session.scrape_task.done(), "scrape_task should be done after cleanup"


# CLI Test Fixtures
# These fixtures provide standardized mocks and helpers for CLI testing

@pytest.fixture(scope="function")
def mock_session_manager():
    """Create a comprehensive mock AsyncSessionManager for CLI tests.
    
    This fixture provides all the methods and attributes that CLI commands
    typically need, with sensible defaults that can be overridden in tests.
    
    Returns:
        AsyncMock: Mock AsyncSessionManager with all common methods configured
    """
    from unittest.mock import AsyncMock

    session = AsyncMock()
    session.add_torrent = AsyncMock(return_value="abcd1234" * 4)
    session.get_torrent_status = AsyncMock(return_value={
        "download_rate": 1000.0,
        "upload_rate": 500.0,
        "pieces_completed": 10,
        "pieces_total": 100,
        "progress": 0.1,
        "downloaded_bytes": 1048576,
        "status": "downloading",
    })
    session.get_peers_for_torrent = AsyncMock(return_value=[
        {"ip": "1.2.3.4", "port": 6881, "download_rate": 100.0, "upload_rate": 50.0},
    ])
    session.pause_torrent = AsyncMock()
    session.resume_torrent = AsyncMock()
    session.remove = AsyncMock()
    session.lock = AsyncMock()
    session.lock.__aenter__ = AsyncMock(return_value=None)
    session.lock.__aexit__ = AsyncMock(return_value=None)
    session.torrents = {}
    session.get_scrape_result = AsyncMock(return_value=None)
    session.export_session_state = AsyncMock()
    session.import_session_state = AsyncMock(return_value={"torrents": {}})
    session.get_all_torrent_status = AsyncMock(return_value={})
    session.shutdown = AsyncMock()
    return session


@pytest.fixture
def udp_tracker_client():
    """Create an AsyncUDPTrackerClient instance with test mode enabled.
    
    This fixture provides a UDP tracker client configured for testing:
    - test_mode=True to bypass socket validation
    - Ready to use with mocked transport if needed
    
    Yields:
        AsyncUDPTrackerClient: UDP tracker client instance in test mode
    
    Example:
        def test_something(udp_tracker_client):
            # Client is ready to use with test_mode=True
            # You can mock transport if needed:
            from unittest.mock import Mock
            mock_transport = Mock()
            mock_transport.is_closing = Mock(return_value=False)
            mock_transport.get_extra_info = Mock(return_value=("127.0.0.1", 0))
            udp_tracker_client.transport = mock_transport
            udp_tracker_client._socket_ready = True
    """
    from ccbt.discovery.tracker_udp_client import AsyncUDPTrackerClient

    client = AsyncUDPTrackerClient(test_mode=True)

    yield client

    # Cleanup: ensure transport is closed if it exists
    if client.transport is not None and not client.transport.is_closing():
        try:
            client.transport.close()
        except Exception:
            pass  # Best effort cleanup
    client.transport = None
    client._socket_ready = False


@pytest.fixture
def mock_config_comprehensive():
    """Create a comprehensive mock Config for CLI tests.
    
    This fixture provides all config attributes that CLI commands might access,
    with sensible defaults that can be overridden in tests.
    
    Returns:
        MagicMock: Mock Config with all common attributes configured
    """
    from unittest.mock import MagicMock

    from ccbt.models import CheckpointFormat

    config = MagicMock()

    # Network config (used by cmd_network and others)
    config.network = MagicMock()
    config.network.listen_port = 6881
    config.network.listen_port_tcp = None
    config.network.listen_port_udp = None
    config.network.max_global_peers = 200
    config.network.max_peers_per_torrent = 50
    config.network.max_connections_per_peer = 1
    config.network.pipeline_depth = 5
    config.network.pipeline_adaptive_depth = True
    config.network.block_size_kib = 16
    config.network.min_block_size_kib = 4
    config.network.max_block_size_kib = 64
    config.network.connection_timeout = 30
    config.network.handshake_timeout = 10
    config.network.peer_timeout = 60
    config.network.timeout_adaptive = True
    config.network.keepalive_interval = 60
    config.network.max_idle_time = 120
    config.network.enable_utp = True
    config.network.enable_tcp = True
    config.network.enable_ipv6 = False
    config.network.enable_encryption = True
    config.network.prefer_encryption = True
    config.network.global_down_kib = 0
    config.network.global_up_kib = 0
    config.network.connection_pool_max_connections = 100
    config.network.connection_pool_warmup_enabled = False
    config.network.socket_rcvbuf_kib = 256
    config.network.socket_sndbuf_kib = 256
    config.network.socket_adaptive_buffers = True
    config.network.tcp_nodelay = True

    # Discovery config
    config.discovery = MagicMock()
    config.discovery.tracker_auto_scrape = False
    config.discovery.tracker_scrape_interval = 300.0
    config.discovery.enable_dht = False
    config.discovery.enable_http_trackers = True
    config.discovery.enable_udp_trackers = True
    config.discovery.enable_pex = True
    config.discovery.enable_webtorrent = False

    # Disk config
    config.disk = MagicMock()
    config.disk.checkpoint_interval = 30.0
    config.disk.resume_save_interval = 30.0
    config.disk.fast_resume_enabled = False
    config.disk.checkpoint_batch_interval = 0
    config.disk.checkpoint_batch_pieces = 0
    config.disk.checkpoint_format = CheckpointFormat.BINARY
    config.disk.checkpoint_enabled = True

    # Limits config
    config.limits = MagicMock()
    config.limits.global_down_kib = 0
    config.limits.global_up_kib = 0

    # NAT config
    config.nat = MagicMock()
    config.nat.auto_map_ports = False

    # Security config
    config.security = MagicMock()
    config.security.ip_filter = MagicMock()
    config.security.ip_filter.filter_update_interval = 3600.0

    # Queue config
    config.queue = MagicMock()
    config.queue.auto_manage_queue = False

    # Optimization config
    config.optimization = MagicMock()
    config.optimization.profile = "balanced"

    return config


@pytest.fixture(scope="function")
def mock_daemon_not_running(monkeypatch):
    """Mock daemon detection to always return False (daemon not running).
    
    This is useful for unit tests that should run in local mode.
    
    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    from unittest.mock import Mock
    mock_daemon_manager = Mock()
    mock_daemon_manager.is_running = Mock(return_value=False)
    mock_daemon_manager.get_pid = Mock(return_value=None)

    # Patch DaemonManager to return our mock
    monkeypatch.setattr("ccbt.daemon.daemon_manager.DaemonManager", lambda: mock_daemon_manager)
    return mock_daemon_manager


@pytest.fixture
def cli_interactive_fixture(mock_session_manager, mock_config_comprehensive):
    """Create a complete InteractiveCLI fixture with all dependencies.
    
    This fixture combines session manager, config, and console into a ready-to-use
    InteractiveCLI instance for testing.
    
    Args:
        mock_session_manager: Mock session manager fixture
        mock_config_comprehensive: Mock config fixture
    
    Returns:
        InteractiveCLI: Configured InteractiveCLI instance
    """
    import time
    from unittest.mock import Mock, patch

    from rich.console import Console as RichConsole

    console = Mock(spec=RichConsole)
    console.print = Mock()
    console.clear = Mock()
    console.print_json = Mock()
    console.get_time = Mock(return_value=time.time)

    # Patch get_config to return our mock config
    with patch("ccbt.cli.interactive.get_config", return_value=mock_config_comprehensive):
        cli = create_interactive_cli(mock_session_manager, console)
        return cli
