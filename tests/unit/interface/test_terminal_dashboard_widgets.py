"""Tests for terminal dashboard widget update methods.

Focus:
- Widget update methods that don't require full Textual context
- update_from_stats, update_from_status, update_from_peers
- get_selected_info_hash
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from ccbt.interface.terminal_dashboard import (
    Overview,
    PeersTable,
    SpeedSparklines,
    TorrentsTable,
)


@pytest.fixture
def mock_static_widget():
    """Create a mock Static widget that can be updated."""
    widget = MagicMock(spec=["update"])
    widget.update = MagicMock()
    return widget


@pytest.fixture
def mock_datatable_widget():
    """Create a mock DataTable widget."""
    widget = MagicMock(spec=["clear", "add_columns", "add_row", "cursor_row_key"])
    widget.clear = MagicMock()
    widget.add_columns = MagicMock()
    widget.add_row = MagicMock()
    widget.cursor_row_key = None
    return widget


def test_overview_update_from_stats(mock_static_widget):
    """Test Overview.update_from_stats."""
    overview = Overview()
    overview.update = mock_static_widget.update

    stats = {
        "num_torrents": 5,
        "num_active": 3,
        "num_paused": 1,
        "num_seeding": 1,
        "download_rate": 1024.5,
        "upload_rate": 512.3,
        "average_progress": 0.75,
    }

    overview.update_from_stats(stats)

    assert mock_static_widget.update.called
    call_args = mock_static_widget.update.call_args[0][0]
    assert hasattr(call_args, "renderable")


def test_overview_update_from_stats_partial():
    """Test Overview.update_from_stats with partial stats."""
    overview = Overview()
    overview.update = MagicMock()

    stats = {"num_torrents": 2}
    overview.update_from_stats(stats)

    assert overview.update.called


def test_torrents_table_update_from_status(mock_datatable_widget):
    """Test TorrentsTable.update_from_status."""
    table = TorrentsTable()
    table.clear = mock_datatable_widget.clear
    table.add_row = mock_datatable_widget.add_row

    status = {
        "hash1": {
            "name": "Test Torrent 1",
            "status": "downloading",
            "progress": 0.5,
            "download_rate": 1024.0,
            "upload_rate": 256.0,
        },
        "hash2": {
            "name": "Test Torrent 2",
            "status": "seeding",
            "progress": 1.0,
            "download_rate": 0.0,
            "upload_rate": 512.0,
        },
    }

    table.update_from_status(status)

    assert mock_datatable_widget.clear.called
    assert mock_datatable_widget.add_row.call_count == 2


def test_torrents_table_get_selected_info_hash_with_key():
    """Test TorrentsTable.get_selected_info_hash when cursor_row_key exists."""
    table = TorrentsTable()
    table.cursor_row_key = "hash123"

    result = table.get_selected_info_hash()

    assert result == "hash123"


def test_torrents_table_get_selected_info_hash_no_key():
    """Test TorrentsTable.get_selected_info_hash when cursor_row_key is None."""
    table = TorrentsTable()
    table.cursor_row_key = None

    result = table.get_selected_info_hash()

    assert result is None


def test_torrents_table_get_selected_info_hash_no_attr():
    """Test TorrentsTable.get_selected_info_hash when cursor_row_key attr doesn't exist."""
    table = TorrentsTable()
    delattr(table, "cursor_row_key") if hasattr(table, "cursor_row_key") else None

    result = table.get_selected_info_hash()

    assert result is None


def test_peers_table_update_from_peers(mock_datatable_widget):
    """Test PeersTable.update_from_peers."""
    table = PeersTable()
    table.clear = mock_datatable_widget.clear
    table.add_row = mock_datatable_widget.add_row

    peers = [
        {
            "ip": "192.168.1.1",
            "port": 6881,
            "download_rate": 1024.0,
            "upload_rate": 256.0,
            "choked": False,
            "client": "uTorrent",
            "request_latency": 0.05,  # 50ms
        },
        {
            "ip": "192.168.1.2",
            "port": 6882,
            "download_rate": 512.0,
            "upload_rate": 128.0,
            "choked": True,
            "client": "qBittorrent",
            "request_latency": 0.1,  # 100ms
        },
    ]

    table.update_from_peers(peers)

    assert mock_datatable_widget.clear.called
    assert mock_datatable_widget.add_row.call_count == 2
    
    # Verify that add_row was called with correct number of columns (IP, Port, Down, Up, Latency, Quality, Health, Choked, Client)
    call_args = mock_datatable_widget.add_row.call_args_list[0][0]
    assert len(call_args) == 9  # 9 columns


