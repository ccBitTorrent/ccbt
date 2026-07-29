"""Concurrency and ordering guarantees for magnet registration (P4-W2).

Proves ``add_magnet`` registers the session in ``torrents`` under the canonical
info-hash key before ``on_torrent_added`` / background startup observers need it,
and that duplicate concurrent adds are serialized by ``AsyncSessionManager.lock``.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from ccbt.core.magnet import MagnetInfo
from ccbt.session.session import AsyncSessionManager

_PIECES_EMPTY = {"piece_length": 0, "num_pieces": 0, "piece_hashes": []}


async def _started_manager(tmp_path):
    manager = AsyncSessionManager(output_dir=str(tmp_path))
    manager.config.nat.auto_map_ports = False
    manager.config.discovery.enable_dht = False
    manager.config.network.enable_tcp = False
    await manager.start()
    return manager


@pytest.mark.asyncio
async def test_add_magnet_registration_visible_before_background_proceeds(
    tmp_path,
) -> None:
    """Lookup succeeds once ``add_torrent_background`` has been entered."""
    manager = await _started_manager(tmp_path)
    info_hash = b"\x00" * 20
    magnet_uri = f"magnet:?xt=urn:btih:{info_hash.hex()}&dn=Test"
    bg_entered = asyncio.Event()
    bg_proceed = asyncio.Event()

    real_add = manager.torrent_addition_handler.add_torrent_background

    async def slowing_add(session, ih, resume):
        bg_entered.set()
        await bg_proceed.wait()
        return await real_add(session, ih, resume)

    manager.torrent_addition_handler.add_torrent_background = slowing_add  # type: ignore[method-assign]

    try:
        with patch("ccbt.session.session.parse_magnet") as mock_parse, patch(
            "ccbt.session.session.build_minimal_torrent_data"
        ) as mock_build:
            mock_parse.return_value = MagnetInfo(
                info_hash=info_hash,
                display_name="Test",
                swarm_id=None,
                trackers=[],
                web_seeds=[],
            )
            mock_build.return_value = {
                "info_hash": info_hash,
                "name": "Test",
                "file_info": {"total_length": 0},
                "pieces_info": _PIECES_EMPTY,
            }
            add_task = asyncio.create_task(manager.add_magnet(magnet_uri))
            await asyncio.wait_for(bg_entered.wait(), timeout=2.0)

            resolved = await manager.get_session_for_info_hash(info_hash)
            assert resolved is not None
            assert resolved.info.info_hash == info_hash
            assert await manager.metadata_pending_for_info_hash(info_hash) is True

            bg_proceed.set()
            await asyncio.wait_for(add_task, timeout=5.0)
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_add_magnet_on_torrent_added_sees_registered_session(tmp_path) -> None:
    """Callback runs after registry insert; async callback can resolve the session."""
    manager = await _started_manager(tmp_path)
    info_hash = b"\x11" * 20
    magnet_uri = f"magnet:?xt=urn:btih:{info_hash.hex()}&dn=Cb"
    checked = False

    async def on_added(ih: bytes, name: str) -> None:
        nonlocal checked
        s = await manager.get_session_for_info_hash(ih)
        assert s is not None
        assert s.info.info_hash == ih
        assert name == "Cb"
        checked = True

    manager.on_torrent_added = on_added

    try:
        with patch("ccbt.session.session.parse_magnet") as mock_parse, patch(
            "ccbt.session.session.build_minimal_torrent_data"
        ) as mock_build:
            mock_parse.return_value = MagnetInfo(
                info_hash=info_hash,
                display_name="Cb",
                swarm_id=None,
                trackers=[],
                web_seeds=[],
            )
            mock_build.return_value = {
                "info_hash": info_hash,
                "name": "Cb",
                "file_info": {"total_length": 0},
                "pieces_info": _PIECES_EMPTY,
            }
            await manager.add_magnet(magnet_uri)
        assert checked is True
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_add_magnet_concurrent_duplicate_one_wins(tmp_path) -> None:
    """Two parallel adds for the same hash: one success, one ``already exists``."""
    manager = await _started_manager(tmp_path)
    info_hash = b"\xaa" * 20
    magnet_uri = f"magnet:?xt=urn:btih:{info_hash.hex()}&dn=Dup"

    try:
        with patch("ccbt.session.session.parse_magnet") as mock_parse, patch(
            "ccbt.session.session.build_minimal_torrent_data"
        ) as mock_build:
            mock_parse.return_value = MagnetInfo(
                info_hash=info_hash,
                display_name="Dup",
                swarm_id=None,
                trackers=[],
                web_seeds=[],
            )
            mock_build.return_value = {
                "info_hash": info_hash,
                "name": "Dup",
                "file_info": {"total_length": 0},
                "pieces_info": _PIECES_EMPTY,
            }
            t1 = asyncio.create_task(manager.add_magnet(magnet_uri))
            t2 = asyncio.create_task(manager.add_magnet(magnet_uri))
            r1, r2 = await asyncio.gather(t1, t2, return_exceptions=True)

        errs = [r for r in (r1, r2) if isinstance(r, BaseException)]
        oks = [r for r in (r1, r2) if not isinstance(r, BaseException)]
        assert len(oks) == 1
        assert len(errs) == 1
        assert isinstance(errs[0], ValueError)
        assert "already exists" in str(errs[0])
        assert len(manager.torrents) == 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_add_magnet_concurrent_distinct_hashes(tmp_path) -> None:
    """Parallel adds for different info hashes both register."""
    manager = await _started_manager(tmp_path)
    h1 = b"\x01" + b"\x00" * 19
    h2 = b"\x02" + b"\x00" * 19

    try:
        with patch("ccbt.session.session.parse_magnet") as mock_parse, patch(
            "ccbt.session.session.build_minimal_torrent_data"
        ) as mock_build:
            uri_by_hash = {
                h1.hex(): f"magnet:?xt=urn:btih:{h1.hex()}&dn=A",
                h2.hex(): f"magnet:?xt=urn:btih:{h2.hex()}&dn=B",
            }

            def parse_side_effect(uri: str) -> MagnetInfo:
                for hb, u in uri_by_hash.items():
                    if uri == u:
                        return MagnetInfo(
                            info_hash=bytes.fromhex(hb),
                            display_name="A" if hb.startswith("01") else "B",
                            swarm_id=None,
                            trackers=[],
                            web_seeds=[],
                        )
                msg = f"unexpected uri {uri}"
                raise AssertionError(msg)

            mock_parse.side_effect = parse_side_effect

            def build_side_effect(
                ih: bytes,
                name: str,
                _trackers: list,
                _web_seeds: list,
            ):
                return {
                    "info_hash": ih,
                    "name": name,
                    "file_info": {"total_length": 0},
                    "pieces_info": _PIECES_EMPTY,
                }

            mock_build.side_effect = build_side_effect

            await asyncio.gather(
                manager.add_magnet(uri_by_hash[h1.hex()]),
                manager.add_magnet(uri_by_hash[h2.hex()]),
            )

        assert set(manager.torrents.keys()) == {h1, h2}
        assert await manager.get_session_for_info_hash(h1) is not None
        assert await manager.get_session_for_info_hash(h2) is not None
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_add_magnet_canonical_key_duplicate_after_normalize(tmp_path) -> None:
    """Non-20-byte raw btih normalizes to the same key as explicit 20-byte form."""
    manager = await _started_manager(tmp_path)
    short = b"\xde\xad"
    canonical = short + b"\x00" * (20 - len(short))
    uri_short = "magnet:?xt=urn:btih:short&dn=X"
    uri_full = f"magnet:?xt=urn:btih:{canonical.hex()}&dn=Y"

    try:
        with patch("ccbt.session.session.parse_magnet") as mock_parse, patch(
            "ccbt.session.session.build_minimal_torrent_data"
        ) as mock_build:

            def parse_side_effect(uri: str) -> MagnetInfo:
                if uri == uri_short:
                    return MagnetInfo(
                        info_hash=short,
                        display_name="X",
                        swarm_id=None,
                        trackers=[],
                        web_seeds=[],
                    )
                if uri == uri_full:
                    return MagnetInfo(
                        info_hash=canonical,
                        display_name="Y",
                        swarm_id=None,
                        trackers=[],
                        web_seeds=[],
                    )
                msg = f"unexpected uri {uri}"
                raise AssertionError(msg)

            mock_parse.side_effect = parse_side_effect

            def build_side_effect(
                ih: bytes,
                name: str,
                _trackers: list,
                _web_seeds: list,
            ):
                return {
                    "info_hash": ih,
                    "name": name,
                    "file_info": {"total_length": 0},
                    "pieces_info": _PIECES_EMPTY,
                }

            mock_build.side_effect = build_side_effect

            await manager.add_magnet(uri_short)
            with pytest.raises(ValueError, match="already exists"):
                await manager.add_magnet(uri_full)
        assert len(manager.torrents) == 1
    finally:
        await manager.stop()
