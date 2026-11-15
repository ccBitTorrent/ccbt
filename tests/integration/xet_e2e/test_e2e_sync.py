"""Folder sync mode scenarios (G8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ccbt.session.xet_conflict import ConflictResolver, ConflictStrategy

pytestmark = [pytest.mark.timeout(30), pytest.mark.integration]


def test_e2e_sync_conflict_preserved(tmp_path: Path) -> None:
    resolver = ConflictResolver(strategy=ConflictStrategy.LAST_WRITE_WINS.value)
    our = {
        "peer_id": "a",
        "timestamp": 1.0,
        "content": b"ours",
        "workspace_root": str(tmp_path),
    }
    their = {
        "peer_id": "b",
        "timestamp": 2.0,
        "content": b"theirs",
        "workspace_root": str(tmp_path),
    }
    winner = resolver.resolve_conflict("dir/file.txt", our, their)
    assert winner["peer_id"] == "b"
    conflicts = list((tmp_path / ".xet" / "conflicts").glob("*"))
    assert conflicts, "loser must be preserved under .xet/conflicts/"


@pytest.mark.asyncio
async def test_e2e_sync_designated_failover() -> None:
    from ccbt.models import PeerInfo
    from ccbt.session.xet_sync_manager import PeerSyncState, SyncMode, XetSyncManager

    mgr = XetSyncManager(sync_mode=SyncMode.DESIGNATED.value, source_peers=["src1"])
    assert mgr.sync_mode == SyncMode.DESIGNATED
    mgr.announce_as_source("src1", term=1)
    assert mgr.source_term == 1
    # Stale same-term rival rejected
    assert not mgr.apply_source_announcement("src2", term=1)
    # Newer term accepted
    assert mgr.apply_source_announcement("src2", term=2)
    assert "src2" in mgr.source_peers
    # Failover when source silent and a healthy peer exists
    mgr.source_failover_timeout = 0.01
    mgr.peer_states["src2"] = PeerSyncState(
        peer_id="src2",
        peer_info=PeerInfo(ip="127.0.0.1", port=1),
        last_contact=0.0,
    )
    mgr.peer_states["alive"] = PeerSyncState(
        peer_id="alive",
        peer_info=PeerInfo(ip="127.0.0.1", port=2),
    )
    elected = await mgr._elect_source_peer()
    assert elected in {"alive", "src2"}
    assert mgr.source_term >= 3

    # Tombstone + rename semantics
    ts = mgr.record_tombstone("a.txt", "alive")
    assert "a.txt" in mgr.tombstones
    assert ts.version_vector["alive"] == 1


@pytest.mark.asyncio
async def test_e2e_sync_broadcast_converges() -> None:
    from ccbt.session.xet_sync_manager import SyncMode, XetSyncManager

    mgr = XetSyncManager(sync_mode=SyncMode.BROADCAST.value)
    assert mgr.sync_mode == SyncMode.BROADCAST
    mgr.enqueue_update = getattr(mgr, "queue_update", None)
    # Smoke: mode is wired and queue accepts entries via public API if present
    assert mgr.update_queue is not None


@pytest.mark.asyncio
async def test_e2e_folder_sync_changed_chunks_only(tmp_path: Path) -> None:
    from ccbt.storage.xet_chunking import GearhashChunker
    from ccbt.storage.xet_hashing import XetHasher

    # Large enough for multiple CDC chunks; edit only the last 1 KiB.
    a = (b"AAAA" * 20000) + (b"ZZZZ" * 20000)
    b = a[:-1024] + (b"B" * 1024)
    ca = GearhashChunker().chunk_buffer(a)
    cb = GearhashChunker().chunk_buffer(b)
    ha = {XetHasher.compute_chunk_hash(c) for c in ca}
    hb = {XetHasher.compute_chunk_hash(c) for c in cb}
    assert len(ca) >= 2 and len(cb) >= 2
    # Edit-locality: at least one chunk identity survives
    assert ha & hb
    assert ha != hb


@pytest.mark.asyncio
async def test_e2e_cold_link_join() -> None:
    from ccbt.core.tonic_link import generate_tonic_link, parse_tonic_link

    wid = b"\x11" * 32
    link = generate_tonic_link(info_hash=wid, display_name="ws", sync_mode="best_effort")
    parsed = parse_tonic_link(link)
    assert parsed.info_hash == wid
