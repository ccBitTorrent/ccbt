"""Unit tests for interface data providers."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.daemon.ipc_protocol import EventType, TorrentStatusResponse
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
    assert result["num_peers"] == 7
    assert result["num_seeds"] == 3
    session.get_torrent_status.assert_awaited_once_with("a" * 40)
    session.get_status.assert_not_called()


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
async def test_daemon_provider_global_stats_maps_canonical_rates() -> None:
    """Global stats should expose canonical and compatibility rate keys."""
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
    assert stats["total_download_rate"] == 1250.0
    assert stats["total_upload_rate"] == 640.0
    assert stats["connected_peers"] == 7
    assert stats["uptime"] == 12.0


@pytest.mark.asyncio
async def test_local_provider_list_torrents_adds_compat_aliases() -> None:
    """Local torrent lists should expose the same UI-facing aliases as daemon mode."""
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
    assert torrents[0]["num_peers"] == 4
    assert torrents[0]["num_seeds"] == 1


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
    assert daemon_status["num_peers"] == 6


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
