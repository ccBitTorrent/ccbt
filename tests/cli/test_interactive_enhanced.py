"""Tests for enhanced interactive CLI helpers (command methods).

We do not run a full interactive loop; we instantiate and call command methods
directly to verify they execute without raising exceptions.
"""

from __future__ import annotations

import pytest
from rich.console import Console

from ccbt.cli.interactive import InteractiveCLI


class DummySession:
    def __init__(self) -> None:
        self._status = {"progress": 0.0}

    async def add_torrent(self, td: dict, resume: bool = False) -> str:
        return "00" * 20

    async def get_torrent_status(self, ih: str) -> dict | None:
        return self._status

    async def pause_torrent(self, ih: str) -> bool:
        return True

    async def resume_torrent(self, ih: str) -> bool:
        return True

    async def remove(self, ih: str) -> bool:
        return True

    async def export_session_state(self, path):
        return None

    async def import_session_state(self, path):
        return {"torrents": {}}

    async def set_rate_limits(self, ih: str, down: int, up: int) -> bool:
        return True


@pytest.mark.asyncio
async def test_interactive_basic_commands():
    session = DummySession()
    cli = InteractiveCLI(session, Console(record=True))
    # Prime current torrent
    cli.current_torrent = {"name": "test", "total_length": 1024}
    cli.current_info_hash_hex = "00" * 20
    await cli.cmd_status([])
    await cli.cmd_pause([])
    await cli.cmd_resume([])
    await cli.cmd_clear([])


@pytest.mark.asyncio
async def test_interactive_config_and_limits():
    session = DummySession()
    cli = InteractiveCLI(session, Console(record=True))
    await cli.cmd_config(["show"])  # print full config
    await cli.cmd_config(["get", "network.listen_port"])  # fetch a key
    await cli.cmd_config(["set", "network.listen_port", "7003"])  # set a key
    await cli.cmd_limits(["set", "00" * 20, "100", "100"])  # set limits


@pytest.mark.asyncio
async def test_interactive_checkpoint_and_alerts():
    session = DummySession()
    cli = InteractiveCLI(session, Console(record=True))
    # These commands will exercise code paths; they may print warnings if backends unavailable
    await cli.cmd_metrics(["show"])  # metrics snapshot
    await cli.cmd_alerts(["list"])  # list rules
