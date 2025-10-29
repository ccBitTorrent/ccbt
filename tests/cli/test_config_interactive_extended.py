from __future__ import annotations

import asyncio

from rich.console import Console

from ccbt.cli.interactive import InteractiveCLI
from ccbt.session import AsyncSessionManager


class _FakeSession(AsyncSessionManager):  # type: ignore[misc]
    def __init__(self):
        pass
    async def add_torrent(self, *_args, **_kwargs):  # pragma: no cover - not called here
        return "deadbeef"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_interactive_capabilities_commands_run() -> None:
    cli = InteractiveCLI(_FakeSession(), Console())
    _run(cli.cmd_capabilities([]))
    _run(cli.cmd_capabilities(["summary"]))


def test_interactive_template_list_runs() -> None:
    cli = InteractiveCLI(_FakeSession(), Console())
    _run(cli.cmd_template(["list"]))


def test_interactive_profile_list_runs() -> None:
    cli = InteractiveCLI(_FakeSession(), Console())
    _run(cli.cmd_profile(["list"]))


def test_interactive_auto_tune_preview_runs() -> None:
    cli = InteractiveCLI(_FakeSession(), Console())
    _run(cli.cmd_auto_tune(["preview"]))


