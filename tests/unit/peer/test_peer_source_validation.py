"""Unit tests for peer source validation in private torrents."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from ccbt.models import PeerInfo
from ccbt.peer.async_peer_connection import (
    AsyncPeerConnectionManager,
    PeerConnectionError,
)


@pytest_asyncio.fixture(scope="function")
async def peer_manager():
    """Create peer connection manager with proper isolation."""
    from unittest.mock import MagicMock, patch
    import asyncio
    import logging
    
    piece_manager = MagicMock()
    torrent_data = {"info_hash": b"\x00" * 20}
    
    # Mock config to disable network components
    with patch("ccbt.peer.async_peer_connection.get_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.network.max_peers_per_torrent = 50
        mock_config.network.connection_pool_max_connections = 200
        mock_config.network.connection_pool_max_idle_time = 300.0
        mock_config.network.connection_pool_health_check_interval = 60.0
        mock_config.network.connection_pool_warmup_enabled = False
        mock_config.network.connection_pool_warmup_count = 5
        mock_config.network.circuit_breaker_enabled = False
        mock_config.network.circuit_breaker_failure_threshold = 5
        mock_config.network.circuit_breaker_recovery_timeout = 60.0
        mock_config.network.connection_timeout = 10.0
        mock_config.network.pipeline_depth = 5
        mock_config.network.enable_utp = False  # Disable UTP to avoid port binding
        mock_config.network.enable_webtorrent = False
        mock_config.network.max_concurrent_connection_attempts = 20  # Required for semaphore
        mock_config.security.enable_encryption = False
        mock_config.security.encryption_mode = "disabled"
        # Add limits config (required for per-peer rate limiting)
        mock_config.limits = MagicMock()
        mock_config.limits.per_peer_up_kib = 0  # Unlimited
        mock_config.limits.per_peer_down_kib = 0  # Unlimited
        mock_get_config.return_value = mock_config
        
        # Patch all network-related components
        with patch("ccbt.peer.async_peer_connection.AsyncPeerConnectionManager._setup_utp_incoming_handler"), \
             patch("asyncio.open_connection") as mock_open_conn:  # Mock socket creation
            mock_open_conn.side_effect = ConnectionError("Mocked connection")
            
            manager = AsyncPeerConnectionManager(
                piece_manager=piece_manager,
                torrent_data=torrent_data,
            )
            
            # Don't start manager - tests only need _connect_to_peer which doesn't require start()
            # Starting would launch background loops that need real config values
            # But we need _running = True to prevent early return in _connect_to_peer
            manager._running = True
            
            yield manager
            
            # Enhanced cleanup with timeout
            try:
                await asyncio.wait_for(manager.stop(), timeout=2.0)
            except (asyncio.TimeoutError, Exception) as e:
                # Force cleanup if stop() times out
                manager._running = False
                # Cancel any remaining tasks
                if hasattr(manager, "_connection_tasks"):
                    for task in list(manager._connection_tasks.values()):
                        if not task.done():
                            task.cancel()
                # Wait briefly for cleanup
                await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_private_torrent_rejects_dht_peer(peer_manager):
    """Test private torrent rejects DHT peer."""
    peer_manager._is_private = True
    
    dht_peer = PeerInfo(
        ip="192.168.1.2",
        port=6882,
        peer_source="dht"
    )
    
    with pytest.raises(PeerConnectionError, match="Private torrents only accept tracker-provided peers"):
        await peer_manager._connect_to_peer(dht_peer)


@pytest.mark.asyncio
async def test_private_torrent_rejects_pex_peer(peer_manager):
    """Test private torrent rejects PEX peer."""
    peer_manager._is_private = True
    
    pex_peer = PeerInfo(
        ip="192.168.1.3",
        port=6883,
        peer_source="pex"
    )
    
    with pytest.raises(PeerConnectionError, match="rejecting peer from pex"):
        await peer_manager._connect_to_peer(pex_peer)


@pytest.mark.asyncio
async def test_private_torrent_rejects_lsd_peer(peer_manager):
    """Test private torrent rejects LSD peer."""
    peer_manager._is_private = True
    
    lsd_peer = PeerInfo(
        ip="192.168.1.4",
        port=6884,
        peer_source="lsd"
    )
    
    with pytest.raises(PeerConnectionError, match="rejecting peer from lsd"):
        await peer_manager._connect_to_peer(lsd_peer)


@pytest.mark.asyncio
async def test_private_torrent_accepts_tracker_peer(peer_manager):
    """Test private torrent accepts tracker peer."""
    peer_manager._is_private = True
    
    tracker_peer = PeerInfo(
        ip="192.168.1.1",
        port=6881,
        peer_source="tracker"
    )
    
    # Mock connection attempt to avoid network calls
    # _connect_to_peer uses asyncio.open_connection internally, so we patch that
    with patch("asyncio.open_connection") as mock_open_conn:
        mock_open_conn.side_effect = ConnectionError("Test connection failure")
        
        # Should not raise PeerConnectionError about peer source
        try:
            await peer_manager._connect_to_peer(tracker_peer)
        except PeerConnectionError as e:
            # If PeerConnectionError is raised, it should NOT be about peer source
            assert "Private torrents only accept tracker-provided peers" not in str(e)
        except Exception:
            # Network errors are OK
            pass


@pytest.mark.asyncio
async def test_private_torrent_accepts_manual_peer(peer_manager):
    """Test private torrent accepts manual peer."""
    peer_manager._is_private = True
    
    manual_peer = PeerInfo(
        ip="192.168.1.5",
        port=6885,
        peer_source="manual"
    )
    
    # Mock connection attempt to avoid network calls
    # _connect_to_peer uses asyncio.open_connection internally, so we patch that
    with patch("asyncio.open_connection") as mock_open_conn:
        mock_open_conn.side_effect = ConnectionError("Test connection failure")
        
        # Should not raise PeerConnectionError about peer source
        try:
            await peer_manager._connect_to_peer(manual_peer)
        except PeerConnectionError as e:
            # If PeerConnectionError is raised, it should NOT be about peer source
            assert "Private torrents only accept tracker-provided peers" not in str(e)
        except Exception:
            # Network errors are OK
            pass


@pytest.mark.asyncio
async def test_non_private_torrent_accepts_all_peers(peer_manager):
    """Test non-private torrent accepts peers from any source."""
    peer_manager._is_private = False
    
    dht_peer = PeerInfo(
        ip="192.168.1.6",
        port=6886,
        peer_source="dht"
    )
    
    # Mock connection attempt to avoid network calls
    # _connect_to_peer uses asyncio.open_connection internally, so we patch that
    with patch("asyncio.open_connection") as mock_open_conn:
        mock_open_conn.side_effect = ConnectionError("Test connection failure")
        
        # Should not raise PeerConnectionError about peer source
        try:
            await peer_manager._connect_to_peer(dht_peer)
        except PeerConnectionError as e:
            # If PeerConnectionError is raised, it should NOT be about peer source
            assert "Private torrents only accept tracker-provided peers" not in str(e)
        except Exception:
            # Network errors are OK
            pass


@pytest.mark.asyncio
async def test_private_torrent_rejects_unknown_source(peer_manager):
    """Test private torrent rejects peer with unknown source."""
    peer_manager._is_private = True
    
    unknown_peer = PeerInfo(
        ip="192.168.1.7",
        port=6887,
        peer_source=None  # No source specified
    )
    
    with pytest.raises(PeerConnectionError, match="rejecting peer from unknown"):
        await peer_manager._connect_to_peer(unknown_peer)


@pytest.mark.asyncio
async def test_private_torrent_logs_warning(peer_manager):
    """Test private torrent logs warning when rejecting peer."""
    peer_manager._is_private = True
    
    dht_peer = PeerInfo(
        ip="192.168.1.8",
        port=6888,
        peer_source="dht"
    )
    
    with patch.object(peer_manager.logger, "warning") as mock_warning:
        try:
            await peer_manager._connect_to_peer(dht_peer)
        except PeerConnectionError:
            pass
        
        # Verify warning was logged
        mock_warning.assert_called_once()
        assert "Rejecting peer" in str(mock_warning.call_args)
        assert "dht" in str(mock_warning.call_args).lower()

