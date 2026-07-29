"""Daemon state restore regression tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.daemon.main import _magnet_uri_for_torrent_state
from ccbt.daemon.state_manager import StateManager

pytestmark = [pytest.mark.unit]


def test_magnet_uri_for_torrent_state_uses_saved_magnet() -> None:
    torrent_state = SimpleNamespace(
        magnet_uri="magnet:?xt=urn:btih:aa",
        torrent_file_path=None,
        info_hash="aa" * 20,
        name="Saved",
    )
    assert _magnet_uri_for_torrent_state(torrent_state) == "magnet:?xt=urn:btih:aa"


def test_magnet_uri_for_torrent_state_falls_back_to_info_hash() -> None:
    info_hash = "3b1244529e5b2a6ead07233738cbbef06ebebb84"
    torrent_state = SimpleNamespace(
        magnet_uri=None,
        torrent_file_path=None,
        info_hash=info_hash,
        name="Backrooms",
    )
    magnet_uri = _magnet_uri_for_torrent_state(torrent_state)
    assert magnet_uri is not None
    assert info_hash in magnet_uri
    assert "Backrooms" in magnet_uri
    assert "tr=" in magnet_uri


@pytest.mark.asyncio
async def test_build_state_persists_magnet_uri_from_session(tmp_path) -> None:
    info_hash_hex = "3b1244529e5b2a6ead07233738cbbef06ebebb84"
    magnet_uri = (
        "magnet:?xt=urn:btih:3b1244529e5b2a6ead07233738cbbef06ebebb84&dn=Backrooms"
    )
    torrent_session = SimpleNamespace(
        torrent_file_path=None,
        magnet_uri=magnet_uri,
        output_dir="/downloads/backrooms",
        options={"priority": "high"},
        info=SimpleNamespace(added_time=1234.5),
    )
    session_manager = MagicMock()
    session_manager.is_shutting_down = lambda: False
    session_manager.get_status_summaries_light = AsyncMock(
        return_value={
            info_hash_hex: {
                "name": "Backrooms",
                "status": "downloading",
                "progress": 0.0,
                "connected_peers": 0,
            }
        }
    )
    session_manager.get_global_stats = AsyncMock(return_value={})
    session_manager.acquire_lock_timed = AsyncMock(return_value=True)
    session_manager.release_manager_lock = MagicMock()
    session_manager.torrents = {bytes.fromhex(info_hash_hex): torrent_session}
    session_manager.get_per_torrent_limits = MagicMock(return_value=None)
    session_manager.config = SimpleNamespace(
        discovery=SimpleNamespace(enable_dht=False),
        nat=SimpleNamespace(auto_map_ports=False),
    )
    session_manager.dht_client = None
    session_manager.nat_manager = None

    state_manager = StateManager(state_dir=tmp_path)
    state = await state_manager._build_state(session_manager)  # noqa: SLF001

    torrent_state = state.torrents[info_hash_hex]
    assert torrent_state.magnet_uri == magnet_uri
    assert torrent_state.output_dir == "/downloads/backrooms"
    assert torrent_state.added_at == 1234.5
