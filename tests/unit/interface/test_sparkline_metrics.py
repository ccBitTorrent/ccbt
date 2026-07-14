"""Sparkline normalization and rate alias tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ccbt.interface.widgets.core_widgets import _get_rate
from ccbt.interface.widgets.graph_widget import (
    _format_kib_rate_label,
    _smooth_append,
    _sparkline_display_values,
)
from ccbt.session.session import AsyncSessionManager

pytestmark = [pytest.mark.unit, pytest.mark.interface]


def test_sparkline_display_values_empty_is_flat_baseline() -> None:
    assert _sparkline_display_values([]) == [0.0, 0.0]


def test_sparkline_display_values_normalizes_shape() -> None:
    normalized = _sparkline_display_values([0.0, 50.0, 100.0, 25.0])
    assert normalized[0] == 0.0
    assert normalized[2] == 1.0
    assert normalized[1] == 0.5


def test_sparkline_display_values_all_zero_stays_flat() -> None:
    assert _sparkline_display_values([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]


def test_get_rate_uses_total_download_alias() -> None:
    stats = {"download_rate": 0.0, "total_download_rate": 4096.0}
    assert _get_rate(stats, "download_rate") == 4096.0


def test_format_kib_rate_label() -> None:
    assert _format_kib_rate_label(0.0) == "0.00 KiB/s"
    assert _format_kib_rate_label(512.0) == "512.00 KiB/s"
    assert _format_kib_rate_label(2048.0) == "2.00 MiB/s"


def test_smooth_append_applies_ema() -> None:
    history: list[float] = [10.0]
    _smooth_append(history, 20.0, alpha=0.5)
    assert history == [10.0, 15.0]


def testlive_transfer_rates_from_download_manager() -> None:
    torrent = SimpleNamespace(
        _cached_status={},
        download_manager=SimpleNamespace(
            _calculate_rates=lambda: (8192.0, 1024.0),
        ),
    )
    down, up = AsyncSessionManager.live_transfer_rates(torrent, {})
    assert down == 8192.0
    assert up == 1024.0


def testlive_transfer_rates_sums_active_peer_stats() -> None:
    peer = SimpleNamespace(
        stats=SimpleNamespace(download_rate=2048.0, upload_rate=512.0),
    )
    torrent = SimpleNamespace(
        _cached_status={"download_rate": 0.0, "upload_rate": 0.0},
        download_manager=SimpleNamespace(
            _calculate_rates=lambda: (0.0, 0.0),
            peer_manager=SimpleNamespace(
                get_active_peers=lambda: [peer],
            ),
        ),
    )
    down, up = AsyncSessionManager.live_transfer_rates(torrent, torrent._cached_status)
    assert down == 2048.0
    assert up == 512.0


def test_live_torrent_progress_uses_piece_manager() -> None:
    torrent = SimpleNamespace(
        piece_manager=SimpleNamespace(get_download_progress=lambda: 0.42),
    )
    assert AsyncSessionManager._live_torrent_progress(torrent, 0.0) == 0.42


def test_resolve_torrent_peer_manager_prefers_download_manager() -> None:
    nested = SimpleNamespace(peer_manager="nested")
    torrent = SimpleNamespace(
        download_manager=nested,
        peer_manager="top-level",
    )
    assert AsyncSessionManager._resolve_torrent_peer_manager(torrent) == "nested"


def testlive_transfer_rates_prefers_cached_status() -> None:
    torrent = SimpleNamespace(
        download_manager=SimpleNamespace(
            _calculate_rates=lambda: (100.0, 100.0),
        ),
    )
    payload = {"download_rate": 5000.0, "upload_rate": 2500.0}
    down, up = AsyncSessionManager.live_transfer_rates(torrent, payload)
    assert down == 5000.0
    assert up == 2500.0
