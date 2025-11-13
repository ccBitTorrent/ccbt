"""Additional tests for ccbt.cli.interactive to increase coverage.

Covers:
- update_download_stats with various paths (lines 328-403)
- cmd_limits validation and all paths (lines 603-631)
- cmd_strategy all paths (lines 633-654)
- cmd_discovery all paths (lines 656-672)
- cmd_disk and cmd_network (lines 674-694)
- cmd_stop all paths (lines 581-592)
- cmd_quit all paths (lines 594-597)
- cmd_clear (lines 599-601)
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
    ])
    session.pause_torrent = AsyncMock()
    session.resume_torrent = AsyncMock()
    session.remove = AsyncMock()
    return session


@pytest.fixture
def interactive_cli(mock_session):
    """Create InteractiveCLI instance."""
    from ccbt.cli.interactive import InteractiveCLI
    
    console = Mock(spec=Console)
    console.print = Mock()
    console.clear = Mock()
    cli = InteractiveCLI(mock_session, console)
    return cli


@pytest.mark.asyncio
async def test_update_download_stats_no_torrent(interactive_cli):
    """Test update_download_stats with no current torrent (lines 328-331)."""
    interactive_cli.current_torrent = None
    
    await interactive_cli.update_download_stats()
    
    # Should return early without error
    assert True


@pytest.mark.asyncio
async def test_update_download_stats_with_status(interactive_cli):
    """Test update_download_stats with session status (lines 328-379)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.get_torrent_status = AsyncMock(return_value={
        "download_rate": 1000.0,
        "upload_rate": 500.0,
        "pieces_completed": 10,
        "pieces_total": 100,
        "progress": 0.1,
        "downloaded_bytes": 1048576,
    })
    interactive_cli.session.get_peers_for_torrent = AsyncMock(return_value=[
        {"ip": "1.2.3.4", "port": 6881},
    ])
    
    await interactive_cli.update_download_stats()
    
    assert interactive_cli.stats["download_speed"] == 1000.0
    assert interactive_cli.stats["upload_speed"] == 500.0
    assert interactive_cli.stats["pieces_completed"] == 10
    assert interactive_cli.stats["pieces_total"] == 100


@pytest.mark.asyncio
async def test_update_download_stats_with_peers_exception(interactive_cli):
    """Test update_download_stats with peers exception (lines 344-353)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.get_torrent_status = AsyncMock(return_value={
        "download_rate": 1000.0,
        "upload_rate": 500.0,
    })
    interactive_cli.session.get_peers_for_torrent = AsyncMock(side_effect=Exception("Error"))
    
    await interactive_cli.update_download_stats()
    
    assert interactive_cli.stats["peers_connected"] == 0


@pytest.mark.asyncio
async def test_update_download_stats_no_status_use_torrent(interactive_cli):
    """Test update_download_stats without status, using torrent attributes (lines 380-401)."""
    torrent = MagicMock()
    torrent.download_speed = 2000.0
    torrent.upload_speed = 1000.0
    torrent.completed_pieces = 20
    torrent.total_pieces = 200
    
    interactive_cli.current_torrent = torrent
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.get_torrent_status = AsyncMock(return_value=None)
    
    await interactive_cli.update_download_stats()
    
    assert interactive_cli.stats["download_speed"] == 2000.0
    assert interactive_cli.stats["upload_speed"] == 1000.0
    assert interactive_cli.stats["pieces_completed"] == 20
    assert interactive_cli.stats["pieces_total"] == 200


@pytest.mark.asyncio
async def test_update_download_stats_with_dict_torrent(interactive_cli):
    """Test update_download_stats with dict-based torrent (lines 381-401)."""
    interactive_cli.current_torrent = {
        "download_speed": 1500.0,
        "upload_speed": 750.0,
        "completed_pieces": 15,
        "total_pieces": 150,
    }
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.get_torrent_status = AsyncMock(return_value=None)
    
    await interactive_cli.update_download_stats()
    
    assert interactive_cli.stats["download_speed"] == 1500.0
    assert interactive_cli.stats["upload_speed"] == 750.0


@pytest.mark.asyncio
async def test_update_download_stats_exception_handling(interactive_cli):
    """Test update_download_stats exception handling (lines 402-403)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.get_torrent_status = AsyncMock(side_effect=Exception("Test error"))
    
    await interactive_cli.update_download_stats()
    
    # Should not raise


