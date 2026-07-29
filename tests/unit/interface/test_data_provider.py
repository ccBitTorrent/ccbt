"""Unit tests for interface data providers."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.daemon.ipc_protocol import (
    DHTQueryMetricsResponse,
    EventType,
    TorrentStatusResponse,
)
from ccbt.interface.data_provider import DaemonDataProvider, LocalDataProvider

pytestmark = [pytest.mark.unit, pytest.mark.interface]


@pytest.mark.asyncio
async def test_local_provider_uses_single_torrent_status_path() -> None:
    """Local provider should call get_torrent_status, not full status map."""
    expected = {
        "info_hash": "a" * 40,
        "name": "Ubuntu ISO",
        "status": "downloading",
        "progress": 0.5,
        "download_rate": 128.0,
        "upload_rate": 64.0,
        "connected_peers": 7,
        "active_peers": 3,
        "downloaded": 50,
        "uploaded": 10,
        "total_size": 100,
        "pieces_completed": 5,
        "pieces_total": 10,
    }
    session = MagicMock()
    session.get_torrent_status = AsyncMock(return_value=expected)
    session.get_status = AsyncMock(side_effect=AssertionError("should not be called"))

    provider = LocalDataProvider(session)
    result = await provider.get_torrent_status("a" * 40)

    assert result is not None
    assert result["info_hash"] == expected["info_hash"]
    assert result["connected_peers"] == 7
    assert result["active_peers"] == 3
    assert "num_peers" not in result
    assert "num_seeds" not in result
    session.get_torrent_status.assert_awaited_once_with("a" * 40)
    session.get_status.assert_not_called()


@pytest.mark.asyncio
async def test_daemon_provider_ttl_zero_disables_cache() -> None:
    """ttl=0.0 must force a fresh fetch on every cache access."""
    client = MagicMock()
    provider = DaemonDataProvider(client)
    fetch_calls = 0

    async def _fetch() -> int:
        nonlocal fetch_calls
        fetch_calls += 1
        return fetch_calls

    assert await provider._get_cached("ttl_test", _fetch, ttl=0.0) == 1
    assert await provider._get_cached("ttl_test", _fetch, ttl=0.0) == 2
    assert fetch_calls == 2


@pytest.mark.asyncio
async def test_daemon_provider_on_event_allows_string_event_types() -> None:
    """String event type values should normalize and clear the intended cache keys."""
    provider = DaemonDataProvider(MagicMock())
    info_hash = "g" * 40
    provider._cache = {
        f"trackers_{info_hash}": (["x"], 0.0),
        f"torrent_files_{info_hash}": (["y"], 0.0),
        f"torrent_status_{info_hash}": ({}, 0.0),
    }

    provider.invalidate_on_event("TRACKER_ANNOUNCE_SUCCESS", info_hash)
    await asyncio.sleep(0.01)

    assert f"trackers_{info_hash}" not in provider._cache
    assert f"torrent_files_{info_hash}" not in provider._cache
    assert f"torrent_status_{info_hash}" not in provider._cache


@pytest.mark.asyncio
async def test_daemon_provider_get_peer_metrics_normalizes_rates() -> None:
    """DaemonDataProvider should project peer rate fields to canonical names."""
    client = MagicMock()
    client.get_peer_metrics = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda: {
                "total_peers": 2,
                "active_peers": 1,
                "peers": [
                    {
                        "ip": "127.0.0.1",
                        "port": 6881,
                        "total_download_rate": 4096.0,
                        "total_upload_rate": 1024.0,
                    },
                    {
                        "ip": "10.0.0.1",
                        "port": 51413,
                        "download_rate": 3072.0,
                        "upload_rate": 2048.0,
                    },
                ],
            }
        )
    )

    provider = DaemonDataProvider(client)
    metrics = await provider.get_peer_metrics()

    assert metrics["total_peers"] == 2
    assert metrics["peers"][0]["download_rate"] == 4096.0
    assert metrics["peers"][0]["upload_rate"] == 1024.0
    assert metrics["peers"][1]["download_rate"] == 3072.0
    assert metrics["peers"][1]["upload_rate"] == 2048.0
    assert "total_download_rate" not in metrics["peers"][0]
    assert "total_upload_rate" not in metrics["peers"][0]


@pytest.mark.asyncio
async def test_daemon_provider_invalidate_on_tracker_and_metadata_events() -> None:
    """Tracker/metadata events should clear targeted cache entries."""
    provider = DaemonDataProvider(MagicMock())
    info_hash = "b" * 40
    provider._cache = {
        f"trackers_{info_hash}": (["x"], 0.0),
        f"torrent_files_{info_hash}": ([{"index": 0}], 0.0),
        f"torrent_status_{info_hash}": ({"progress": 0.5}, 0.0),
        "metrics": ({}, 0.0),
        "global_kpis": ({}, 0.0),
    }

    provider.invalidate_on_event(EventType.TRACKER_ANNOUNCE_SUCCESS, info_hash)
    provider.invalidate_on_event(EventType.METADATA_READY, info_hash)
    await asyncio.sleep(0.01)

    assert f"trackers_{info_hash}" not in provider._cache
    assert f"torrent_files_{info_hash}" not in provider._cache
    assert f"torrent_status_{info_hash}" not in provider._cache
    assert "metrics" not in provider._cache
    assert "global_kpis" not in provider._cache


@pytest.mark.asyncio
async def test_daemon_provider_batch_invalidates_cache_keys() -> None:
    """Concurrent invalidation calls should aggregate and clear all queued entries."""
    provider = DaemonDataProvider(MagicMock())
    provider._cache = {
        "a": ("alpha", 0.0),
        "b": ("beta", 0.0),
        "c": ("gamma", 0.0),
    }

    provider.invalidate_cache("a")
    provider.invalidate_cache("b")
    provider.invalidate_cache(None)
    provider.invalidate_cache("c")

    await asyncio.sleep(0.02)

    assert provider._cache == {}


@pytest.mark.asyncio
async def test_daemon_provider_global_stats_maps_canonical_rates() -> None:
    """Global stats should expose canonical rate keys."""
    response = SimpleNamespace(
        num_torrents=3,
        num_active=2,
        num_paused=1,
        total_download_rate=1250.0,
        total_upload_rate=640.0,
        total_downloaded=1000,
        total_uploaded=500,
        stats={"connected_peers": 7, "uptime": 12.0},
    )
    client = MagicMock()
    client.get_global_stats = AsyncMock(return_value=response)

    provider = DaemonDataProvider(client)
    stats = await provider.get_global_stats()

    assert stats["download_rate"] == 1250.0
    assert stats["upload_rate"] == 640.0
    assert "total_download_rate" not in stats
    assert "total_upload_rate" not in stats
    assert stats["connected_peers"] == 7
    assert stats["uptime"] == 12.0


@pytest.mark.asyncio
async def test_local_provider_list_torrents_exposes_canonical_peer_keys() -> None:
    """Local torrent lists should expose canonical peer key names."""
    session = MagicMock()
    session.get_status = AsyncMock(
        return_value={
            "a" * 40: {
                "info_hash": "a" * 40,
                "name": "Example",
                "status": "downloading",
                "progress": 0.25,
                "download_rate": 512.0,
                "upload_rate": 128.0,
                "connected_peers": 4,
                "active_peers": 1,
                "downloaded": 250,
                "uploaded": 25,
                "total_size": 1000,
                "pieces_completed": 2,
                "pieces_total": 8,
            },
        },
    )

    provider = LocalDataProvider(session)
    torrents = await provider.list_torrents()

    assert len(torrents) == 1
    assert torrents[0]["connected_peers"] == 4
    assert torrents[0]["active_peers"] == 1
    assert "num_peers" not in torrents[0]
    assert "num_seeds" not in torrents[0]


@pytest.mark.asyncio
async def test_daemon_and_local_providers_share_torrent_status_shape() -> None:
    """Daemon and local providers should expose matching torrent status keys."""
    info_hash = "c" * 40
    local_session = MagicMock()
    local_session.get_torrent_status = AsyncMock(
        return_value={
            "info_hash": info_hash,
            "name": "Parity",
            "status": "seeding",
            "progress": 1.0,
            "download_rate": 0.0,
            "upload_rate": 42.0,
            "connected_peers": 6,
            "active_peers": 6,
            "downloaded": 100,
            "uploaded": 200,
            "total_size": 100,
            "pieces_completed": 8,
            "pieces_total": 8,
            "is_private": True,
            "output_dir": "C:/downloads",
        },
    )
    daemon_client = MagicMock()
    daemon_client.get_torrent_status = AsyncMock(
        return_value=TorrentStatusResponse(
            info_hash=info_hash,
            name="Parity",
            status="seeding",
            progress=1.0,
            download_rate=0.0,
            upload_rate=42.0,
            num_peers=6,
            num_seeds=6,
            total_size=100,
            downloaded=100,
            uploaded=200,
            is_private=True,
            output_dir="C:/downloads",
            pieces_completed=8,
            pieces_total=8,
        ),
    )

    local_provider = LocalDataProvider(local_session)
    daemon_provider = DaemonDataProvider(daemon_client)

    local_status = await local_provider.get_torrent_status(info_hash)
    daemon_status = await daemon_provider.get_torrent_status(info_hash)

    assert local_status is not None
    assert daemon_status is not None
    assert set(local_status) == set(daemon_status)
    assert daemon_status["connected_peers"] == 6


@pytest.mark.asyncio
async def test_daemon_provider_preserves_extended_torrent_status_fields() -> None:
    """Daemon provider should preserve tracker and swarm health extensions."""
    info_hash = "d" * 40
    client = MagicMock()
    client.get_torrent_status = AsyncMock(
        return_value=TorrentStatusResponse(
            info_hash=info_hash,
            name="Extended",
            status="downloading",
            progress=0.1,
            download_rate=0.0,
            upload_rate=0.0,
            num_peers=2,
            num_seeds=0,
            total_size=100,
            downloaded=10,
            uploaded=0,
            tracker_status="degraded",
            last_tracker_error="timeout",
            last_error="metadata pending",
            productive_peers=0,
            requestable_peers=0,
            handshake_complete_peers=2,
            extension_capable_peers=2,
            metadata_capable_peers=1,
            hash_verification_failures=3,
        )
    )

    provider = DaemonDataProvider(client)
    status = await provider.get_torrent_status(info_hash)

    assert status is not None
    assert status["tracker_status"] == "degraded"
    assert status["last_tracker_error"] == "timeout"
    assert status["productive_peers"] == 0
    assert status["requestable_peers"] == 0
    assert status["handshake_complete_peers"] == 2
    assert status["extension_capable_peers"] == 2
    assert status["metadata_capable_peers"] == 1
    assert status["hash_verification_failures"] == 3


@pytest.mark.asyncio
async def test_daemon_provider_tracker_rows_include_screen_compat_aliases() -> None:
    """Tracker rows should expose both canonical and legacy screen field names."""
    client = MagicMock()
    client.get_torrent_trackers = AsyncMock(
        return_value=SimpleNamespace(
            trackers=[
                SimpleNamespace(
                    url="udp://tracker.example:80/announce",
                    status="timeout",
                    seeds=0,
                    peers=12,
                    downloaders=4,
                    last_update=123.0,
                    error="timed out",
                )
            ]
        )
    )

    provider = DaemonDataProvider(client)
    trackers = await provider.get_torrent_trackers("e" * 40)

    assert len(trackers) == 1
    assert trackers[0]["status"] == "timeout"
    assert trackers[0]["tracker_status"] == "timeout"
    assert trackers[0]["last_update"] == 123.0
    assert trackers[0]["last_announce"] == 123.0


@pytest.mark.asyncio
async def test_daemon_piece_health_avoids_guessed_dht_success_ratio() -> None:
    """Piece health should not invent a DHT success ratio without a success counter."""
    client = MagicMock()
    client.get_torrent_piece_availability = AsyncMock(return_value=[1, 0, 2])
    client.get_torrent_piece_selection_metrics = AsyncMock(return_value={})
    client.get_torrent_dht_metrics = AsyncMock(
        return_value=DHTQueryMetricsResponse(
            info_hash="f" * 40,
            total_queries=4,
            total_peers_found=0,
        )
    )
    client.get_torrent_peer_quality = AsyncMock(return_value=None)

    provider = DaemonDataProvider(client)
    piece_health = await provider.get_piece_health("f" * 40)

    assert piece_health["dht_success_ratio"] is None


@pytest.mark.asyncio
async def test_local_provider_lists_xet_folders_with_flattened_status() -> None:
    """Local XET folder reads should expose the normalized workspace schema."""
    session = MagicMock()
    session.list_xet_folders = AsyncMock(
        return_value=[
            {
                "folder_key": "workspace-1",
                "folder_path": "C:/workspaces/demo",
                "workspace_id": "a" * 64,
                "sync_mode": "best_effort",
                "bootstrap_pending": False,
                "metadata_source": "remote",
                "started": True,
                "status": {
                    "is_syncing": True,
                    "connected_peers": 2,
                    "pending_changes": 1,
                    "sync_progress": 0.5,
                    "current_git_ref": "deadbeef",
                },
            }
        ]
    )
    session.get_xet_folder_status = AsyncMock(
        return_value={
            "folder_path": "C:/workspaces/demo",
            "sync_mode": "best_effort",
            "is_syncing": True,
            "connected_peers": 2,
            "pending_changes": 1,
            "sync_progress": 0.5,
        }
    )

    provider = LocalDataProvider(session)
    folders = await provider.list_xet_folders()
    status = await provider.get_xet_folder_status("workspace-1")

    assert len(folders) == 1
    assert folders[0]["folder_key"] == "workspace-1"
    assert folders[0]["connected_peers"] == 2
    assert folders[0]["sync_progress"] == 0.5
    assert status is not None
    assert status["folder_key"] == "workspace-1"
    assert status["sync_mode"] == "best_effort"


@pytest.mark.asyncio
async def test_daemon_provider_invalidates_xet_caches_on_xet_events() -> None:
    """XET events should invalidate both list and per-folder XET caches."""
    provider = DaemonDataProvider(MagicMock())
    provider._cache = {
        "xet_folders": ([{"folder_key": "workspace-1"}], 0.0),
        "xet_folder_status_workspace-1": ({"folder_key": "workspace-1"}, 0.0),
        "metrics": ({}, 0.0),
        "global_kpis": ({}, 0.0),
        "peer_metrics": ({}, 0.0),
    }

    provider.invalidate_on_event(EventType.XET_SYNC_PROGRESS, "workspace-1")
    await asyncio.sleep(0.01)

    assert "xet_folders" not in provider._cache
    assert "xet_folder_status_workspace-1" not in provider._cache


@pytest.mark.asyncio
async def test_daemon_provider_media_helpers_surface_candidates_and_status() -> None:
    """Media helpers should filter playable files and expose stream status."""
    client = MagicMock()
    client.get_torrent_files = AsyncMock(
        return_value=SimpleNamespace(
            files=[
                SimpleNamespace(
                    index=0,
                    name="clip.mp4",
                    size=10,
                    selected=True,
                    priority="normal",
                    progress=0.5,
                    attributes=None,
                    path="C:/downloads/clip.mp4",
                    mime_type="video/mp4",
                    is_media=True,
                ),
                SimpleNamespace(
                    index=1,
                    name="notes.txt",
                    size=2,
                    selected=True,
                    priority="normal",
                    progress=1.0,
                    attributes=None,
                    path="C:/downloads/notes.txt",
                    mime_type="text/plain",
                    is_media=False,
                ),
            ]
        )
    )
    client.get_media_stream_status = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda: {
                "stream_id": "stream-1",
                "info_hash": "d" * 40,
                "state": "ready",
            }
        )
    )

    provider = DaemonDataProvider(client)
    candidates = await provider.get_media_candidates("d" * 40)
    status = await provider.get_media_stream_status("d" * 40)

    assert [candidate["name"] for candidate in candidates] == ["clip.mp4"]
    assert status == {
        "stream_id": "stream-1",
        "info_hash": "d" * 40,
        "state": "ready",
    }


@pytest.mark.asyncio
async def test_local_provider_dht_health_summary_exposes_bootstrap_metrics() -> None:
    """Local provider should propagate bootstrap health metrics into DHT summary."""

    class _DummyLock:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

    info_hash = "a" * 40
    info_hash_bytes = bytes.fromhex(info_hash)
    dht_setup = SimpleNamespace(
        _dht_query_metrics={
            "bootstrap_recovery_attempts": 3,
            "bootstrap_health_state": "degraded",
            "bootstrap_zero_state_count": 2,
            "bootstrap_zero_nodes_last_reason": "empty_routing_table",
            "rebootstrap_attempt_count": 4,
            "rebootstrap_success_count": 1,
            "rebootstrap_failure_count": 3,
            "rebootstrap_last_outcome": "failure",
            "rebootstrap_last_reason": "summary",
            "rebootstrap_last_source": "rebootstrap",
            "rebootstrap_health_state": "degraded",
            "rebootstrap_consecutive_failures": 3,
            "bootstrap_success_count": 0,
            "bootstrap_failure_count": 1,
            "query_depths": [2, 3],
            "nodes_queried": [8, 12],
            "total_queries": 5,
            "total_peers_found": 1,
            "last_query": {"duration": 0.2, "peers_found": 0, "depth": 2, "nodes_queried": 4},
            "last_bootstrap_reason": "",
            "last_bootstrap_failure_reason": "",
            "last_zero_node_lookup_at": 0.0,
        },
        _aggressive_mode=False,
    )
    torrent_session = SimpleNamespace(
        _dht_setup=dht_setup,
        dht_client=SimpleNamespace(routing_table=SimpleNamespace(nodes=[1, 2, 3])),
    )
    session = MagicMock()
    session.lock = _DummyLock()
    session.torrents = {info_hash_bytes: torrent_session}
    session.get_status = AsyncMock(
        return_value={
            info_hash: {
                "info_hash": info_hash,
                "name": "sample",
                "status": "downloading",
                "progress": 0.1,
                "download_rate": 1.0,
                "upload_rate": 0.0,
                "connected_peers": 1,
                "active_peers": 0,
                "total_size": 100,
                "downloaded": 10,
                "uploaded": 0,
                "pieces_completed": 1,
                "pieces_total": 10,
            }
        }
    )

    provider = LocalDataProvider(session)
    summary = await provider.get_dht_health_summary()

    assert summary["total_bootstrap_recovery_attempts"] == 3
    assert summary["total_bootstrap_zero_state_count"] == 2
    assert summary["bootstrap_health_state"] == "degraded"
    item = summary["all_items"][0]
    assert item["bootstrap_recovery_attempts"] == 3
    assert item["bootstrap_health_state"] == "degraded"
    assert item["bootstrap_zero_nodes_last_reason"] == "empty_routing_table"


@pytest.mark.asyncio
async def test_daemon_provider_invalidates_media_caches_on_media_events() -> None:
    """Media events should clear targeted media-related cache entries."""
    provider = DaemonDataProvider(MagicMock())
    info_hash = "e" * 40
    provider._cache = {
        f"media_status_{info_hash}": ({"state": "buffering"}, 0.0),
        f"torrent_status_{info_hash}": ({"progress": 0.5}, 0.0),
        f"torrent_files_{info_hash}": ([{"index": 0}], 0.0),
        "metrics": ({}, 0.0),
        "global_kpis": ({}, 0.0),
    }

    provider.invalidate_on_event(EventType.MEDIA_STREAM_READY, info_hash)
    await asyncio.sleep(0.01)

    assert f"media_status_{info_hash}" not in provider._cache
    assert f"torrent_status_{info_hash}" not in provider._cache
    assert f"torrent_files_{info_hash}" not in provider._cache


def test_ui_snapshot_response_shape() -> None:
    """UISnapshotResponse must have global_stats, torrents, services_status, rate_samples."""
    from ccbt.daemon.ipc_protocol import UISnapshotResponse

    empty = UISnapshotResponse()
    assert "global_stats" in empty.model_dump()
    assert "torrents" in empty.model_dump()
    assert "services_status" in empty.model_dump()
    assert "rate_samples" in empty.model_dump()
    assert isinstance(empty.global_stats, dict)
    assert isinstance(empty.torrents, list)
    assert isinstance(empty.rate_samples, list)

    filled = UISnapshotResponse(
        global_stats={"num_torrents": 1, "download_rate": 0.0},
        torrents=[{"info_hash": "a" * 40, "name": "x"}],
        services_status={"services": {"dht": {"enabled": True}}},
        rate_samples=[{"timestamp": 0.0, "download_rate": 0.0, "upload_rate": 0.0}],
    )
    assert filled.global_stats["num_torrents"] == 1
    assert len(filled.torrents) == 1
    assert len(filled.rate_samples) == 1


@pytest.mark.asyncio
async def test_daemon_provider_get_ui_snapshot_returns_canonical_keys() -> None:
    """DaemonDataProvider.get_ui_snapshot returns dict with global_stats, torrents, services_status, rate_samples."""
    from ccbt.daemon.ipc_protocol import UISnapshotResponse

    client = MagicMock()
    client.get_ui_snapshot = AsyncMock(
        return_value=UISnapshotResponse(
            global_stats={"num_torrents": 0, "download_rate": 0.0, "upload_rate": 0.0},
            torrents=[],
            services_status={},
            rate_samples=[],
        )
    )
    provider = DaemonDataProvider(client)
    snapshot = await provider.get_ui_snapshot()
    assert isinstance(snapshot, dict)
    assert "global_stats" in snapshot
    assert "torrents" in snapshot
    assert "services_status" in snapshot
    assert "rate_samples" in snapshot
    client.get_ui_snapshot.assert_awaited()
