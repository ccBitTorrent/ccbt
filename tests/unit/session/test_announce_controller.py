from __future__ import annotations

from types import SimpleNamespace
from typing import Any, List, Optional

from ccbt.config.config import get_config
from ccbt.session.announce import AnnounceController, slice_trackers_for_announce_round
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
        left: Optional[int] = None,
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


def test_collect_trackers_truncates_when_max_tracker_urls_configured() -> None:
    config = get_config()
    config = config.model_copy(
        update={
            "discovery": config.discovery.model_copy(
                update={"max_tracker_urls_per_torrent": 2},
            ),
        },
    )
    torrent_data = {
        "info_hash": b"x" * 20,
        "name": "many-trackers",
        "trackers": [
            "udp://a.example:1/announce",
            "udp://b.example:2/announce",
            "udp://c.example:3/announce",
        ],
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
    controller = AnnounceController(ctx, FakeTracker())
    urls = controller.collect_trackers(torrent_data)
    assert len(urls) == 2
    assert urls[0].startswith("udp://a.")
    assert urls[1].startswith("udp://b.")


def test_slice_trackers_for_announce_round_rotates() -> None:
    urls = ["a", "b", "c", "d"]
    s1, off1 = slice_trackers_for_announce_round(urls, cap=2, offset=0)
    assert s1 == ["a", "b"]
    s2, off2 = slice_trackers_for_announce_round(urls, cap=2, offset=off1)
    assert s2 == ["c", "d"]
    s3, _ = slice_trackers_for_announce_round(urls, cap=2, offset=off2)
    assert s3 == ["a", "b"]


def test_slice_trackers_for_announce_round_full_when_unneeded() -> None:
    urls = ["x", "y"]
    out, nxt = slice_trackers_for_announce_round(urls, cap=10, offset=0)
    assert out == urls
    assert nxt == 0


