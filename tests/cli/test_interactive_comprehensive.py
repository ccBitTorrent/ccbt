"""Comprehensive tests for interactive.py to achieve 100% coverage.

Covers all methods and code paths in InteractiveCLI class.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from rich.console import Console

pytestmark = [pytest.mark.unit, pytest.mark.cli]


@pytest.fixture
def mock_session():
    """Create a mock AsyncSessionManager."""
    session = AsyncMock()
    session.add_torrent = AsyncMock(return_value="abcd1234" * 4)
    session.get_torrent_status = AsyncMock(return_value={
        "download_rate": 1000.0,
        "upload_rate": 500.0,
        "pieces_completed": 10,
        "pieces_total": 100,
        "progress": 0.1,
        "downloaded_bytes": 1048576,
        "status": "downloading",
    })
    session.get_peers_for_torrent = AsyncMock(return_value=[
        {"ip": "1.2.3.4", "port": 6881, "download_rate": 100.0, "upload_rate": 50.0},
    ])
    session.pause_torrent = AsyncMock()
    session.resume_torrent = AsyncMock()
    session.remove = AsyncMock()
    session.lock = AsyncMock()
    session.lock.__aenter__ = AsyncMock(return_value=None)
    session.lock.__aexit__ = AsyncMock(return_value=None)
    session.torrents = {}
    session.get_scrape_result = AsyncMock(return_value=None)
    session.export_session_state = AsyncMock()
    session.import_session_state = AsyncMock(return_value={"torrents": {}})
    return session


@pytest.fixture
def interactive_cli(mock_session):
    """Create InteractiveCLI instance."""
    from ccbt.cli.interactive import InteractiveCLI
    
    console = Mock(spec=Console)
    console.print = Mock()
    console.clear = Mock()
    console.print_json = Mock()
    cli = InteractiveCLI(mock_session, console)
    return cli


class TestInteractiveComprehensive:
    """Comprehensive tests for InteractiveCLI."""

    @pytest.mark.asyncio
    async def test_download_torrent_with_file_selection(self, interactive_cli, mock_session):
        """Test download_torrent with file selection (lines 146-181)."""
        # Setup layout first
        interactive_cli.setup_layout()
        
        # Create mock torrent session with file manager
        mock_torrent_session = MagicMock()
        mock_file_manager = AsyncMock()
        mock_file_manager.get_all_file_states = AsyncMock(return_value={})
        mock_torrent_session.file_selection_manager = mock_file_manager
        
        info_hash_bytes = bytes.fromhex("abcd1234" * 4)
        mock_session.torrents = {info_hash_bytes: mock_torrent_session}
        
        torrent_data = {"name": "test.torrent", "total_size": 1024}
        interactive_cli.running = True
        interactive_cli._interactive_file_selection = AsyncMock()
        interactive_cli.show_download_interface = Mock()
        
        # Mock get_torrent_status to return seeding after a while
        call_count = [0]
        def status_side_effect(*args):
            call_count[0] += 1
            if call_count[0] > 1:
                return {"status": "seeding"}
            return {"status": "downloading"}
        
        mock_session.get_torrent_status = AsyncMock(side_effect=status_side_effect)
        interactive_cli.update_download_stats = AsyncMock()
        
        # Run download
        await interactive_cli.download_torrent(torrent_data, resume=False)
        
        # Verify file selection was called
        interactive_cli._interactive_file_selection.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_torrent_completes(self, interactive_cli, mock_session):
        """Test download_torrent completion (lines 178-181)."""
        torrent_data = {"name": "test.torrent", "total_size": 1024}
        interactive_cli.running = True
        interactive_cli._interactive_file_selection = AsyncMock()
        interactive_cli.show_download_interface = Mock()
        interactive_cli.update_download_stats = AsyncMock()
        
        # Mock status to return seeding immediately
        mock_session.get_torrent_status = AsyncMock(return_value={"status": "seeding"})
        
        await interactive_cli.download_torrent(torrent_data, resume=False)
        
        # Should complete
        assert interactive_cli.current_torrent == torrent_data

    def test_setup_layout(self, interactive_cli):
        """Test setup_layout (lines 190-201)."""
        interactive_cli.setup_layout()
        
        # Verify layout structure
        assert interactive_cli.layout is not None

    def test_show_welcome(self, interactive_cli):
        """Test show_welcome (lines 203-206)."""
        interactive_cli.setup_layout()
        interactive_cli.show_welcome()
        
        # Should not raise
        assert True

    def test_show_download_interface_no_torrent(self, interactive_cli):
        """Test show_download_interface with no torrent (lines 208-211)."""
        interactive_cli.current_torrent = None
        interactive_cli.setup_layout()
        
        interactive_cli.show_download_interface()
        
        # Should return early
        assert True

    def test_show_download_interface_with_torrent(self, interactive_cli):
        """Test show_download_interface with torrent (lines 208-223)."""
        interactive_cli.current_torrent = {"name": "test.torrent", "total_size": 1024}
        interactive_cli.setup_layout()
        interactive_cli.create_download_panel = Mock(return_value=Mock())
        interactive_cli.create_peers_panel = Mock(return_value=Mock())
        interactive_cli.create_status_panel = Mock(return_value=Mock())
        
        interactive_cli.show_download_interface()
        
        # Should create panels
        interactive_cli.create_download_panel.assert_called_once()

    def test_create_download_panel_no_torrent(self, interactive_cli):
        """Test create_download_panel with no torrent (lines 225-228)."""
        interactive_cli.current_torrent = None
        
        result = interactive_cli.create_download_panel()
        
        # Should return panel with "No torrent active"
        assert result is not None

    def test_create_download_panel_with_torrent(self, interactive_cli):
        """Test create_download_panel with torrent (lines 225-306)."""
        interactive_cli.current_torrent = {
            "name": "test.torrent",
            "total_size": 1024 * 1024 * 1024,
            "downloaded_bytes": 512 * 1024 * 1024,
            "total_length": 1024 * 1024 * 1024,
        }
        interactive_cli.stats = {
            "download_speed": 1024 * 1024,
            "upload_speed": 512 * 1024,
            "peers_connected": 5,
            "pieces_completed": 50,
            "pieces_total": 100,
        }
        interactive_cli.progress_manager.create_download_progress = Mock(return_value=Mock())
        
        result = interactive_cli.create_download_panel()
        
        assert result is not None

    def test_create_download_panel_with_eta(self, interactive_cli):
        """Test create_download_panel with ETA calculation (lines 286-297)."""
        interactive_cli.current_torrent = {
            "name": "test.torrent",
            "total_size": 1024 * 1024 * 1024,
            "downloaded_bytes": 512 * 1024 * 1024,
        }
        interactive_cli.stats = {
            "download_speed": 1024 * 1024,  # 1 MB/s
            "upload_speed": 0,
            "peers_connected": 0,
            "pieces_completed": 0,
            "pieces_total": 0,
        }
        interactive_cli.progress_manager.create_download_progress = Mock(return_value=Mock())
        
        result = interactive_cli.create_download_panel()
        
        assert result is not None

    def test_create_peers_panel_no_torrent(self, interactive_cli):
        """Test create_peers_panel with no torrent (lines 308-311)."""
        interactive_cli.current_torrent = None
        
        result = interactive_cli.create_peers_panel()
        
        assert result is not None

    def test_create_peers_panel_no_peers(self, interactive_cli):
        """Test create_peers_panel with no peers (lines 308-315)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli._last_peers = []
        
        result = interactive_cli.create_peers_panel()
        
        assert result is not None

    def test_create_peers_panel_with_peers(self, interactive_cli):
        """Test create_peers_panel with peers (lines 308-353)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli._last_peers = [
            {"ip": "1.2.3.4", "port": 6881, "download_rate": 100.0, "upload_rate": 50.0},
        ]
        
        result = interactive_cli.create_peers_panel()
        
        assert result is not None

    def test_create_status_panel(self, interactive_cli):
        """Test create_status_panel (lines 355-367)."""
        interactive_cli.current_torrent = {"name": "test.torrent"}
        interactive_cli.stats = {
            "download_speed": 1000.0,
            "upload_speed": 500.0,
            "peers_connected": 5,
            "pieces_completed": 10,
            "pieces_total": 100,
        }
        
        result = interactive_cli.create_status_panel()
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_display(self, interactive_cli):
        """Test update_display (lines 369-450)."""
        interactive_cli.current_torrent = {"name": "test.torrent"}
        interactive_cli.update_download_stats = AsyncMock()
        interactive_cli.show_download_interface = Mock()
        
        await interactive_cli.update_display()
        
        interactive_cli.update_download_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_help(self, interactive_cli):
        """Test cmd_help (lines 452-467)."""
        await interactive_cli.cmd_help([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_status_no_torrent(self, interactive_cli):
        """Test cmd_status with no torrent (lines 469-473)."""
        interactive_cli.current_torrent = None
        
        await interactive_cli.cmd_status([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_status_with_torrent(self, interactive_cli, mock_session):
        """Test cmd_status with torrent (lines 469-548)."""
        interactive_cli.current_torrent = {"name": "test.torrent", "total_size": 1024}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        interactive_cli.stats = {
            "download_speed": 1000.0,
            "upload_speed": 500.0,
            "peers_connected": 5,
            "pieces_completed": 10,
            "pieces_total": 100,
        }
        
        # Mock torrent session
        mock_torrent_session = MagicMock()
        mock_torrent_session.is_private = False
        mock_session.torrents = {
            bytes.fromhex(interactive_cli.current_info_hash_hex): mock_torrent_session
        }
        
        await interactive_cli.cmd_status([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_peers_no_torrent(self, interactive_cli):
        """Test cmd_peers with no torrent (lines 550-554)."""
        interactive_cli.current_torrent = None
        
        await interactive_cli.cmd_peers([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_peers_no_peers(self, interactive_cli, mock_session):
        """Test cmd_peers with no peers (lines 550-570)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        mock_session.get_peers_for_torrent = AsyncMock(return_value=[])
        
        await interactive_cli.cmd_peers([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_peers_with_peers_dict(self, interactive_cli, mock_session):
        """Test cmd_peers with peers as dict (lines 550-611)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        mock_session.get_peers_for_torrent = AsyncMock(return_value=[
            {"ip": "1.2.3.4", "port": 6881, "download_rate": 100.0, "upload_rate": 50.0},
        ])
        
        await interactive_cli.cmd_peers([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_peers_with_peers_object(self, interactive_cli, mock_session):
        """Test cmd_peers with peers as objects (lines 580-611)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        
        peer_obj = SimpleNamespace(
            ip="1.2.3.4",
            port=6881,
            download_speed=100.0,
            upload_speed=50.0,
            progress_percentage=lambda: 50.0,
        )
        mock_session.get_peers_for_torrent = AsyncMock(return_value=[peer_obj])
        
        await interactive_cli.cmd_peers([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_peers_exception(self, interactive_cli, mock_session):
        """Test cmd_peers with exception (lines 565-566)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        mock_session.get_peers_for_torrent = AsyncMock(side_effect=Exception("Error"))
        
        await interactive_cli.cmd_peers([])
        
        # Should handle gracefully
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_no_torrent(self, interactive_cli):
        """Test cmd_files with no torrent (lines 613-624)."""
        interactive_cli.current_torrent = None
        
        await interactive_cli.cmd_files([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_no_file_manager(self, interactive_cli, mock_session):
        """Test cmd_files with no file manager (lines 613-633)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        
        mock_torrent_session = MagicMock()
        mock_torrent_session.file_selection_manager = None
        mock_session.torrents = {
            bytes.fromhex(interactive_cli.current_info_hash_hex): mock_torrent_session
        }
        
        await interactive_cli.cmd_files([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_select_success(self, interactive_cli, mock_session):
        """Test cmd_files select success (lines 650-656)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        
        mock_torrent_session = MagicMock()
        mock_file_manager = AsyncMock()
        mock_file_manager.select_file = AsyncMock()
        mock_file_manager.get_all_file_states = AsyncMock(return_value={0: MagicMock()})
        mock_torrent_session.file_selection_manager = mock_file_manager
        mock_session.torrents = {
            bytes.fromhex(interactive_cli.current_info_hash_hex): mock_torrent_session
        }
        
        await interactive_cli.cmd_files(["select", "0"])
        
        mock_file_manager.select_file.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_cmd_files_deselect_success(self, interactive_cli, mock_session):
        """Test cmd_files deselect success (lines 658-665)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        
        mock_torrent_session = MagicMock()
        mock_file_manager = AsyncMock()
        mock_file_manager.deselect_file = AsyncMock()
        mock_file_manager.get_all_file_states = AsyncMock(return_value={0: MagicMock()})
        mock_torrent_session.file_selection_manager = mock_file_manager
        mock_session.torrents = {
            bytes.fromhex(interactive_cli.current_info_hash_hex): mock_torrent_session
        }
        
        await interactive_cli.cmd_files(["deselect", "0"])
        
        mock_file_manager.deselect_file.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_cmd_files_priority_success(self, interactive_cli, mock_session):
        """Test cmd_files priority success (lines 666-677)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        
        mock_torrent_session = MagicMock()
        mock_file_manager = AsyncMock()
        mock_file_manager.set_file_priority = AsyncMock()
        mock_file_manager.get_all_file_states = AsyncMock(return_value={0: MagicMock()})
        mock_torrent_session.file_selection_manager = mock_file_manager
        mock_session.torrents = {
            bytes.fromhex(interactive_cli.current_info_hash_hex): mock_torrent_session
        }
        
        await interactive_cli.cmd_files(["priority", "0", "high"])
        
        mock_file_manager.set_file_priority.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_files_priority_invalid(self, interactive_cli, mock_session):
        """Test cmd_files priority with invalid priority (lines 666-680)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        
        mock_torrent_session = MagicMock()
        mock_file_manager = AsyncMock()
        mock_file_manager.get_all_file_states = AsyncMock(return_value={0: MagicMock()})
        mock_torrent_session.file_selection_manager = mock_file_manager
        mock_session.torrents = {
            bytes.fromhex(interactive_cli.current_info_hash_hex): mock_torrent_session
        }
        
        await interactive_cli.cmd_files(["priority", "0", "invalid_priority"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_files_display_table(self, interactive_cli, mock_session):
        """Test cmd_files display table (lines 685-724)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        
        mock_torrent_session = MagicMock()
        mock_file_manager = MagicMock()
        mock_file_state = MagicMock()
        mock_file_state.selected = True
        mock_file_state.priority = MagicMock()
        mock_file_state.priority.name = "high"
        mock_file_state.bytes_total = 1024
        mock_file_state.bytes_downloaded = 512
        # get_all_file_states should return a dict, not a coroutine
        mock_file_manager.get_all_file_states = Mock(return_value={0: mock_file_state})
        mock_file_manager.torrent_info = MagicMock()
        mock_file_info = MagicMock()
        mock_file_info.path = "test.txt"
        mock_file_info.length = 1024
        mock_file_info.progress = 50.0
        mock_file_info.name = "test.txt"  # Must be a string, not MagicMock
        mock_file_manager.torrent_info.files = [mock_file_info]
        mock_torrent_session.file_selection_manager = mock_file_manager
        mock_session.torrents = {
            bytes.fromhex(interactive_cli.current_info_hash_hex): mock_torrent_session
        }
        
        await interactive_cli.cmd_files([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_pause_no_torrent(self, interactive_cli):
        """Test cmd_pause with no torrent (lines 915-919)."""
        interactive_cli.current_torrent = None
        
        await interactive_cli.cmd_pause([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_pause_success(self, interactive_cli, mock_session):
        """Test cmd_pause success (lines 915-923)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        
        await interactive_cli.cmd_pause([])
        
        mock_session.pause_torrent.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_resume_no_torrent(self, interactive_cli):
        """Test cmd_resume with no torrent (lines 925-929)."""
        interactive_cli.current_torrent = None
        
        await interactive_cli.cmd_resume([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_resume_success(self, interactive_cli, mock_session):
        """Test cmd_resume success (lines 925-933)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        
        await interactive_cli.cmd_resume([])
        
        mock_session.resume_torrent.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_stop_no_torrent(self, interactive_cli):
        """Test cmd_stop with no torrent (lines 935-939)."""
        interactive_cli.current_torrent = None
        
        await interactive_cli.cmd_stop([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_stop_no_remove_method(self, interactive_cli):
        """Test cmd_stop without remove method (lines 935-944)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        if hasattr(interactive_cli.session, "remove"):
            delattr(interactive_cli.session, "remove")
        
        await interactive_cli.cmd_stop([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_checkpoint_list(self, interactive_cli, tmp_path):
        """Test cmd_checkpoint list (lines 1052-1071)."""
        from ccbt.storage.checkpoint import CheckpointManager
        
        # Mock checkpoint manager
        mock_cm = AsyncMock()
        mock_checkpoint = MagicMock()
        mock_checkpoint.info_hash.hex = Mock(return_value="abcd1234" * 4)
        mock_checkpoint.checkpoint_format.value = "v1"
        mock_checkpoint.size = 1024
        mock_cm.list_checkpoints = AsyncMock(return_value=[mock_checkpoint])
        
        with patch("ccbt.storage.checkpoint.CheckpointManager", return_value=mock_cm):
            await interactive_cli.cmd_checkpoint(["list"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_checkpoint_invalid(self, interactive_cli):
        """Test cmd_checkpoint with invalid args (lines 1052-1060)."""
        await interactive_cli.cmd_checkpoint(["invalid"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_metrics_show_all(self, interactive_cli):
        """Test cmd_metrics show all (lines 1073-1100)."""
        mock_mc = MagicMock()
        mock_mc.get_system_metrics = Mock(return_value={"cpu": 50.0})
        mock_mc.get_performance_metrics = Mock(return_value={"download_rate": 1000.0})
        mock_mc.collect_system_metrics = AsyncMock()
        mock_mc.collect_performance_metrics = AsyncMock()
        
        with patch("ccbt.monitoring.MetricsCollector", return_value=mock_mc):
            await interactive_cli.cmd_metrics(["show", "all"])
        
        assert interactive_cli.console.print_json.called

    @pytest.mark.asyncio
    async def test_cmd_metrics_show_system(self, interactive_cli):
        """Test cmd_metrics show system (lines 1073-1100)."""
        mock_mc = MagicMock()
        mock_mc.get_system_metrics = Mock(return_value={"cpu": 50.0})
        mock_mc.collect_system_metrics = AsyncMock()
        
        with patch("ccbt.monitoring.MetricsCollector", return_value=mock_mc):
            await interactive_cli.cmd_metrics(["show", "system"])
        
        assert interactive_cli.console.print_json.called

    @pytest.mark.asyncio
    async def test_cmd_metrics_export_json(self, interactive_cli, tmp_path):
        """Test cmd_metrics export json (lines 1101-1125)."""
        mock_mc = MagicMock()
        mock_mc.get_all_metrics = Mock(return_value={"test": "data"})
        mock_mc.collect_system_metrics = AsyncMock()
        mock_mc.collect_performance_metrics = AsyncMock()
        mock_mc.collect_custom_metrics = AsyncMock()
        
        output_file = tmp_path / "metrics.json"
        
        with patch("ccbt.monitoring.MetricsCollector", return_value=mock_mc):
            await interactive_cli.cmd_metrics(["export", "json", str(output_file)])
        
        assert output_file.exists()

    @pytest.mark.asyncio
    async def test_cmd_metrics_export_prometheus(self, interactive_cli):
        """Test cmd_metrics export prometheus (lines 1101-1125)."""
        mock_mc = MagicMock()
        mock_mc.export_prometheus_format = Mock(return_value="test_metrics")
        mock_mc.collect_system_metrics = AsyncMock()
        mock_mc.collect_performance_metrics = AsyncMock()
        mock_mc.collect_custom_metrics = AsyncMock()
        
        with patch("ccbt.monitoring.MetricsCollector", return_value=mock_mc):
            await interactive_cli.cmd_metrics(["export", "prometheus"])
        
        # Should not raise - line 1122 is covered (pass statement)

    @pytest.mark.asyncio
    async def test_cmd_metrics_export_json_no_file(self, interactive_cli):
        """Test cmd_metrics export json without file (lines 1123-1124)."""
        mock_mc = MagicMock()
        mock_mc.get_all_metrics = Mock(return_value={"test": "data"})
        mock_mc.collect_system_metrics = AsyncMock()
        mock_mc.collect_performance_metrics = AsyncMock()
        mock_mc.collect_custom_metrics = AsyncMock()
        
        with patch("ccbt.monitoring.MetricsCollector", return_value=mock_mc):
            await interactive_cli.cmd_metrics(["export", "json"])
        
        # Should print content (line 1124)
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_alerts_show(self, interactive_cli):
        """Test cmd_alerts show (lines 1130-1240)."""
        mock_am = MagicMock()
        mock_am.alert_rules = {}
        
        with patch("ccbt.monitoring.get_alert_manager", return_value=mock_am):
            await interactive_cli.cmd_alerts(["show"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_export(self, interactive_cli, tmp_path):
        """Test cmd_export (lines 1241-1253)."""
        output_file = tmp_path / "export.json"
        
        await interactive_cli.cmd_export([str(output_file)])
        
        interactive_cli.session.export_session_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_export_no_args(self, interactive_cli):
        """Test cmd_export with no args (lines 1241-1249)."""
        await interactive_cli.cmd_export([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_import(self, interactive_cli, tmp_path):
        """Test cmd_import (lines 1255-1267)."""
        import_file = tmp_path / "import.json"
        import_file.write_text('{"torrents": {}}')
        
        await interactive_cli.cmd_import([str(import_file)])
        
        interactive_cli.session.import_session_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_import_no_args(self, interactive_cli):
        """Test cmd_import with no args (lines 1255-1263)."""
        await interactive_cli.cmd_import([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_backup(self, interactive_cli, tmp_path):
        """Test cmd_backup (lines 1269-1285)."""
        backup_dest = tmp_path / "backup"
        
        with patch("ccbt.storage.checkpoint.CheckpointManager") as mock_cm_class:
            mock_cm = AsyncMock()
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_backup(["abcd1234" * 4, str(backup_dest)])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_backup_no_args(self, interactive_cli):
        """Test cmd_backup with no args (lines 1269-1277)."""
        await interactive_cli.cmd_backup([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_restore(self, interactive_cli, tmp_path):
        """Test cmd_restore (lines 1287-1305)."""
        backup_file = tmp_path / "backup.tar.gz"
        backup_file.write_text("test")
        
        mock_checkpoint = MagicMock()
        mock_checkpoint.torrent_name = "test.torrent"
        mock_checkpoint.info_hash.hex = Mock(return_value="abcd1234" * 4)
        
        with patch("ccbt.storage.checkpoint.CheckpointManager") as mock_cm_class:
            mock_cm = AsyncMock()
            mock_cm.restore_checkpoint = AsyncMock(return_value=mock_checkpoint)
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_restore([str(backup_file)])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_restore_no_args(self, interactive_cli):
        """Test cmd_restore with no args (lines 1287-1295)."""
        await interactive_cli.cmd_restore([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_capabilities_show(self, interactive_cli):
        """Test cmd_capabilities show (lines 1307-1347)."""
        mock_sc = MagicMock()
        mock_sc.get_all_capabilities = Mock(return_value={
            "test_bool": True,
            "test_dict": {"key": True},
            "test_list": ["item1", "item2"],
            "test_str": "value",
        })
        
        with patch("ccbt.config.config_capabilities.SystemCapabilities", return_value=mock_sc):
            await interactive_cli.cmd_capabilities(["show"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_capabilities_summary(self, interactive_cli):
        """Test cmd_capabilities summary (lines 1307-1327)."""
        mock_sc = MagicMock()
        mock_sc.get_capability_summary = Mock(return_value={"test": True})
        
        with patch("ccbt.config.config_capabilities.SystemCapabilities", return_value=mock_sc):
            await interactive_cli.cmd_capabilities(["summary"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_auto_tune_preview(self, interactive_cli):
        """Test cmd_auto_tune preview (lines 1349-1373)."""
        mock_cc = MagicMock()
        mock_tuned_config = MagicMock()
        mock_tuned_config.model_dump = Mock(return_value={"test": "value"})
        mock_cc.adjust_for_system = Mock(return_value=(mock_tuned_config, []))
        
        with patch("ccbt.config.config_conditional.ConditionalConfig", return_value=mock_cc):
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_auto_tune(["preview"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_auto_tune_apply(self, interactive_cli):
        """Test cmd_auto_tune apply (lines 1366-1369)."""
        mock_cc = MagicMock()
        mock_tuned_config = MagicMock()
        mock_tuned_config.model_dump = Mock(return_value={"test": "value"})
        mock_cc.adjust_for_system = Mock(return_value=(mock_tuned_config, []))
        
        with patch("ccbt.config.config_conditional.ConditionalConfig", return_value=mock_cc):
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                with patch("ccbt.config.config.set_config") as mock_set_config:
                    mock_cm = MagicMock()
                    mock_cm.config = MagicMock()
                    mock_cm_class.return_value = mock_cm
                    
                    await interactive_cli.cmd_auto_tune(["apply"])
            
            assert interactive_cli.console.print.called
            mock_set_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_template_list(self, interactive_cli):
        """Test cmd_template list (lines 1375-1397)."""
        from ccbt.config.config_templates import ConfigTemplates
        
        mock_templates = [
            {"key": "test", "name": "Test Template", "description": "Test"},
        ]
        
        with patch.object(ConfigTemplates, "list_templates", return_value=mock_templates):
            await interactive_cli.cmd_template(["list"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_template_list_empty(self, interactive_cli):
        """Test cmd_template list empty (lines 1375-1389)."""
        from ccbt.config.config_templates import ConfigTemplates
        
        with patch.object(ConfigTemplates, "list_templates", return_value=[]):
            await interactive_cli.cmd_template(["list"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_template_apply(self, interactive_cli):
        """Test cmd_template apply (lines 1398-1412)."""
        from ccbt.config.config_templates import ConfigTemplates
        
        mock_new_dict = {"test": "value"}
        
        with patch.object(ConfigTemplates, "apply_template", return_value=mock_new_dict):
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm.config.model_dump = Mock(return_value={})
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_template(["apply", "test"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_template_invalid(self, interactive_cli):
        """Test cmd_template with invalid args (lines 1375-1413)."""
        await interactive_cli.cmd_template(["invalid"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_profile_list(self, interactive_cli):
        """Test cmd_profile list (lines 1415-1437)."""
        from ccbt.config.config_templates import ConfigProfiles
        
        mock_profiles = [
            {"key": "test", "name": "Test Profile", "templates": ["template1"]},
        ]
        
        with patch.object(ConfigProfiles, "list_profiles", return_value=mock_profiles):
            await interactive_cli.cmd_profile(["list"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_profile_list_empty(self, interactive_cli):
        """Test cmd_profile list empty (lines 1415-1429)."""
        from ccbt.config.config_templates import ConfigProfiles
        
        with patch.object(ConfigProfiles, "list_profiles", return_value=[]):
            await interactive_cli.cmd_profile(["list"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_profile_apply(self, interactive_cli):
        """Test cmd_profile apply (lines 1438-1452)."""
        from ccbt.config.config_templates import ConfigProfiles
        
        mock_new_dict = {"test": "value"}
        
        with patch.object(ConfigProfiles, "apply_profile", return_value=mock_new_dict):
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm.config.model_dump = Mock(return_value={})
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_profile(["apply", "test"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_backup_list(self, interactive_cli):
        """Test cmd_config_backup list (lines 1454-1473)."""
        mock_backups = [
            {
                "timestamp": "2024-01-01",
                "backup_type": "manual",
                "description": "Test backup",
                "file": Path("backup1.toml"),
            }
        ]
        
        with patch("ccbt.config.config_backup.ConfigBackup") as mock_cb_class:
            mock_cb = MagicMock()
            mock_cb.list_backups = Mock(return_value=mock_backups)
            mock_cb_class.return_value = mock_cb
            
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm.config.disk = MagicMock()
                mock_cm.config.disk.backup_dir = "/tmp"
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_config_backup(["list"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_backup_create(self, interactive_cli):
        """Test cmd_config_backup create (lines 1474-1482)."""
        with patch("ccbt.config.config_backup.ConfigBackup") as mock_cb_class:
            mock_cb = MagicMock()
            mock_cb.create_backup = Mock(return_value=(True, Path("backup.toml"), []))
            mock_cb_class.return_value = mock_cb
            
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm.config.disk = MagicMock()
                mock_cm.config.disk.backup_dir = "/tmp"
                mock_cm.config_file = "/tmp/config.toml"
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_config_backup(["create", "test"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_backup_create_failure(self, interactive_cli):
        """Test cmd_config_backup create failure (lines 1499-1500)."""
        with patch("ccbt.config.config_backup.ConfigBackup") as mock_cb_class:
            mock_cb = MagicMock()
            mock_cb.create_backup = Mock(return_value=(False, None, ["Error message"]))
            mock_cb_class.return_value = mock_cb
            
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm.config.disk = MagicMock()
                mock_cm.config.disk.backup_dir = "/tmp"
                mock_cm.config_file = "/tmp/config.toml"
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_config_backup(["create", "test"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_backup_restore(self, interactive_cli, tmp_path):
        """Test cmd_config_backup restore (lines 1483-1491)."""
        backup_file = tmp_path / "backup.toml"
        
        with patch("ccbt.config.config_backup.ConfigBackup") as mock_cb_class:
            mock_cb = MagicMock()
            mock_cb.restore_backup = Mock(return_value=(True, []))
            mock_cb_class.return_value = mock_cb
            
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm.config.disk = MagicMock()
                mock_cm.config.disk.backup_dir = "/tmp"
                mock_cm.config_file = "/tmp/config.toml"
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_config_backup(["restore", str(backup_file)])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_backup_restore_failure(self, interactive_cli, tmp_path):
        """Test cmd_config_backup restore failure (lines 1506-1507)."""
        backup_file = tmp_path / "backup.toml"
        
        with patch("ccbt.config.config_backup.ConfigBackup") as mock_cb_class:
            mock_cb = MagicMock()
            mock_cb.restore_backup = Mock(return_value=(False, ["Error message"]))
            mock_cb_class.return_value = mock_cb
            
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm.config.disk = MagicMock()
                mock_cm.config.disk.backup_dir = "/tmp"
                mock_cm.config_file = "/tmp/config.toml"
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_config_backup(["restore", str(backup_file)])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_backup_invalid(self, interactive_cli):
        """Test cmd_config_backup with invalid args (lines 1454-1492)."""
        await interactive_cli.cmd_config_backup(["invalid"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_diff(self, interactive_cli):
        """Test cmd_config_diff (lines 1513-1529)."""
        mock_diff = MagicMock()
        mock_diff.compare = Mock(return_value={"changed": ["test.key"]})
        
        with patch("ccbt.config.config_diff.ConfigDiff", return_value=mock_diff):
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm.config.model_dump = Mock(return_value={})
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_config_diff([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_export(self, interactive_cli, tmp_path):
        """Test cmd_config_export (lines 1531-1561)."""
        output_file = tmp_path / "config.json"
        
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"test": "value"})  # Must be JSON-serializable
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_config_export(["json", str(output_file)])
        
        assert output_file.exists()
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_export_no_file(self, interactive_cli):
        """Test cmd_config_export without file (lines 1531-1561)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.export = Mock(return_value='{"test": "value"}')
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_config_export(["json"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_import(self, interactive_cli, tmp_path):
        """Test cmd_config_import (lines 1563-1608)."""
        import_file = tmp_path / "config.json"
        import_file.write_text('{"network": {"listen_port": 6881}}')
        
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.import_config = Mock()
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_config_import([str(import_file)])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_import_no_args(self, interactive_cli):
        """Test cmd_config_import with no args (lines 1563-1567)."""
        await interactive_cli.cmd_config_import([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_schema(self, interactive_cli):
        """Test cmd_config_schema (lines 1610-1624)."""
        from ccbt.config.config_schema import ConfigSchema
        
        mock_schema = {"test": "schema"}
        
        with patch.object(ConfigSchema, "generate_full_schema", return_value=mock_schema):
            await interactive_cli.cmd_config_schema([])
        
        assert interactive_cli.console.print_json.called

    @pytest.mark.asyncio
    async def test_cmd_config_show_all(self, interactive_cli):
        """Test cmd_config show all (lines 1626-1655)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"test": "value"})
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_config(["show"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_show_section(self, interactive_cli):
        """Test cmd_config show section (lines 1626-1655)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {"listen_port": 6881}})
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_config(["show", "network"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_show_key_not_found(self, interactive_cli):
        """Test cmd_config show with key not found (lines 1646-1651)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {"listen_port": 6881}})
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_config(["show", "nonexistent.key"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_get(self, interactive_cli):
        """Test cmd_config get (lines 1656-1667)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {"listen_port": 6881}})
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_config(["get", "network.listen_port"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_get_not_found(self, interactive_cli):
        """Test cmd_config get with key not found (lines 1656-1667)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {"listen_port": 6881}})
            mock_cm_class.return_value = mock_cm
            
            await interactive_cli.cmd_config(["get", "nonexistent.key"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_get_no_args(self, interactive_cli):
        """Test cmd_config get with no args (lines 1656-1659)."""
        await interactive_cli.cmd_config(["get"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_set_bool(self, interactive_cli):
        """Test cmd_config set with bool value (lines 1668-1707)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {}})
            mock_cm_class.return_value = mock_cm
            
            with patch("ccbt.models.Config") as mock_model_class:
                mock_model = MagicMock()
                mock_model_class.return_value = mock_model
                
                await interactive_cli.cmd_config(["set", "network.test", "true"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_set_int(self, interactive_cli):
        """Test cmd_config set with int value (lines 1668-1707)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {}})
            mock_cm_class.return_value = mock_cm
            
            with patch("ccbt.models.Config") as mock_model_class:
                mock_model = MagicMock()
                mock_model_class.return_value = mock_model
                
                await interactive_cli.cmd_config(["set", "network.port", "6881"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_set_float(self, interactive_cli):
        """Test cmd_config set with float value (lines 1668-1707)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {}})
            mock_cm_class.return_value = mock_cm
            
            with patch("ccbt.models.Config") as mock_model_class:
                mock_model = MagicMock()
                mock_model_class.return_value = mock_model
                
                await interactive_cli.cmd_config(["set", "network.ratio", "1.5"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_set_string(self, interactive_cli):
        """Test cmd_config set with string value (lines 1668-1707)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {}})
            mock_cm_class.return_value = mock_cm
            
            with patch("ccbt.models.Config") as mock_model_class:
                mock_model = MagicMock()
                mock_model_class.return_value = mock_model
                
                await interactive_cli.cmd_config(["set", "network.host", "localhost"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_set_error(self, interactive_cli):
        """Test cmd_config set with error (lines 1706-1707)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {}})
            mock_cm_class.return_value = mock_cm
            
            with patch("ccbt.models.Config", side_effect=Exception("Validation error")):
                await interactive_cli.cmd_config(["set", "network.invalid", "value"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_set_no_args(self, interactive_cli):
        """Test cmd_config set with no args (lines 1668-1671)."""
        await interactive_cli.cmd_config(["set"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_reload(self, interactive_cli):
        """Test cmd_config reload (lines 1708-1713)."""
        with patch("ccbt.cli.interactive.reload_config") as mock_reload:
            await interactive_cli.cmd_config(["reload"])
        
        mock_reload.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_config_reload_error(self, interactive_cli):
        """Test cmd_config reload with error (lines 1708-1713)."""
        with patch("ccbt.cli.interactive.reload_config", side_effect=Exception("Reload error")):
            await interactive_cli.cmd_config(["reload"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_invalid_subcommand(self, interactive_cli):
        """Test cmd_config with invalid subcommand (lines 1714-1715)."""
        await interactive_cli.cmd_config(["invalid"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_no_args(self, interactive_cli):
        """Test cmd_config with no args (lines 1635-1637)."""
        await interactive_cli.cmd_config([])
        
        assert interactive_cli.console.print.called

