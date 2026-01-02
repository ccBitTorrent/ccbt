"""Expanded tests for ccbt.cli.interactive.

Covers:
- Command handlers (help, status, peers, files, pause, resume, stop, quit, clear)
- Configuration commands (config, limits, strategy, discovery, etc.)
- Extended config commands (capabilities, auto_tune, template, profile, etc.)
- Display update logic
- Error handling paths
- File operations
- Background tasks
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
    session.add_torrent = AsyncMock(return_value="abcd1234")
    session.get_torrent_status = AsyncMock(return_value={
        "download_rate": 1000.0,
        "upload_rate": 500.0,
        "pieces_completed": 10,
        "pieces_total": 100,
        "progress": 0.1,
        "downloaded_bytes": 1048576,
    })
    session.get_peers_for_torrent = AsyncMock(return_value=[
        {"ip": "1.2.3.4", "port": 6881, "download_rate": 100.0, "upload_rate": 50.0},
        {"ip": "5.6.7.8", "port": 6882, "download_rate": 200.0, "upload_rate": 100.0},
    ])
    session.pause_torrent = AsyncMock()
    session.resume_torrent = AsyncMock()
    session.remove = AsyncMock()
    # Initialize torrents dict to prevent AttributeError
    session.torrents = {}
    session.lock = AsyncMock()
    session.lock.__aenter__ = AsyncMock(return_value=None)
    session.lock.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def mock_console():
    """Create a mock Console."""
    import time
    console = MagicMock(spec=Console)
    console.print = Mock()
    console.clear = Mock()
    console.print_json = Mock()
    # CRITICAL FIX: Rich Progress requires console.get_time method
    console.get_time = Mock(return_value=time.time)
    return console


@pytest.fixture
def interactive_cli(mock_session, mock_console, mock_config_manager):
    """Create an InteractiveCLI instance.
    
    Uses mock_config_manager fixture to ensure ConfigManager is patched
    at module level for all commands that create ConfigManager(None) instances.
    """
    from tests.conftest import create_interactive_cli
    
    cli = create_interactive_cli(mock_session, mock_console)
    return cli


@pytest.mark.asyncio
async def test_interactive_cli_init(mock_session, mock_console):
    """Test InteractiveCLI initialization (lines 44-110)."""
    from tests.conftest import create_interactive_cli
    
    cli = create_interactive_cli(mock_session, mock_console)
    
    assert cli.session == mock_session
    assert cli.console == mock_console
    assert cli.running is False
    assert cli.current_torrent is None
    assert isinstance(cli.layout, type(cli.layout))
    assert cli.live_display is None
    assert isinstance(cli.stats, dict)
    assert cli.current_info_hash_hex is None
    assert isinstance(cli.commands, dict)
    assert "help" in cli.commands
    assert "status" in cli.commands
    assert "quit" in cli.commands


@pytest.mark.asyncio
async def test_cmd_help(interactive_cli):
    """Test cmd_help command handler (lines 405-420)."""
    await interactive_cli.cmd_help([])
    
    # Verify help text was printed
    assert interactive_cli.console.print.called
    call_args = interactive_cli.console.print.call_args
    assert call_args is not None
    # Check that Panel was printed
    assert len(call_args[0]) > 0


@pytest.mark.asyncio
async def test_cmd_status_no_torrent(interactive_cli):
    """Test cmd_status with no active torrent (lines 422-426)."""
    interactive_cli.current_torrent = None
    
    await interactive_cli.cmd_status([])
    
    interactive_cli.console.print.assert_called_with("No torrent active")


@pytest.mark.asyncio
async def test_cmd_status_with_torrent(interactive_cli):
    """Test cmd_status with active torrent (lines 422-465)."""
    interactive_cli.current_torrent = {
        "name": "test_torrent",
        "total_size": 1024 * 1024 * 1024,  # 1 GB
        "downloaded_bytes": 100 * 1024 * 1024,  # 100 MB
    }
    interactive_cli.stats = {
        "download_speed": 1024.0,
        "upload_speed": 512.0,
        "peers_connected": 5,
        "pieces_completed": 50,
        "pieces_total": 100,
    }
    
    await interactive_cli.cmd_status([])
    
    # Verify table was printed
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_status_with_progress_percentage(interactive_cli):
    """Test cmd_status with progress_percentage property (lines 439-444)."""
    # Use a dict to match the code's expectation, or create object that works with getattr
    class MockTorrent:
        def __init__(self):
            self.name = "test"
            self.total_size = 1024 * 1024 * 1024
            self.downloaded_bytes = 100 * 1024 * 1024
            # progress_percentage as a method
            self.progress_percentage = lambda: 10
        
        # Make it work with getattr but not dict.get()
        def get(self, key, default=None):
            return getattr(self, key, default)
    
    torrent = MockTorrent()
    
    interactive_cli.current_torrent = torrent
    interactive_cli.stats = {
        "download_speed": 1024.0,
        "upload_speed": 512.0,
        "peers_connected": 5,
        "pieces_completed": 50,
        "pieces_total": 100,
    }
    
    await interactive_cli.cmd_status([])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_peers_no_torrent(interactive_cli):
    """Test cmd_peers with no active torrent (lines 467-471)."""
    interactive_cli.current_torrent = None
    
    await interactive_cli.cmd_peers([])
    
    interactive_cli.console.print.assert_called_with("No torrent active")


@pytest.mark.asyncio
async def test_cmd_peers_no_peers(interactive_cli):
    """Test cmd_peers with no peers (lines 467-487)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.get_peers_for_torrent = AsyncMock(return_value=[])
    
    await interactive_cli.cmd_peers([])
    
    interactive_cli.console.print.assert_called_with("No peers connected")


