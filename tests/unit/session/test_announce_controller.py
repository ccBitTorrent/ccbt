from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, List

from ccbt.config.config import get_config
from ccbt.session.announce import AnnounceController
from ccbt.session.models import SessionContext


class FakeTracker:
    def __init__(self) -> None:
        self.session = None
        self._started = False

    async def start(self) -> None:
        self._started = True
        self.session = object()

    async def stop(self) -> None:
        self.session = None
        self._started = False

    async def announce_to_multiple(  # type: ignore[override]
        self,
        torrent_data: dict[str, Any],
        tracker_urls: list[str],
        port: int = 6881,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int | None = None,
        event: str = "started",
    ) -> List[Any]:
        # Return two peers across two responses
        p1 = SimpleNamespace(ip="127.0.0.1", port=6881)
        p2 = SimpleNamespace(ip="127.0.0.2", port=6881)
        r1 = SimpleNamespace(peers=[p1])
        r2 = SimpleNamespace(peers=[p2])
        return [r1, r2]


async def test_announce_controller_initial(monkeypatch: Any) -> None:
    config = get_config()
    torrent_data = {
        "info_hash": b"x" * 20,
        "name": "sample",
        "announce": "udp://tracker.opentrackr.org:1337/announce",
        "file_info": {"total_length": 0},
    }
    ctx = SessionContext(
        config=config,
        torrent_data=torrent_data,
        output_dir=config.disk.download_dir,
        info=None,
        session_manager=None,
        logger=None,
    )

    tracker = FakeTracker()
    controller = AnnounceController(ctx, tracker)
    responses = await controller.announce_initial()
    assert isinstance(responses, list)
    assert len(responses) == 2