def test_peers_table_calculate_connection_quality():
    """Test PeersTable._calculate_connection_quality."""
    from ccbt.interface.terminal_dashboard import PeersTable
    
    table = PeersTable()
    
    # Test high quality peer (unchoked, high speed)
    peer1 = {
        "download_rate": 1024 * 1024,  # 1 MB/s
        "upload_rate": 512 * 1024,  # 512 KB/s
        "choked": False,
    }
    quality1 = table._calculate_connection_quality(peer1)
    assert 0.0 <= quality1 <= 100.0
    assert quality1 >= 50.0  # Should be high due to unchoked and speed
    
    # Test low quality peer (choked, low speed)
    peer2 = {
        "download_rate": 100.0,
        "upload_rate": 50.0,
        "choked": True,
    }
    quality2 = table._calculate_connection_quality(peer2)
    assert 0.0 <= quality2 <= 100.0
    assert quality2 < quality1  # Should be lower than peer1


def test_peers_table_format_quality_indicator():
    """Test PeersTable._format_quality_indicator."""
    from ccbt.interface.terminal_dashboard import PeersTable
    
    table = PeersTable()
    
    # Test excellent quality
    result1 = table._format_quality_indicator(85.0)
    assert "85" in result1
    assert "%" in result1
    assert "green" in result1.lower() or "[green]" in result1
    
    # Test poor quality
    result2 = table._format_quality_indicator(30.0)
    assert "30" in result2
    assert "%" in result2
    assert "red" in result2.lower() or "[red]" in result2


def test_peers_table_get_health_status():
    """Test PeersTable._get_health_status."""
    from ccbt.interface.terminal_dashboard import PeersTable
    
    table = PeersTable()
    
    # Test excellent health
    status1 = table._get_health_status(85.0)
    assert "Excellent" in status1 or "excellent" in status1.lower()
    
    # Test poor health
    status2 = table._get_health_status(30.0)
    assert "Poor" in status2 or "poor" in status2.lower()


def test_peers_table_update_from_peers_empty():
    """Test PeersTable.update_from_peers with empty list."""
    table = PeersTable()
    table.clear = MagicMock()
    table.add_row = MagicMock()

    table.update_from_peers([])

    assert table.clear.called
    assert not table.add_row.called


def test_peers_table_update_from_peers_none():
    """Test PeersTable.update_from_peers with None."""
    table = PeersTable()
    table.clear = MagicMock()
    table.add_row = MagicMock()

    table.update_from_peers(None)

    assert table.clear.called
    assert not table.add_row.called


def test_speed_sparklines_update_from_stats():
    """Test SpeedSparklines.update_from_stats."""
    sparklines = SpeedSparklines()
    sparklines._down_history = []
    sparklines._up_history = []
    sparklines._down = MagicMock(spec=["data"])
    sparklines._up = MagicMock(spec=["data"])

    stats = {"download_rate": 1024.5, "upload_rate": 512.3}
    sparklines.update_from_stats(stats)

    assert len(sparklines._down_history) == 1
    assert len(sparklines._up_history) == 1
    assert sparklines._down_history[0] == 1024.5
    assert sparklines._up_history[0] == 512.3


def test_speed_sparklines_update_from_stats_history_limit():
    """Test SpeedSparklines.update_from_stats maintains history limit."""
    sparklines = SpeedSparklines()
    sparklines._down_history = [1.0] * 120
    sparklines._up_history = [2.0] * 120
    sparklines._down = MagicMock(spec=["data"])
    sparklines._up = MagicMock(spec=["data"])

    stats = {"download_rate": 1024.5, "upload_rate": 512.3}
    sparklines.update_from_stats(stats)

    assert len(sparklines._down_history) == 120
    assert len(sparklines._up_history) == 120
    assert sparklines._down_history[-1] == 1024.5
    assert sparklines._up_history[-1] == 512.3









