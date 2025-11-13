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

    # Make parse_args return desired args without touching argparse internals
    fake_args = SimpleNamespace(
        torrent=None,
        config=None,
        output_dir=".",
        port=None,
        max_peers=None,
        down_limit=None,
        up_limit=None,
        log_level=None,
        magnet=False,
        daemon=True,
        add=None,
        status=True,
        metrics=False,
        streaming=False,
    )

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
    import argparse
    monkeypatch.setattr(config_module, "init_config", lambda _p: _FakeConfigMgr())
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self: fake_args)

    # Run CLI main() directly (Click entrypoint raises SystemExit)
    from ccbt.cli.main import main
    with pytest.raises(SystemExit) as excinfo:
        main()
    rc = excinfo.value.code
    assert rc == 0


