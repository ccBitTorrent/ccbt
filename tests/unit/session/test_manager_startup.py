from __future__ import annotations

import asyncio
from typing import Any
import contextlib

# Functions removed from manager_startup - test disabled
# from ccbt.session.manager_startup import (
#     start_background_tasks,
#     start_security_manager,
# )


class DummyLogger:
    def info(self, *_: Any, **__: Any) -> None: ...
    def warning(self, *_: Any, **__: Any) -> None: ...
    def debug(self, *_: Any, **__: Any) -> None: ...
    def exception(self, *_: Any, **__: Any) -> None: ...


class DummyConfig:
    class Net:
        listen_interface = "127.0.0.1"
        listen_port = 6881
        enable_ipv6 = False

    class Disc:
        dht_port = 6881
        tracker_auto_scrape = False
        enable_dht = False

    class Queue:
        auto_manage_queue = False

    class Nat:
        auto_map_ports = False

    network = Net()
    discovery = Disc()
    queue = Queue()
    nat = Nat()


class DummySecurity:
    async def load_ip_filter(self, *_: Any, **__: Any) -> None:
        return


class DummyManager:
    def __init__(self) -> None:
        self.logger = DummyLogger()
        self.config = DummyConfig()
        self.security_manager = None
        self._cleanup_task = None
        self._metrics_task = None
        self.scrape_task = None

    def _make_security_manager(self) -> Any:
        return DummySecurity()

    async def _cleanup_loop(self) -> None:  # pragma: no cover - background
        await asyncio.sleep(0.01)

    async def _metrics_loop(self) -> None:  # pragma: no cover - background
        await asyncio.sleep(0.01)


async def test_manager_startup_helpers_smoke() -> None:
    # Test disabled - functions removed from manager_startup
    mgr = DummyManager()
    # log_network_configuration removed - function no longer exists
    # await start_security_manager(mgr)
    # assert mgr.security_manager is not None
    # await start_background_tasks(mgr)
    # Cancel tasks created
    for t in (mgr._cleanup_task, mgr._metrics_task, mgr.scrape_task):
        if t:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t