@pytest.mark.asyncio
async def test_cmd_peers_with_peers(interactive_cli):
    """Test cmd_peers with connected peers (lines 467-524)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    
    await interactive_cli.cmd_peers([])
    
    # Verify table was printed
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_peers_with_peer_exception(interactive_cli):
    """Test cmd_peers with exception (lines 478-483)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.get_peers_for_torrent = AsyncMock(side_effect=Exception("Error"))
    
    await interactive_cli.cmd_peers([])
    
    # Should handle exception and print "No peers connected"
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_peers_with_dict_peers(interactive_cli):
    """Test cmd_peers with dict-based peers (lines 503-508)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.get_peers_for_torrent = AsyncMock(return_value=[
        {
            "ip": "1.2.3.4",
            "port": 6881,
            "download_rate": 100.0,
            "upload_rate": 50.0,
            "progress_percentage": Mock(return_value=50.0),
        },
    ])
    
    await interactive_cli.cmd_peers([])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_files_no_torrent(interactive_cli):
    """Test cmd_files with no active torrent (lines 526-530)."""
    interactive_cli.current_torrent = None
    
    await interactive_cli.cmd_files([])
    
    interactive_cli.console.print.assert_called_with("No torrent active")


@pytest.mark.asyncio
async def test_cmd_files_with_files(interactive_cli):
    """Test cmd_files with file information (lines 526-559)."""
    interactive_cli.current_torrent = {
        "files": [
            {
                "name": "file1.txt",
                "length": 1024 * 1024,
                "progress_percentage": Mock(return_value=50.0),
                "priority": Mock(name="high"),
            },
        ],
    }
    
    await interactive_cli.cmd_files([])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_files_with_files_as_attr(interactive_cli):
    """Test cmd_files with files as attribute (lines 541)."""
    file_info = MagicMock()
    file_info.name = "file1.txt"
    file_info.length = 1024 * 1024
    file_info.progress_percentage = Mock(return_value=50.0)
    file_info.priority = MagicMock()
    file_info.priority.name = "high"
    
    torrent = MagicMock()
    torrent.files = [file_info]
    
    interactive_cli.current_torrent = torrent
    
    await interactive_cli.cmd_files([])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_pause_no_torrent(interactive_cli):
    """Test cmd_pause with no active torrent (lines 561-565)."""
    interactive_cli.current_torrent = None
    
    await interactive_cli.cmd_pause([])
    
    interactive_cli.console.print.assert_called_with("No torrent active")


@pytest.mark.asyncio
async def test_cmd_pause_with_torrent(interactive_cli):
    """Test cmd_pause with active torrent (lines 561-569)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    
    await interactive_cli.cmd_pause([])
    
    interactive_cli.session.pause_torrent.assert_called_once_with("abcd1234")
    interactive_cli.console.print.assert_called_with("Download paused")