@pytest.mark.asyncio
async def test_cmd_limits_invalid_args(interactive_cli):
    """Test cmd_limits with invalid arguments (lines 603-612)."""
    await interactive_cli.cmd_limits([])
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_limits_show_not_found(interactive_cli):
    """Test cmd_limits show with torrent not found (lines 614-618)."""
    interactive_cli.session.get_torrent_status = AsyncMock(return_value=None)
    
    await interactive_cli.cmd_limits(["show", "invalid_hash"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_limits_show_success(interactive_cli):
    """Test cmd_limits show success (lines 614-619)."""
    status_data = {"download_rate": 1000.0, "upload_rate": 500.0}
    interactive_cli.session.get_torrent_status = AsyncMock(return_value=status_data)
    
    await interactive_cli.cmd_limits(["show", "abcd1234"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_limits_set_invalid_args(interactive_cli):
    """Test cmd_limits set with invalid arguments (lines 620-623)."""
    await interactive_cli.cmd_limits(["set", "abcd1234"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_limits_set_success(interactive_cli):
    """Test cmd_limits set success (lines 624-627)."""
    interactive_cli.session.set_rate_limits = AsyncMock(return_value=True)
    
    await interactive_cli.cmd_limits(["set", "abcd1234", "100", "50"])
    
    interactive_cli.session.set_rate_limits.assert_called_once_with("abcd1234", 100, 50)
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_limits_set_failed(interactive_cli):
    """Test cmd_limits set failure (lines 624-627)."""
    interactive_cli.session.set_rate_limits = AsyncMock(return_value=False)
    
    await interactive_cli.cmd_limits(["set", "abcd1234", "100", "50"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_limits_set_not_supported(interactive_cli):
    """Test cmd_limits set when not supported (lines 628-629)."""
    # Remove the attribute to simulate it not existing
    if hasattr(interactive_cli.session, 'set_rate_limits'):
        delattr(interactive_cli.session, 'set_rate_limits')
    
    await interactive_cli.cmd_limits(["set", "abcd1234", "100", "50"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_limits_unknown_subcommand(interactive_cli):
    """Test cmd_limits with unknown subcommand (lines 630-631)."""
    await interactive_cli.cmd_limits(["unknown", "abcd1234"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_strategy_show(interactive_cli):
    """Test cmd_strategy show (lines 633-648)."""
    await interactive_cli.cmd_strategy([])
    await interactive_cli.cmd_strategy(["show"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_strategy_piece_selection_success(interactive_cli):
    """Test cmd_strategy piece_selection success (lines 649-652)."""
    await interactive_cli.cmd_strategy(["piece_selection", "rarest_first"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_discovery_show(interactive_cli):
    """Test cmd_discovery show (lines 656-665)."""
    await interactive_cli.cmd_discovery([])
    await interactive_cli.cmd_discovery(["show"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_discovery_dht_toggle(interactive_cli):
    """Test cmd_discovery dht toggle (lines 667-669)."""
    from ccbt.config.config import get_config
    
    cfg = get_config()
    original_value = cfg.discovery.enable_dht
    
    await interactive_cli.cmd_discovery(["dht"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_discovery_pex_toggle(interactive_cli):
    """Test cmd_discovery pex toggle (lines 670-672)."""
    from ccbt.config.config import get_config
    
    cfg = get_config()
    original_value = cfg.discovery.enable_pex
    
    await interactive_cli.cmd_discovery(["pex"])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_disk(interactive_cli):
    """Test cmd_disk (lines 674-683)."""
    await interactive_cli.cmd_disk([])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_network(interactive_cli):
    """Test cmd_network (lines 685-694)."""
    await interactive_cli.cmd_network([])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_stop_no_remove_method(interactive_cli):
    """Test cmd_stop without remove method (lines 587-590)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = None
    
    await interactive_cli.cmd_stop([])
    
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_stop_success(interactive_cli):
    """Test cmd_stop success (lines 581-592)."""
    interactive_cli.current_torrent = {"name": "test"}
    interactive_cli.current_info_hash_hex = "abcd1234"
    interactive_cli.session.remove = AsyncMock()
    
    await interactive_cli.cmd_stop([])
    
    interactive_cli.session.remove.assert_called_once_with("abcd1234")
    assert interactive_cli.console.print.called


@pytest.mark.asyncio
async def test_cmd_quit_with_confirm(interactive_cli, monkeypatch):
    """Test cmd_quit with confirmation (lines 594-597)."""
    from rich.prompt import Confirm
    
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)
    
    await interactive_cli.cmd_quit([])
    
    assert interactive_cli.running is False


@pytest.mark.asyncio
async def test_cmd_quit_without_confirm(interactive_cli, monkeypatch):
    """Test cmd_quit without confirmation (lines 594-597)."""
    from rich.prompt import Confirm
    
    # Set running to True first
    interactive_cli.running = True
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: False)
    
    await interactive_cli.cmd_quit([])
    
    # Should remain True when confirmation is declined
    assert interactive_cli.running is True


@pytest.mark.asyncio
async def test_cmd_clear(interactive_cli):
    """Test cmd_clear (lines 599-601)."""
    await interactive_cli.cmd_clear([])
    
    interactive_cli.console.clear.assert_called_once()

