from __future__ import annotations

import pytest

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
async def test_add_torrent_normalizes_registry_key_for_dict_input(tmp_path) -> None:
    manager = await _started_manager(tmp_path)
    short = b"\xde\xad"
    canonical = short + b"\x00" * (20 - len(short))
    try:
        ih_hex = await manager.add_torrent(
            {
                "info_hash": short,
                "name": "dict-short",
                "file_info": {"total_length": 0},
                "pieces_info": _PIECES_EMPTY,
            }
        )
        assert ih_hex == canonical.hex()
        assert canonical in manager.torrents
        assert await manager.get_session_for_info_hash(canonical) is not None
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_add_torrent_duplicate_detected_for_canonical_equivalent_input(tmp_path) -> None:
    manager = await _started_manager(tmp_path)
    short = b"\xab\xcd"
    canonical = short + b"\x00" * (20 - len(short))
    try:
        await manager.add_torrent(
            {
                "info_hash": short,
                "name": "first",
                "file_info": {"total_length": 0},
                "pieces_info": _PIECES_EMPTY,
            }
        )
        with pytest.raises(ValueError, match="already exists"):
            await manager.add_torrent(
                {
                    "info_hash": canonical,
                    "name": "second",
                    "file_info": {"total_length": 0},
                    "pieces_info": _PIECES_EMPTY,
                }
            )
    finally:
        await manager.stop()