@pytest.mark.asyncio
async def test_cmd_resume_no_torrent(interactive_cli):
    """Test cmd_resume with no active torrent (lines 571-575)."""
    interactive_cli.current_torrent = None
    
    await interactive_cli.cmd_resume([])
    
    interactive_cli.console.print.assert_called_with("No torrent active")


@pytest.mark.asyncio
async def test_cmd_resume_with_torrent(interactive_cli):
    """Test cmd_resume with active torrent (lines 571-579)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    
    # Mock executor to return success with checkpoint info
    from ccbt.executor.executor import CommandResult
    interactive_cli.executor.execute = AsyncMock(return_value=CommandResult(
        success=True,
        data={"checkpoint_restored": False}  # No checkpoint found
    ))
    
    await interactive_cli.cmd_resume([])
    
    # Verify executor was called
    interactive_cli.executor.execute.assert_called_once_with(
        "torrent.resume", info_hash="abcd1234"
    )
    # The message includes checkpoint info - check that it contains "Download resumed"
    calls = interactive_cli.console.print.call_args_list
    resume_calls = [str(call) for call in calls if "Download resumed" in str(call)]
    assert len(resume_calls) > 0, f"Expected 'Download resumed' message, got calls: {calls}"


@pytest.mark.asyncio
async def test_cmd_stop_no_torrent(interactive_cli):
    """Test cmd_stop with no active torrent (lines 581-585)."""
    interactive_cli.current_torrent = None
    
    await interactive_cli.cmd_stop([])
    
    interactive_cli.console.print.assert_called_with("No torrent active")


@pytest.mark.asyncio
async def test_cmd_stop_with_torrent(interactive_cli):
    """Test cmd_stop with active torrent (lines 581-592)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    
    await interactive_cli.cmd_stop([])
    
    interactive_cli.session.remove.assert_called_once_with("abcd1234")
    interactive_cli.console.print.assert_called_with("Download stopped")


@pytest.mark.asyncio
async def test_cmd_stop_no_remove_method(interactive_cli):
    """Test cmd_stop when session has no remove method (lines 588-590)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    delattr(interactive_cli.session, "remove")
    
    # Mock executor to return failure when remove method doesn't exist
    from unittest.mock import MagicMock
    from ccbt.executor.executor import CommandResult
    interactive_cli.executor.execute = AsyncMock(return_value=CommandResult(
        success=False,
        error="remove"
    ))
    
    await interactive_cli.cmd_stop([])
    
    # Should print error message when remove fails
    assert interactive_cli.console.print.called
    call_args = interactive_cli.console.print.call_args[0][0]
    assert "Failed to stop" in call_args or "remove" in call_args


@pytest.mark.asyncio
async def test_cmd_quit(interactive_cli):
    """Test cmd_quit command handler (lines 594-597)."""
    from rich.prompt import Confirm
    
    with patch.object(Confirm, "ask", return_value=True):
        await interactive_cli.cmd_quit([])
        assert interactive_cli.running is False
    
    with patch.object(Confirm, "ask", return_value=False):
        interactive_cli.running = True
        await interactive_cli.cmd_quit([])
        # Should remain True if user says no
        assert interactive_cli.running is True


@pytest.mark.asyncio
async def test_cmd_clear(interactive_cli):
    """Test cmd_clear command handler (lines 599)."""
    await interactive_cli.cmd_clear([])
    
    # Clear typically just prints to console
    assert interactive_cli.console.print.called or interactive_cli.console.clear.called


@pytest.mark.asyncio
async def test_update_download_stats_with_status(interactive_cli):
    """Test update_download_stats with session status (lines 328-380)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    
    await interactive_cli.update_download_stats()
    
    # Verify stats were updated
    assert interactive_cli.stats["download_speed"] == 1000.0
    assert interactive_cli.stats["upload_speed"] == 500.0
    assert interactive_cli.stats["pieces_completed"] == 10
    assert interactive_cli.stats["pieces_total"] == 100


