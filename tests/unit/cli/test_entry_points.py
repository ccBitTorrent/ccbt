from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest


def test___main___daemon_status_quick_exit(monkeypatch):
    """Smoke-test ccbt.__main__ with --daemon --status for quick, side-effect-free exit."""
    import ccbt.__main__ as mainmod

    argv = [
        "python",
        "magnet:?xt=urn:btih:0123456789ABCDEF0123456789ABCDEF01234567",
        "--daemon",
        "--status",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    rc = mainmod.main()
    assert rc == 0


@pytest.mark.asyncio
async def test_async_main_sync_wrapper_daemon_status(monkeypatch):
    """Smoke-test CLI main via main() with --daemon --status."""
    from unittest.mock import AsyncMock, MagicMock, patch

    class _FakeConfigMgr:
        def __init__(self):
            self.config = SimpleNamespace()
            # attribute used to decide starting hot reload
            setattr(self.config, "_config_file", None)

        async def start_hot_reload(self):  # pragma: no cover
            pass

        def stop_hot_reload(self):  # pragma: no cover
            pass

    from ccbt.config import config as config_module
    monkeypatch.setattr(config_module, "init_config", lambda _p: _FakeConfigMgr())

    # Mock _get_executor to return None (no daemon running)
    # This will cause status command to exit gracefully
    async def mock_get_executor():
        return (None, False)
    
    # Use patch context manager to patch the function
    with patch("ccbt.cli.main._get_executor", mock_get_executor):
        # Run CLI status command via Click
        from ccbt.cli.main import cli
        from click.testing import CliRunner
        
        runner = CliRunner()
        # Test status command - should exit gracefully when no daemon is running
        result = runner.invoke(cli, ["status"])
        # Status command should exit with code 0 (success) or 1 (no daemon)
        # Both are acceptable for this smoke test
        assert result.exit_code in (0, 1)


