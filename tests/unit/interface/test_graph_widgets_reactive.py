"""Reactive graph widget tests (F2.5)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ccbt.interface.widgets.graph_widget import (
    DownloadGraphWidget,
    PerTorrentGraphWidget,
    SwarmHealthDotPlot,
    UploadDownloadGraphWidget,
    UploadGraphWidget,
)
from ccbt.interface.widgets.swarm_timeline_widget import SwarmTimelineWidget

pytestmark = [pytest.mark.unit, pytest.mark.interface]


def test_upload_download_graph_declares_reactives() -> None:
    assert hasattr(UploadDownloadGraphWidget, "global_stats")
    assert hasattr(UploadDownloadGraphWidget, "rate_samples")


def test_download_graph_declares_global_stats_reactive() -> None:
    assert hasattr(DownloadGraphWidget, "global_stats")


def test_upload_graph_declares_global_stats_reactive() -> None:
    assert hasattr(UploadGraphWidget, "global_stats")


def test_per_torrent_graph_declares_selected_torrent_status_reactive() -> None:
    assert hasattr(PerTorrentGraphWidget, "selected_torrent_status")


def test_swarm_health_dot_plot_declares_swarm_health_samples_reactive() -> None:
    assert hasattr(SwarmHealthDotPlot, "swarm_health_samples")


def test_swarm_timeline_declares_swarm_health_samples_reactive() -> None:
    assert hasattr(SwarmTimelineWidget, "swarm_health_samples")


def test_upload_download_watch_global_stats_appends_history() -> None:
    widget = UploadDownloadGraphWidget.__new__(UploadDownloadGraphWidget)
    widget._max_samples = 120
    widget._download_history = []
    widget._upload_history = []
    widget._timestamps = []
    widget._update_display = MagicMock()  # type: ignore[assignment]
    widget._update_event_annotations = MagicMock()  # type: ignore[assignment]

    widget.watch_global_stats({"download_rate": 2048.0, "upload_rate": 1024.0})

    assert widget._download_history == [2.0]
    assert widget._upload_history == [1.0]
    widget._update_display.assert_called_once()


def test_upload_download_apply_rate_samples_replaces_history() -> None:
    widget = UploadDownloadGraphWidget.__new__(UploadDownloadGraphWidget)
    widget._max_samples = 120
    widget._download_history = []
    widget._upload_history = []
    widget._timestamps = []
    widget._update_display = MagicMock()  # type: ignore[assignment]
    widget._update_event_annotations = MagicMock()  # type: ignore[assignment]

    samples = [
        {"timestamp": 1.0, "download_rate": 2048.0, "upload_rate": 1024.0},
        {"timestamp": 2.0, "download_rate": 4096.0, "upload_rate": 2048.0},
    ]
    widget._apply_rate_samples(samples)

    assert widget._download_history == [2.0, 4.0]
    assert widget._upload_history == [1.0, 2.0]


def test_download_graph_watch_global_stats_appends() -> None:
    widget = DownloadGraphWidget.__new__(DownloadGraphWidget)
    widget._max_samples = 120
    widget._download_history = []
    widget._update_display = MagicMock()  # type: ignore[assignment]

    widget.watch_global_stats({"download_rate": 1024.0})

    assert widget._download_history == [1.0]


def test_swarm_health_dot_plot_watch_renders_empty_message() -> None:
    widget = SwarmHealthDotPlot.__new__(SwarmHealthDotPlot)
    widget._content = MagicMock()
    widget._legend = MagicMock()

    widget.watch_swarm_health_samples([])

    widget._content.update.assert_called_once_with("No swarm activity yet")
    widget._legend.update.assert_called_once_with("")
