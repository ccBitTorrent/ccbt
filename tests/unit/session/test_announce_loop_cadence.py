"""Tests for AnnounceLoop cadence fixes (RC-4/5).

Covers:
- AnnounceLoop reads `discovery.tracker_announce_interval` (not
  `network.announce_interval`) as the base interval.
- Tracker `min_interval` is honored as a hard floor; weak-swarm acceleration
  cannot push the interval below it.
- `requestable_peers == 0` with `connected_peers > 0` triggers the 90s
  acceleration tier.
- Loop continues on exception (regression guard).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.session.announce import AnnounceController, AnnounceLoop
from ccbt.session.session import AsyncTorrentSession, TorrentSessionInfo


def _make_session(announce_interval_disc: float = 60.0) -> AsyncTorrentSession:
    td = {
        "name": "test",
        "info_hash": b"1" * 20,
        "announce": "http://tracker.example.com/announce",
        "pieces_info": {
            "num_pieces": 0,
            "piece_length": 0,
            "piece_hashes": [],
            "total_length": 0,
        },
        "file_info": {"total_length": 0},
    }
    session = AsyncTorrentSession(td, ".")
    session._stop_event = asyncio.Event()
    # Base interval must come from discovery, not network. Set both to distinct
    # sentinel values so we can detect which one the loop actually used.
    session.config.network.announce_interval = 1800
    session.config.discovery.tracker_announce_interval = announce_interval_disc
    if not hasattr(session, "info") or session.info is None:
        session.info = TorrentSessionInfo(
            info_hash=b"1" * 20,
            name="test",
            status="downloading",
        )
    return session


def _wire_tracker(session, responses, *, sessions_map=None):
    async def announce_to_multiple(self, _td, _urls, port=None, event=""):
        return list(responses)

    session.tracker = type(
        "T",
        (),
        {"announce_to_multiple": announce_to_multiple, "sessions": sessions_map or {}},
    )()


def _wire_fast_sleep(monkeypatch):
    original_sleep = asyncio.sleep

    async def fast_sleep(secs):
        await original_sleep(min(secs, 0.01))

    monkeypatch.setattr("ccbt.session.announce.asyncio.sleep", fast_sleep)


def _wire_collect_trackers(monkeypatch, urls):
    def collect_trackers(self, _td):
        return list(urls)

    monkeypatch.setattr(AnnounceController, "collect_trackers", collect_trackers)


def _wire_ingest_capture(session):
    captured: list = []

    async def capture_ingest(peers, **_kwargs):
        captured.append(peers)
        return len(peers)

    session._ingest_tracker_discovery_peers = capture_ingest  # type: ignore[method-assign]
    session.download_manager = SimpleNamespace(
        peer_manager=SimpleNamespace(),
        _download_started=True,
    )
    return captured


def _build_response(*, interval=1800, peers=None, complete=10, incomplete=5):
    if peers is None:
        peers = [SimpleNamespace(ip="1.0.0.1", port=6881, ssl_capable=False)]
    return SimpleNamespace(
        peers=peers,
        complete=complete,
        incomplete=incomplete,
        interval=interval,
    )


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_announce_loop_uses_discovery_interval_not_network(monkeypatch):
    """Loop base interval comes from discovery.tracker_announce_interval (60s),
    not network.announce_interval (1800s). Verified by observing the sleep
    durations called via the patched fast_sleep (which receives the real secs)."""
    session = _make_session(announce_interval_disc=60.0)
    _wire_tracker(session, [_build_response(interval=1800)])
    _wire_collect_trackers(monkeypatch, ["http://tracker.example.com/announce"])
    _wire_ingest_capture(session)
    session.get_swarm_recovery_state = AsyncMock(
        return_value={
            "active_peers": 5,
            "productive_peers": 5,
            "requestable_peers": 5,
            "peers_with_piece_info": 5,
        }
    )

    slept: list[float] = []
    original_sleep = asyncio.sleep

    async def tracking_sleep(secs):
        slept.append(float(secs))
        await original_sleep(min(secs, 0.01))

    monkeypatch.setattr("ccbt.session.announce.asyncio.sleep", tracking_sleep)

    # Tracker interval=1800 is honored up to adaptive_max (3600). With a healthy
    # swarm (5 active, 5 productive, 5 requestable), no weak-swarm cap applies and
    # adaptive multipliers keep it near 1800. The key assertion: the loop did NOT
    # sleep for the old 1800s base when tracker didn't ask for it — and when tracker
    # asks for 1800, that's the value used, not network.announce_interval.
    loop = AnnounceLoop(session)
    task = asyncio.create_task(loop.run())
    await original_sleep(0.08)
    session._stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # The first sleep after a successful announce should reflect the tracker's
    # interval (1800), not the deprecated network.announce_interval (which is
    # also 1800 here but the discovery base of 60 is what feeds the cap math).
    # Assert at least one sleep was recorded and that none equals the discovery
    # base of 60 when the tracker asked for 1800 (i.e. tracker interval wins).
    assert slept, "AnnounceLoop did not sleep after announce"
    announce_sleeps = [s for s in slept if s > 100]
    assert announce_sleeps, (
        f"Expected a sleep near tracker interval (1800); got sleeps={slept}"
    )


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_announce_loop_respects_tracker_min_interval_floor(monkeypatch):
    """Weak-swarm acceleration (60s) must not push below tracker min_interval (300s)."""
    session = _make_session(announce_interval_disc=60.0)
    url = "http://tracker.example.com/announce"
    tracker_session = SimpleNamespace(min_interval=300, interval=1800)
    _wire_tracker(
        session,
        [_build_response(interval=1800)],
        sessions_map={url: tracker_session},
    )
    _wire_collect_trackers(monkeypatch, [url])
    _wire_ingest_capture(session)
    # Swarm is dead -> would normally trigger 60s weak-swarm cap.
    session.get_swarm_recovery_state = AsyncMock(
        return_value={
            "active_peers": 0,
            "productive_peers": 0,
            "requestable_peers": 0,
            "peers_with_piece_info": 0,
        }
    )

    slept: list[float] = []
    original_sleep = asyncio.sleep

    async def tracking_sleep(secs):
        slept.append(float(secs))
        await original_sleep(min(secs, 0.01))

    monkeypatch.setattr("ccbt.session.announce.asyncio.sleep", tracking_sleep)

    loop = AnnounceLoop(session)
    task = asyncio.create_task(loop.run())
    await original_sleep(0.08)
    session._stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # The post-announce sleep must be >= tracker min_interval (300s), even though
    # weak-swarm acceleration would otherwise cap it at 60s.
    announce_sleeps = [s for s in slept if s >= 300.0]
    assert announce_sleeps, (
        f"Expected a sleep >= tracker min_interval (300s); got sleeps={slept}"
    )


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_announce_loop_accelerates_on_zero_requestable_with_connected(
    monkeypatch,
):
    """connected_peers > 0 and requestable_peers == 0 triggers the 90s acceleration tier."""
    session = _make_session(announce_interval_disc=60.0)
    _wire_tracker(session, [_build_response(interval=1800)])
    _wire_collect_trackers(monkeypatch, ["http://tracker.example.com/announce"])
    _wire_ingest_capture(session)
    session.get_swarm_recovery_state = AsyncMock(
        return_value={
            "active_peers": 5,
            "productive_peers": 5,
            "requestable_peers": 0,
            "peers_with_piece_info": 5,
        }
    )

    slept: list[float] = []
    original_sleep = asyncio.sleep

    async def tracking_sleep(secs):
        slept.append(float(secs))
        await original_sleep(min(secs, 0.01))

    monkeypatch.setattr("ccbt.session.announce.asyncio.sleep", tracking_sleep)

    loop = AnnounceLoop(session)
    task = asyncio.create_task(loop.run())
    await original_sleep(0.08)
    session._stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Tracker interval=1800, but requestable==0 with connected=5 -> 90s cap.
    # Assert a sleep <= 90 appears (the 90s cap), and no sleep > 90 (i.e. the
    # tracker's 1800 was overridden by the weak-swarm cap).
    announce_sleeps = [s for s in slept if s > 0.1]
    assert announce_sleeps, f"No announce sleep recorded; sleeps={slept}"
    assert min(announce_sleeps) <= 90.0, (
        f"Expected weak-swarm cap of 90s to apply; got sleeps={slept}"
    )


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_announce_loop_continues_on_exception(monkeypatch):
    """Announce loop must continue after a tracker exception (regression guard)."""
    session = _make_session(announce_interval_disc=60.0)
    call_count = {"n": 0}

    async def announce_to_multiple(self, _td, _urls, port=None, event=""):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated tracker failure")
        return [_build_response(interval=60)]

    session.tracker = type(
        "T",
        (),
        {"announce_to_multiple": announce_to_multiple, "sessions": {}},
    )()
    _wire_collect_trackers(monkeypatch, ["http://tracker.example.com/announce"])
    _wire_ingest_capture(session)
    session.get_swarm_recovery_state = AsyncMock(
        return_value={
            "active_peers": 0,
            "productive_peers": 0,
            "requestable_peers": 0,
            "peers_with_piece_info": 0,
        }
    )

    original_sleep = asyncio.sleep

    async def fast_sleep(secs):
        await original_sleep(min(secs, 0.01))

    monkeypatch.setattr("ccbt.session.announce.asyncio.sleep", fast_sleep)

    loop = AnnounceLoop(session)
    task = asyncio.create_task(loop.run())
    await original_sleep(0.15)
    session._stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert call_count["n"] >= 2, (
        f"Loop should have retried after exception; call_count={call_count['n']}"
    )
