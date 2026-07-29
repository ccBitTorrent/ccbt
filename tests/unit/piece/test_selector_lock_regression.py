"""Regression: nested piece selectors must not run under an outer piece-manager lock."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from ccbt.models import PieceSelectionStrategy
from ccbt.piece.async_piece_manager import AsyncPieceManager

pytestmark = [pytest.mark.unit, pytest.mark.piece]


def _minimal_torrent_dict() -> dict:
    return {
        "info_hash": b"\xab" * 20,
        "file_info": {
            "name": "lock-regression.bin",
            "total_length": 10 * 16384,
            "type": "single",
        },
        "pieces_info": {
            "num_pieces": 10,
            "piece_length": 16384,
            "piece_hashes": [b"\xcd" * 20 for _ in range(10)],
        },
    }


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_adaptive_hybrid_does_not_deadlock_on_piece_lock() -> None:
    """_select_adaptive_hybrid must release lock before awaiting _select_sequential."""
    td = _minimal_torrent_dict()
    pm = AsyncPieceManager(td)
    await pm.start()
    try:
        pm.config.strategy.piece_selection = PieceSelectionStrategy.ADAPTIVE_HYBRID
        pm._metadata_incomplete = False  # noqa: SLF001
        pm._peer_manager = SimpleNamespace(get_active_peers=list)  # noqa: SLF001
        await asyncio.wait_for(pm._select_adaptive_hybrid(), timeout=3.0)  # noqa: SLF001
    finally:
        await pm.stop()


@pytest.mark.asyncio
@pytest.mark.timeout_fast
async def test_progressive_rarest_does_not_deadlock_on_piece_lock() -> None:
    """_select_progressive_rarest must release lock before awaiting child selector."""
    td = _minimal_torrent_dict()
    pm = AsyncPieceManager(td)
    await pm.start()
    try:
        pm.config.strategy.piece_selection = PieceSelectionStrategy.PROGRESSIVE_RAREST
        pm.config.strategy.progressive_rarest_transition_threshold = 0.55
        pm._metadata_incomplete = False  # noqa: SLF001
        pm._peer_manager = SimpleNamespace(get_active_peers=list)  # noqa: SLF001
        await asyncio.wait_for(pm._select_progressive_rarest(), timeout=3.0)  # noqa: SLF001
    finally:
        await pm.stop()
