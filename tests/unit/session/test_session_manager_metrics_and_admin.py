import asyncio
import pytest


@pytest.mark.asyncio
async def test_set_rate_limits_and_stats_aggregation(monkeypatch):
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(".")

    # No torrents yet
    assert await mgr.set_rate_limits("deadbeef", 100, 50) is False

    # Inject a dummy torrent session with required properties
    class _Dummy:
        def __init__(self):
            self._status = {
                "status": "downloading",
                "download_rate": 2.5,
                "upload_rate": 1.0,
                "progress": 0.4,
                "downloaded": 100,
                "uploaded": 10,
                "left": 900,
                "peers": 3,
            }

        async def get_status(self):
            return dict(self._status)

        @property
        def downloaded_bytes(self):
            return self._status["downloaded"]

        @property
        def uploaded_bytes(self):
            return self._status["uploaded"]

        @property
        def left_bytes(self):
            return self._status["left"]

        @property
        def peers(self):
            return {"count": self._status["peers"]}

        @property
        def download_rate(self):
            return self._status["download_rate"]

        @property
        def upload_rate(self):
            return self._status["upload_rate"]

    ih = bytes.fromhex("11" * 20)
    async with mgr.lock:
        mgr.torrents[ih] = _Dummy()

    # Now set rate limits on existing torrent
    ok = await mgr.set_rate_limits(ih.hex(), 200, 100)
    assert ok is True

    # Aggregate stats
    stats = await mgr.get_global_stats()
    assert stats["num_torrents"] == 1
    assert stats["num_active"] == 1
    assert stats["download_rate"] > 0
    assert stats["upload_rate"] > 0
    assert 0 < stats["average_progress"] <= 1


@pytest.mark.asyncio
async def test_emit_global_metrics(monkeypatch):
    from ccbt.session.session import AsyncSessionManager
    from ccbt.utils import events as ev_mod

    recorded = {}

    async def _emit(evt):
        recorded["evt"] = evt

    monkeypatch.setattr(ev_mod, "emit_event", _emit)

    mgr = AsyncSessionManager(".")
    stats = {"total_torrents": 0}
    await mgr._emit_global_metrics(stats)
    assert "evt" in recorded

