"""Aux-metrics worker tests (F2.6)."""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
from ccbt.interface.terminal_dashboard import TerminalDashboard

pytestmark = [pytest.mark.unit, pytest.mark.interface]


def _make_app() -> TerminalDashboard:
    mock_ipc_client = MagicMock()
    mock_ipc_client.is_daemon_running = AsyncMock(return_value=True)
    mock_ipc_client.connect_websocket = AsyncMock(return_value=True)
    mock_ipc_client.subscribe_events = AsyncMock()
    mock_ipc_client._websocket_task = None
    session = DaemonInterfaceAdapter(mock_ipc_client)
    return TerminalDashboard(session, refresh_interval=0.5)


@pytest.mark.asyncio
async def test_refresh_aux_metrics_impl_sets_all_reactives() -> None:
    """_refresh_aux_metrics_impl assigns all seven aux reactives (F2.6.1)."""
    app = _make_app()
    dp = MagicMock()
    dp.get_global_kpis = AsyncMock(return_value={"overall_efficiency": 0.5})
    dp.get_dht_health_summary = AsyncMock(return_value={"overall_health": 0.8})
    dp.get_peer_quality_distribution = AsyncMock(return_value={"buckets": []})
    dp.get_disk_io_metrics = AsyncMock(return_value={"read_rate": 1})
    dp.get_system_metrics = AsyncMock(return_value={"cpu_usage": 0.1})
    dp.get_rate_samples = AsyncMock(return_value=[{"timestamp": 1.0, "download_rate": 100.0}])
    dp.get_network_timing_metrics = AsyncMock(return_value={"latency_ms": 5.0})
    app._data_provider = dp

    await app._refresh_aux_metrics_impl()

    dp.get_global_kpis.assert_awaited_once()
    dp.get_dht_health_summary.assert_awaited_once()
    dp.get_peer_quality_distribution.assert_awaited_once()
    dp.get_disk_io_metrics.assert_awaited_once()
    dp.get_system_metrics.assert_awaited_once()
    dp.get_rate_samples.assert_awaited_once_with(60)
    dp.get_network_timing_metrics.assert_awaited_once()

    assert app.global_kpis == {"overall_efficiency": 0.5}
    assert app.dht_health_summary == {"overall_health": 0.8}
    assert app.peer_quality_distribution == {"buckets": []}
    assert app.disk_io_metrics == {"read_rate": 1}
    assert app.system_metrics == {"cpu_usage": 0.1}
    assert app.rate_samples == [{"timestamp": 1.0, "download_rate": 100.0}]
    assert app.network_quality == {"latency_ms": 5.0}


def test_aux_metrics_worker_is_exclusive_in_aux_metrics_group() -> None:
    """_refresh_aux_metrics must be @work(exclusive=True, group='aux_metrics') (F2.6.1)."""
    assert inspect.iscoroutinefunction(TerminalDashboard._refresh_aux_metrics_impl)
    assert TerminalDashboard._refresh_aux_metrics is not TerminalDashboard._refresh_aux_metrics_impl

    app = TerminalDashboard.__new__(TerminalDashboard)
    captured: dict[str, Any] = {}

    def fake_run_worker(_func: Any, *, name: str, group: str, description: str, exclusive: bool, exit_on_error: bool, thread: bool) -> Any:
        captured["group"] = group
        captured["exclusive"] = exclusive
        return MagicMock()

    app.run_worker = fake_run_worker  # type: ignore[assignment]
    app._refresh_aux_metrics()  # type: ignore[func-returns-value]

    assert captured["group"] == "aux_metrics"
    assert captured["exclusive"] is True
