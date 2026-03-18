"""Unit tests for MetricsCollector connection stats and performance_data connection_success_rate.

Covers get_connection_stats(), running totals (O(1) global rate), FIFO eviction of per-peer
dicts, and the wiring of performance_data["connection_success_rate"] in _collect_performance_metrics_impl().
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ccbt.monitoring.metrics_collector import MetricsCollector


class TestRunningTotalsAndGlobalRate:
    """Tests for running totals and O(1) global rate."""

    @pytest.mark.asyncio
    async def test_get_connection_success_rate_none_matches_running_totals(self):
        """get_connection_success_rate(None) returns rate from running totals."""
        collector = MetricsCollector()
        await collector.record_connection_attempt("a")
        await collector.record_connection_success("a")
        await collector.record_connection_attempt("b")
        global_rate = await collector.get_connection_success_rate(None)
        assert global_rate == 0.5  # 1 success, 2 attempts
        rate, total = await collector.get_connection_stats()
        assert rate == global_rate
        assert total == 2


class TestFIFOEviction:
    """Tests for bounded per-peer dicts and FIFO eviction."""

    @pytest.mark.asyncio
    async def test_eviction_keeps_dict_size_at_cap_and_global_rate_correct(self):
        """When over cap, oldest key is evicted; global rate and total remain correct."""
        collector = MetricsCollector()
        collector._connection_stats_max_peers = 2
        await collector.record_connection_attempt("p1")
        await collector.record_connection_success("p1")
        await collector.record_connection_attempt("p2")
        await collector.record_connection_attempt("p3")  # evict p1
        assert len(collector._connection_attempts) <= 2
        assert len(collector._connection_successes) <= 2
        rate, total_attempts = await collector.get_connection_stats()
        assert total_attempts == 3
        assert rate == pytest.approx(1 / 3)  # 1 success, 3 attempts

    @pytest.mark.asyncio
    async def test_evicted_peer_returns_zero_rate(self):
        """Per-peer rate for an evicted peer_key returns 0.0."""
        collector = MetricsCollector()
        collector._connection_stats_max_peers = 2
        await collector.record_connection_attempt("old")
        await collector.record_connection_success("old")
        await collector.record_connection_attempt("p2")
        await collector.record_connection_attempt("p3")  # evict "old"
        per_peer_old = await collector.get_connection_success_rate("old")
        assert per_peer_old == 0.0
        per_peer_p2 = await collector.get_connection_success_rate("p2")
        assert per_peer_p2 == 0.0  # 0 successes for p2
        per_peer_p3 = await collector.get_connection_success_rate("p3")
        assert per_peer_p3 == 0.0  # 0 successes for p3


class TestGetConnectionStats:
    """Tests for get_connection_stats()."""

    @pytest.mark.asyncio
    async def test_no_attempts_returns_zero_rate_and_zero_count(self):
        """When no connection attempts recorded, returns (0.0, 0)."""
        collector = MetricsCollector()
        rate, total_attempts = await collector.get_connection_stats()
        assert rate == 0.0
        assert total_attempts == 0

    @pytest.mark.asyncio
    async def test_with_attempts_and_successes_returns_correct_rate_and_count(self):
        """With attempts and successes, returns correct rate (0-1) and total_attempts."""
        collector = MetricsCollector()
        await collector.record_connection_attempt("peer1")
        await collector.record_connection_attempt("peer2")
        await collector.record_connection_success("peer1")
        # peer2: attempt but no success -> 1/2 = 0.5
        rate, total_attempts = await collector.get_connection_stats()
        assert total_attempts == 2
        assert rate == 0.5

    @pytest.mark.asyncio
    async def test_all_successes_returns_one(self):
        """When all attempts succeed, rate is 1.0."""
        collector = MetricsCollector()
        await collector.record_connection_attempt("p1")
        await collector.record_connection_success("p1")
        rate, total_attempts = await collector.get_connection_stats()
        assert total_attempts == 1
        assert rate == 1.0

    @pytest.mark.asyncio
    async def test_all_failures_returns_zero_rate(self):
        """When all attempts fail (no successes), rate is 0.0."""
        collector = MetricsCollector()
        await collector.record_connection_attempt("p1")
        await collector.record_connection_attempt("p2")
        rate, total_attempts = await collector.get_connection_stats()
        assert total_attempts == 2
        assert rate == 0.0


class TestPerformanceDataConnectionSuccessRate:
    """Tests for performance_data['connection_success_rate'] in _collect_performance_metrics_impl."""

    def _make_session_with_torrents(
        self,
        *,
        num_connections: int = 0,
        num_queued_peers: int = 0,
    ) -> MagicMock:
        """Build a mock session with torrents that have peer_manager and _queued_peers."""
        mock_session = MagicMock()
        mock_torrent = MagicMock()
        mock_peer_manager = MagicMock()
        mock_peer_manager.connections = [MagicMock()] * num_connections
        mock_torrent.peer_manager = mock_peer_manager
        mock_torrent.download_manager = None
        mock_torrent._queued_peers = [MagicMock()] * num_queued_peers
        mock_session.torrents = {"tid": mock_torrent}
        mock_session._sessions = None
        return mock_session

    @pytest.mark.asyncio
    async def test_real_rate_used_when_attempts_recorded(self):
        """When at least one connection attempt is recorded, performance_data uses real global rate."""
        collector = MetricsCollector()
        await collector.record_connection_attempt("a")
        await collector.record_connection_success("a")
        await collector.record_connection_attempt("b")
        # 1 success, 2 attempts -> 50%
        mock_session = self._make_session_with_torrents(
            num_connections=1,
            num_queued_peers=2,
        )
        collector.set_session(mock_session)
        await collector.collect_performance_metrics()

        assert collector.performance_data["total_connection_attempts"] == 2
        assert collector.performance_data["connection_success_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_heuristic_used_when_zero_attempts_and_connections(self):
        """When zero attempts but session has connections/queued, heuristic is used."""
        collector = MetricsCollector()
        mock_session = self._make_session_with_torrents(
            num_connections=3,
            num_queued_peers=2,
        )
        collector.set_session(mock_session)
        await collector.collect_performance_metrics()

        assert collector.performance_data["total_connection_attempts"] == 0
        # Heuristic: 3 / (3+2) * 100 = 60.0
        assert collector.performance_data["connection_success_rate"] == 60.0

    @pytest.mark.asyncio
    async def test_zero_attempts_zero_connections_sets_zero_rate(self):
        """When zero attempts and no connections/queued, connection_success_rate is 0.0."""
        collector = MetricsCollector()
        mock_session = self._make_session_with_torrents(
            num_connections=0,
            num_queued_peers=0,
        )
        collector.set_session(mock_session)
        await collector.collect_performance_metrics()

        assert collector.performance_data["total_connection_attempts"] == 0
        assert collector.performance_data["connection_success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_zero_attempts_only_queued_sets_zero_rate(self):
        """When zero attempts and only queued peers (no active connections), rate is 0.0."""
        collector = MetricsCollector()
        mock_session = self._make_session_with_torrents(
            num_connections=0,
            num_queued_peers=5,
        )
        collector.set_session(mock_session)
        await collector.collect_performance_metrics()

        assert collector.performance_data["total_connection_attempts"] == 0
        assert collector.performance_data["connection_success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_performance_metrics_returns_connection_success_rate(self):
        """get_performance_metrics() returns the same connection_success_rate as performance_data."""
        collector = MetricsCollector()
        await collector.record_connection_attempt("x")
        await collector.record_connection_success("x")
        mock_session = self._make_session_with_torrents(num_connections=1, num_queued_peers=0)
        collector.set_session(mock_session)
        await collector.collect_performance_metrics()

        perf = collector.get_performance_metrics()
        assert perf["connection_success_rate"] == 100.0
        assert perf["total_connection_attempts"] == 1