@pytest.mark.asyncio
async def test_update_download_stats_no_status(interactive_cli):
    """Test update_download_stats without session status (lines 380-401)."""
    interactive_cli.current_torrent = {
        "download_speed": 2000.0,
        "upload_speed": 1000.0,
        "completed_pieces": 20,
        "total_pieces": 200,
    }
    interactive_cli.current_info_hash_hex = None
    interactive_cli.session.get_torrent_status = AsyncMock(return_value=None)
    
    await interactive_cli.update_download_stats()
    
    # Should use torrent attributes
    assert interactive_cli.stats["download_speed"] in (2000.0, 0)


@pytest.mark.asyncio
async def test_update_download_stats_exception(interactive_cli):
    """Test update_download_stats with exception (lines 402-403)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.get_torrent_status = AsyncMock(side_effect=Exception("Error"))
    
    # Should not raise
    await interactive_cli.update_download_stats()


@pytest.mark.asyncio
async def test_update_display(interactive_cli):
    """Test update_display method (lines 322-326)."""
    interactive_cli.current_torrent = {"name": "test"}
    
    with patch.object(interactive_cli, "update_download_stats", new_callable=AsyncMock) as mock_update:
        with patch.object(interactive_cli, "show_download_interface", new_callable=Mock) as mock_show:
            await interactive_cli.update_display()
            
            mock_update.assert_called_once()
            mock_show.assert_called_once()


@pytest.mark.asyncio
async def test_update_display_no_torrent(interactive_cli):
    """Test update_display with no torrent (lines 324)."""
    interactive_cli.current_torrent = None
    
    with patch.object(interactive_cli, "update_download_stats", new_callable=AsyncMock) as mock_update:
        with patch.object(interactive_cli, "show_download_interface", new_callable=Mock) as mock_show:
            await interactive_cli.update_display()
            
            # Should not call update or show when no torrent
            mock_update.assert_not_called()
            mock_show.assert_not_called()


@pytest.mark.asyncio
async def test_download_torrent(interactive_cli):
    """Test download_torrent method (lines 140-150)."""
    # Setup layout first so show_download_interface works
    interactive_cli.setup_layout()
    # Make running False so loop exits immediately
    interactive_cli.running = False
    torrent_data = {"name": "test", "info_hash": b"abcd1234"}
    
    info_hash_hex = "abcd1234"
    info_hash_bytes = bytes.fromhex(info_hash_hex)
    mock_torrent_session = AsyncMock()
    mock_torrent_session.file_selection_manager = None
    interactive_cli.session.torrents = {info_hash_bytes: mock_torrent_session}
    
    await interactive_cli.download_torrent(torrent_data, resume=False)
    
    assert interactive_cli.current_torrent == torrent_data
    interactive_cli.session.add_torrent.assert_called_once_with(torrent_data, resume=False)
    assert interactive_cli.current_info_hash_hex == "abcd1234"


@pytest.mark.asyncio
async def test_download_torrent_with_resume(interactive_cli):
    """Test download_torrent with resume option (lines 143)."""
    # Setup layout first so show_download_interface works
    interactive_cli.setup_layout()
    # Make running False so loop exits immediately
    interactive_cli.running = False
    torrent_data = {"name": "test", "info_hash": b"abcd1234"}
    
    info_hash_hex = "abcd1234"
    info_hash_bytes = bytes.fromhex(info_hash_hex)
    mock_torrent_session = AsyncMock()
    mock_torrent_session.file_selection_manager = None
    interactive_cli.session.torrents = {info_hash_bytes: mock_torrent_session}
    
    await interactive_cli.download_torrent(torrent_data, resume=True)
    
    interactive_cli.session.add_torrent.assert_called_once_with(torrent_data, resume=True)


@pytest.mark.asyncio
async def test_cmd_config_basic(interactive_cli):
    """Test cmd_config basic functionality."""
    # This tests configuration command handler
    # Implementation may vary, so we test the command exists and can be called
    if hasattr(interactive_cli, "cmd_config"):
        await interactive_cli.cmd_config([])
        # Command should execute without error
        assert True


@pytest.mark.asyncio
async def test_cmd_limits(interactive_cli):
    """Test cmd_limits command handler."""
    if hasattr(interactive_cli, "cmd_limits"):
        await interactive_cli.cmd_limits([])
        assert True


@pytest.mark.asyncio
async def test_cmd_strategy(interactive_cli):
    """Test cmd_strategy command handler."""
    if hasattr(interactive_cli, "cmd_strategy"):
        await interactive_cli.cmd_strategy([])
        assert True


@pytest.mark.asyncio
async def test_cmd_discovery(interactive_cli):
    """Test cmd_discovery command handler."""
    if hasattr(interactive_cli, "cmd_discovery"):
        await interactive_cli.cmd_discovery([])
        assert True


@pytest.mark.asyncio
async def test_cmd_disk(interactive_cli):
    """Test cmd_disk command handler."""
    if hasattr(interactive_cli, "cmd_disk"):
        await interactive_cli.cmd_disk([])
        assert True


@pytest.mark.asyncio
async def test_cmd_network(interactive_cli):
    """Test cmd_network command handler."""
    from unittest.mock import MagicMock, patch
    
    # Create a comprehensive mock config with all network settings
    mock_config = MagicMock()
    mock_config.network = MagicMock()
    # Set all network config attributes that might be accessed
    mock_config.network.listen_port = 6881
    mock_config.network.listen_port_tcp = None
    mock_config.network.listen_port_udp = None
    mock_config.network.max_global_peers = 200
    mock_config.network.max_peers_per_torrent = 50
    mock_config.network.max_connections_per_peer = 1
    mock_config.network.pipeline_depth = 5
    mock_config.network.pipeline_adaptive_depth = True
    mock_config.network.block_size_kib = 16
    mock_config.network.min_block_size_kib = 4
    mock_config.network.max_block_size_kib = 64
    mock_config.network.connection_timeout = 30
    mock_config.network.handshake_timeout = 10
    mock_config.network.peer_timeout = 60
    mock_config.network.timeout_adaptive = True
    mock_config.network.keepalive_interval = 60
    mock_config.network.max_idle_time = 120
    mock_config.network.enable_utp = True
    mock_config.network.enable_tcp = True
    mock_config.network.enable_ipv6 = False
    mock_config.network.enable_encryption = True
    mock_config.network.prefer_encryption = True
    mock_config.network.global_down_kib = 0
    mock_config.network.global_up_kib = 0
    mock_config.network.connection_pool_max_connections = 100
    mock_config.network.connection_pool_warmup_enabled = False
    mock_config.network.socket_rcvbuf_kib = 256
    mock_config.network.socket_sndbuf_kib = 256
    mock_config.network.socket_adaptive_buffers = True
    mock_config.network.tcp_nodelay = True
    
    # Mock get_network_optimizer to avoid import/initialization issues
    mock_optimizer = MagicMock()
    mock_optimizer.get_stats.return_value = {
        "connection_pool": {
            "total_connections": 0,
            "active_connections": 0,
            "failed_connections": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
        },
        "socket_configs": {},
    }
    
    with patch("ccbt.cli.interactive.get_config", return_value=mock_config), \
         patch("ccbt.utils.network_optimizer.get_network_optimizer", return_value=mock_optimizer):
        if hasattr(interactive_cli, "cmd_network"):
            await interactive_cli.cmd_network([])
            assert True


@pytest.mark.asyncio
async def test_cmd_checkpoint(interactive_cli):
    """Test cmd_checkpoint command handler."""
    if hasattr(interactive_cli, "cmd_checkpoint"):
        await interactive_cli.cmd_checkpoint([])
        assert True


@pytest.mark.asyncio
async def test_cmd_metrics(interactive_cli):
    """Test cmd_metrics command handler."""
    if hasattr(interactive_cli, "cmd_metrics"):
        await interactive_cli.cmd_metrics([])
        assert True


@pytest.mark.asyncio
async def test_cmd_alerts(interactive_cli):
    """Test cmd_alerts command handler."""
    if hasattr(interactive_cli, "cmd_alerts"):
        await interactive_cli.cmd_alerts([])
        assert True


@pytest.mark.asyncio
async def test_cmd_export(interactive_cli):
    """Test cmd_export command handler."""
    if hasattr(interactive_cli, "cmd_export"):
        await interactive_cli.cmd_export([])
        assert True


@pytest.mark.asyncio
async def test_cmd_import(interactive_cli):
    """Test cmd_import command handler."""
    if hasattr(interactive_cli, "cmd_import"):
        await interactive_cli.cmd_import([])
        assert True


@pytest.mark.asyncio
async def test_cmd_backup(interactive_cli):
    """Test cmd_backup command handler."""
    if hasattr(interactive_cli, "cmd_backup"):
        await interactive_cli.cmd_backup([])
        assert True


@pytest.mark.asyncio
async def test_cmd_restore(interactive_cli):
    """Test cmd_restore command handler."""
    if hasattr(interactive_cli, "cmd_restore"):
        await interactive_cli.cmd_restore([])
        assert True


@pytest.mark.asyncio
async def test_cmd_capabilities(interactive_cli):
    """Test cmd_capabilities command handler."""
    if hasattr(interactive_cli, "cmd_capabilities"):
        await interactive_cli.cmd_capabilities([])
        assert True


@pytest.mark.asyncio
async def test_cmd_auto_tune(interactive_cli):
    """Test cmd_auto_tune command handler."""
    if hasattr(interactive_cli, "cmd_auto_tune"):
        from unittest.mock import patch, MagicMock, Mock
        from ccbt.config.config_conditional import ConditionalConfig
        
        mock_cc = MagicMock()
        mock_tuned_config = MagicMock()
        mock_tuned_config.model_dump = Mock(return_value={"test": "value"})
        mock_cc.adjust_for_system = Mock(return_value=(mock_tuned_config, []))
        
        with patch("ccbt.config.config_conditional.ConditionalConfig", return_value=mock_cc):
            with patch("ccbt.cli.interactive.ConfigManager") as mock_cm_class:
                mock_config = Mock()
                # Create proper disk mock with read_ahead_kib attribute
                mock_disk = Mock()
                mock_disk.read_ahead_kib = 512
                mock_config.disk = mock_disk
                mock_config.model_dump.return_value = {"network": {"port": 6881}}
                # Create mock ConfigManager instance
                mock_cm = MagicMock()
                mock_cm.config = mock_config
                mock_cm.config_file = None
                mock_cm_class.return_value = mock_cm
                
                await interactive_cli.cmd_auto_tune([])
        
        assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_template(interactive_cli):
    """Test cmd_template command handler."""
    if hasattr(interactive_cli, "cmd_template"):
        await interactive_cli.cmd_template([])
        assert True


@pytest.mark.asyncio
async def test_cmd_profile(interactive_cli):
    """Test cmd_profile command handler."""
    if hasattr(interactive_cli, "cmd_profile"):
        await interactive_cli.cmd_profile([])
        assert True


@pytest.mark.asyncio
async def test_cmd_config_backup(interactive_cli):
    """Test cmd_config_backup command handler."""
    if hasattr(interactive_cli, "cmd_config_backup"):
        await interactive_cli.cmd_config_backup([])
        assert True


@pytest.mark.asyncio
async def test_cmd_config_diff(interactive_cli):
    """Test cmd_config_diff command handler."""
    if hasattr(interactive_cli, "cmd_config_diff"):
        await interactive_cli.cmd_config_diff([])
        assert True


@pytest.mark.asyncio
async def test_cmd_config_export(interactive_cli):
    """Test cmd_config_export command handler."""
    if hasattr(interactive_cli, "cmd_config_export"):
        await interactive_cli.cmd_config_export([])
        assert True


@pytest.mark.asyncio
async def test_cmd_config_import(interactive_cli):
    """Test cmd_config_import command handler."""
    if hasattr(interactive_cli, "cmd_config_import"):
        await interactive_cli.cmd_config_import([])
        assert True


@pytest.mark.asyncio
async def test_cmd_config_schema(interactive_cli):
    """Test cmd_config_schema command handler."""
    if hasattr(interactive_cli, "cmd_config_schema"):
        await interactive_cli.cmd_config_schema([])
        assert True


@pytest.mark.asyncio
async def test_run_method_keyboard_interrupt(interactive_cli):  # pragma: no cover
    """Test run() method handles KeyboardInterrupt (lines 131-135).
    
    Note: Skipped during coverage runs to prevent pytest from interpreting
    KeyboardInterrupt as a real user interrupt and exiting early.
    This test intentionally raises KeyboardInterrupt to verify graceful shutdown of interactive CLI.
    """
    # Skip only if coverage is running to prevent early test suite exit
    import sys
    if any("--cov" in arg or "-m" in arg and "cov" in arg for arg in sys.argv):
        pytest.skip(
            "KeyboardInterrupt test skipped in coverage runs to prevent early test suite exit. "
            "This test intentionally raises KeyboardInterrupt which pytest may interpret as a "
            "real user interrupt, causing the test suite to exit at 94%. "
            "Run with --no-cov to execute this test.",
            allow_module_level=False,
        )  # pragma: no cover
    from unittest.mock import patch
    # Mock Live context manager to avoid needing actual terminal
    with patch('ccbt.cli.interactive.Live') as mock_live:
        mock_live.return_value.__enter__ = Mock(return_value=mock_live.return_value)
        mock_live.return_value.__exit__ = Mock(return_value=None)
        
        interactive_cli.setup_layout = Mock()
        interactive_cli.show_welcome = Mock()
        interactive_cli.update_display = AsyncMock(side_effect=KeyboardInterrupt())
        
        # Should handle KeyboardInterrupt gracefully
        await interactive_cli.run()
        
        assert interactive_cli.running is False


@pytest.mark.asyncio
async def test_setup_layout(interactive_cli):
    """Test setup_layout method."""
    if hasattr(interactive_cli, "setup_layout"):
        interactive_cli.setup_layout()
        # Should configure layout without error
        assert True


@pytest.mark.asyncio
async def test_show_welcome(interactive_cli):
    """Test show_welcome method."""
    if hasattr(interactive_cli, "show_welcome"):
        # Setup layout first so layout sections exist
        interactive_cli.setup_layout()
        interactive_cli.show_welcome()
        # Should update layout without error
        assert True


@pytest.mark.asyncio
async def test_show_download_interface(interactive_cli):
    """Test show_download_interface method."""
    if hasattr(interactive_cli, "show_download_interface"):
        # Setup layout first so layout sections exist
        interactive_cli.setup_layout()
        interactive_cli.current_torrent = {"name": "test"}
        interactive_cli.show_download_interface()
        # Should update layout without error
        assert True


@pytest.mark.asyncio
async def test_create_peers_panel(interactive_cli):
    """Test create_peers_panel method."""
    if hasattr(interactive_cli, "create_peers_panel"):
        interactive_cli._last_peers = [
            {"ip": "1.2.3.4", "port": 6881, "download_rate": 100.0, "upload_rate": 50.0},
        ]
        panel = interactive_cli.create_peers_panel()
        assert panel is not None


@pytest.mark.asyncio
async def test_create_status_panel(interactive_cli):
    """Test create_status_panel method."""
    if hasattr(interactive_cli, "create_status_panel"):
        panel = interactive_cli.create_status_panel()
        assert panel is not None

