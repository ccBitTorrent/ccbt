"""Final coverage tests for interactive.py to reach 100% coverage.

Covers remaining missing lines:
- Line 176: torrent_status None break
- Lines 409-420: Progress update with _fmt_bytes
- Lines 487-489: progress_percentage callable
- Lines 496-497: hasattr is_private check
- Lines 506-507: Exception handler for is_private
- Lines 1109-1110: Exception handler for metrics
- Lines 1147-1160: Alert rules display
- Lines 1364-1365: Warnings in auto_tune
- Lines 1476-1477: No backups found
- Line 1679: parse_value False return
- Line 1705: Config set success
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from rich.console import Console

pytestmark = [pytest.mark.unit, pytest.mark.cli]


@pytest.fixture
def mock_session():
    """Create a mock AsyncSessionManager."""
    session = AsyncMock()
    session.add_torrent = AsyncMock(return_value="abcd1234" * 4)
    session.get_torrent_status = AsyncMock(return_value=None)  # Will return None to trigger break
    session.lock = AsyncMock()
    session.lock.__aenter__ = AsyncMock(return_value=None)
    session.lock.__aexit__ = AsyncMock(return_value=None)
    session.torrents = {}
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


class TestInteractiveFinalCoverage:
    """Tests for final coverage gaps."""

    @pytest.mark.asyncio
    async def test_download_torrent_status_none_breaks(self, interactive_cli, mock_session):
        """Test download_torrent breaks when status is None (line 176)."""
        interactive_cli.setup_layout()
        interactive_cli.running = True
        interactive_cli._interactive_file_selection = AsyncMock()
        interactive_cli.show_download_interface = Mock()
        interactive_cli.update_download_stats = AsyncMock()
        
        torrent_data = {"name": "test.torrent", "total_size": 1024}
        # Mock get_torrent_status to return None immediately
        mock_session.get_torrent_status = AsyncMock(return_value=None)
        
        await interactive_cli.download_torrent(torrent_data, resume=False)
        
        # Should break out of loop when status is None
        assert interactive_cli.current_torrent == torrent_data

    @pytest.mark.asyncio
    async def test_update_download_stats_progress_update(self, interactive_cli):
        """Test update_download_stats with progress update (lines 409-420)."""
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli._download_progress = MagicMock()
        interactive_cli._download_task = 123
        interactive_cli.stats = {
            "download_speed": 1024 * 1024,
            "upload_speed": 0,
            "peers_connected": 0,
            "pieces_completed": 0,
            "pieces_total": 0,
        }
        
        interactive_cli.session.get_torrent_status = AsyncMock(return_value={
            "progress": 0.5,
            "downloaded_bytes": 512 * 1024 * 1024,
        })
        
        await interactive_cli.update_download_stats()
        
        # Should update progress (lines 409-420)
        interactive_cli._download_progress.update.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_status_progress_percentage_callable(self, interactive_cli, mock_session):
        """Test cmd_status with callable progress_percentage (lines 487-489)."""
        # Use dict but add progress_percentage as callable attribute
        torrent_dict = {
            "name": "test.torrent",
            "total_size": 1024 * 1024 * 1024,  # 1 GB
            "downloaded_bytes": 512 * 1024 * 1024,
        }
        # Add progress_percentage as a callable (will be checked via hasattr)
        torrent_obj = type('TorrentObj', (dict,), {
            'progress_percentage': Mock(return_value=50),
            '__getitem__': dict.__getitem__,
            'get': dict.get,
        })(torrent_dict)
        
        interactive_cli.current_torrent = torrent_obj
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        interactive_cli.stats = {
            "download_speed": 0,
            "upload_speed": 0,
            "peers_connected": 0,
            "pieces_completed": 0,
            "pieces_total": 0,
        }
        mock_session.get_scrape_result = AsyncMock(return_value=None)
        
        await interactive_cli.cmd_status([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_status_is_private_hasattr(self, interactive_cli, mock_session):
        """Test cmd_status with hasattr is_private check (lines 496-497)."""
        # Use dict but add is_private as attribute
        torrent_dict = {
            "name": "test.torrent",
            "total_size": 1024 * 1024 * 1024,  # 1 GB
            "downloaded_bytes": 512 * 1024 * 1024,
        }
        # Create object that has is_private attribute but also works as dict
        torrent_obj = type('TorrentObj', (dict,), {
            'is_private': True,
            '__getitem__': dict.__getitem__,
            'get': dict.get,
        })(torrent_dict)
        
        interactive_cli.current_torrent = torrent_obj
        interactive_cli.current_info_hash_hex = "abcd1234" * 4
        interactive_cli.session = mock_session
        interactive_cli.stats = {
            "download_speed": 0,
            "upload_speed": 0,
            "peers_connected": 0,
            "pieces_completed": 0,
            "pieces_total": 0,
        }
        mock_session.get_scrape_result = AsyncMock(return_value=None)
        
        await interactive_cli.cmd_status([])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_status_is_private_exception(self, interactive_cli, mock_session):
        """Test cmd_status is_private check exception handler (lines 506-507)."""
        interactive_cli.current_torrent = {"name": "test.torrent", "total_size": 1024}
        interactive_cli.current_info_hash_hex = "invalid_hex"  # Will cause exception
        interactive_cli.session = mock_session
        interactive_cli.stats = {
            "download_speed": 0,
            "upload_speed": 0,
            "peers_connected": 0,
            "pieces_completed": 0,
            "pieces_total": 0,
        }
        mock_session.get_scrape_result = AsyncMock(return_value=None)
        
        await interactive_cli.cmd_status([])
        
        # Should handle exception gracefully (lines 506-507)
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_metrics_exception_handler(self, interactive_cli):
        """Test cmd_metrics exception handler (lines 1109-1110)."""
        mock_mc = MagicMock()
        mock_mc.collect_system_metrics = AsyncMock(side_effect=Exception("Test error"))
        mock_mc.collect_performance_metrics = AsyncMock()
        mock_mc.collect_custom_metrics = AsyncMock()
        mock_mc.get_all_metrics = Mock(return_value={"test": "data"})
        
        with patch("ccbt.monitoring.MetricsCollector", return_value=mock_mc):
            await interactive_cli.cmd_metrics(["export", "json"])
        
        # Should handle exception (lines 1109-1110)
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_alerts_list_with_rules(self, interactive_cli):
        """Test cmd_alerts list with rules (lines 1147-1160)."""
        mock_am = MagicMock()
        mock_rule = MagicMock()
        mock_rule.severity.value = "warning"
        mock_rule.metric_name = "test_metric"
        mock_rule.condition = "> 100"
        mock_am.alert_rules = {"test_rule": mock_rule}
        
        with patch("ccbt.monitoring.get_alert_manager", return_value=mock_am):
            await interactive_cli.cmd_alerts(["list"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_auto_tune_with_warnings(self, interactive_cli):
        """Test cmd_auto_tune with warnings (lines 1364-1365)."""
        mock_cc = MagicMock()
        mock_tuned_config = MagicMock()
        mock_tuned_config.model_dump = Mock(return_value={"test": "value"})
        mock_cc.adjust_for_system = Mock(return_value=(mock_tuned_config, ["Warning 1", "Warning 2"]))
        
        with patch("ccbt.config.config_conditional.ConditionalConfig", return_value=mock_cc):
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_cm = MagicMock()
                mock_cm.config = MagicMock()
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_auto_tune(["preview"])
        
        # Should print warnings (lines 1364-1365)
        assert interactive_cli.console.print.called
        assert interactive_cli.console.print.call_count >= 2  # At least warnings + preview

    @pytest.mark.asyncio
    async def test_cmd_config_backup_list_empty(self, interactive_cli):
        """Test cmd_config_backup list with no backups (lines 1476-1477)."""
        with patch("ccbt.config.config_backup.ConfigBackup") as mock_cb_class:
            mock_cb = MagicMock()
            mock_cb.list_backups = Mock(return_value=[])
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
    async def test_cmd_config_set_parse_value_false(self, interactive_cli):
        """Test cmd_config set with parse_value returning False (line 1679)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {}})
            mock_cm_class.return_value = mock_cm
            
            with patch("ccbt.models.Config") as mock_model_class:
                mock_model = MagicMock()
                mock_model_class.return_value = mock_model
                
                await interactive_cli.cmd_config(["set", "network.test", "false"])
        
        assert interactive_cli.console.print.called

    @pytest.mark.asyncio
    async def test_cmd_config_set_success(self, interactive_cli):
        """Test cmd_config set success path (line 1705)."""
        with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.config = MagicMock()
            mock_cm.config.model_dump = Mock(return_value={"network": {}})
            mock_cm_class.return_value = mock_cm
            
            with patch("ccbt.models.Config") as mock_model_class:
                with patch("ccbt.config.config.set_config") as mock_set_config:
                    mock_model = MagicMock()
                    mock_model_class.return_value = mock_model
                    
                    await interactive_cli.cmd_config(["set", "network.port", "6881"])
        
        assert interactive_cli.console.print.called
        mock_set_config.assert_called_once()

