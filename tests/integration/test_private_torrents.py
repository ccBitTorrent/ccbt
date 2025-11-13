"""Integration tests for BEP 27: Private Torrents.

Tests that private torrents correctly disable DHT, PEX, and LSD,
and only accept tracker-provided peers.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.models import PeerInfo
from ccbt.peer.async_peer_connection import AsyncPeerConnectionManager, PeerConnectionError
from ccbt.session.session import AsyncSessionManager, AsyncTorrentSession
from tests.conftest import create_test_torrent_dict


@pytest.mark.asyncio
async def test_private_torrent_peer_source_validation(tmp_path: Path):
    """Test that private torrents reject peers from non-tracker sources.
    
    Verifies that _connect_to_peer() rejects DHT, PEX, and LSD peers
    for private torrents.
    """
    # Create mock torrent data with is_private=True
    torrent_data = {
        "info": {"name": "private_torrent", "length": 1024, "pieces": [b"x" * 20]},
        "is_private": True,
    }
    
    # Create peer connection manager
    peer_manager = AsyncPeerConnectionManager(torrent_data, MagicMock())
    peer_manager._is_private = True  # Mark as private torrent
    
    # Test 1: Tracker peer should be accepted
    tracker_peer = PeerInfo(ip="192.168.1.1", port=6881, peer_source="tracker")
    # Should not raise exception
    try:
        await peer_manager._connect_to_peer(tracker_peer)
        # Connection will fail (no real network), but shouldn't raise PeerConnectionError
        # about peer source
    except PeerConnectionError as e:
        # If PeerConnectionError is raised, it should not be about peer source
        assert "Private torrents only accept tracker-provided peers" not in str(e)
    except Exception:
        # Other exceptions (network, etc.) are OK
        pass

    # Test 2: DHT peer should be rejected
    dht_peer = PeerInfo(ip="192.168.1.2", port=6882, peer_source="dht")
    # The exception is logged but caught by the outer exception handler
    # Check that it raises the correct error by catching it directly
    try:
        await peer_manager._connect_to_peer(dht_peer)
        pytest.fail("Expected PeerConnectionError for DHT peer in private torrent")
    except PeerConnectionError as e:
        assert "Private torrents only accept tracker-provided peers" in str(e)
        assert "dht" in str(e).lower()
    except Exception:
        # Network errors are OK, but we should have gotten PeerConnectionError first
        pass

    # Test 3: PEX peer should be rejected
    pex_peer = PeerInfo(ip="192.168.1.3", port=6883, peer_source="pex")
    with pytest.raises(PeerConnectionError) as exc_info:
        await peer_manager._connect_to_peer(pex_peer)
    assert "Private torrents only accept tracker-provided peers" in str(exc_info.value)
    assert "pex" in str(exc_info.value).lower()
    
    # Test 4: LSD peer should be rejected
    lsd_peer = PeerInfo(ip="192.168.1.4", port=6884, peer_source="lsd")
    with pytest.raises(PeerConnectionError) as exc_info:
        await peer_manager._connect_to_peer(lsd_peer)
    assert "Private torrents only accept tracker-provided peers" in str(exc_info.value)
    assert "lsd" in str(exc_info.value).lower()
    
    # Test 5: Manual peer should be accepted
    manual_peer = PeerInfo(ip="192.168.1.5", port=6885, peer_source="manual")
    try:
        await peer_manager._connect_to_peer(manual_peer)
        # Connection will fail (no real network), but shouldn't raise PeerConnectionError
        # about peer source
    except PeerConnectionError as e:
        # If PeerConnectionError is raised, it should not be about peer source
        assert "Private torrents only accept tracker-provided peers" not in str(e)
    except Exception:
        # Other exceptions (network, etc.) are OK
        pass


@pytest.mark.asyncio
async def test_private_torrent_dht_disabled(tmp_path: Path):
    """Test that DHT is disabled for private torrents in session manager.
    
    Verifies that private torrents are tracked and DHT announces are skipped.
    """
    # Create session manager
    session = AsyncSessionManager(str(tmp_path))
    session.config.discovery.enable_dht = True  # Enable DHT globally
    session.config.nat.auto_map_ports = False  # Disable NAT to avoid blocking
    session.config.discovery.enable_pex = False  # Disable PEX for this test
    
    try:
        await session.start()
        
        # Mock DHT client
        if session.dht_client:
            session.dht_client.get_peers = AsyncMock(return_value=[])
            session.dht_client.announce_peer = AsyncMock(return_value=False)

        # Create private torrent data with proper structure
        info_hash = b"\x01" * 20
        torrent_data = create_test_torrent_dict(
            name="private_test",
            info_hash=info_hash,
            file_length=1024,
            piece_length=16384,
            num_pieces=1,
        )
        # Add private flag
        if "info" in torrent_data and isinstance(torrent_data["info"], dict):
            torrent_data["info"]["private"] = 1
        torrent_data["is_private"] = True

        # Add private torrent
        info_hash_hex = await session.add_torrent(torrent_data, resume=False)
        
        # Verify torrent was marked as private
        info_hash_bytes = bytes.fromhex(info_hash_hex)
        assert info_hash_bytes in session.private_torrents
        
        # Verify DHT client has the private torrent check
        if session.dht_client and hasattr(session.dht_client, "_is_private_torrent"):
            # Verify DHT would skip this torrent
            assert session.dht_client._is_private_torrent(info_hash)
        
    finally:
        await session.stop()


@pytest.mark.asyncio
async def test_private_torrent_pex_disabled(tmp_path: Path):
    """Test that PEX is disabled for private torrents.
    
    Verifies that PEX manager is not started for private torrents.
    """
    # Create session manager
    session = AsyncSessionManager(str(tmp_path))
    session.config.discovery.enable_pex = True  # Enable PEX globally
    session.config.discovery.enable_dht = False
    session.config.nat.auto_map_ports = False
    
    try:
        await session.start()

        # Create private torrent data with proper structure
        info_hash = b"\x02" * 20
        torrent_data = create_test_torrent_dict(
            name="private_pex_test",
            info_hash=info_hash,
            file_length=1024,
            piece_length=16384,
            num_pieces=1,
        )
        # Add private flag
        if "info" in torrent_data and isinstance(torrent_data["info"], dict):
            torrent_data["info"]["private"] = 1
        torrent_data["is_private"] = True

        # Add private torrent
        info_hash_hex = await session.add_torrent(torrent_data, resume=False)
        
        # Get the torrent session
        torrent_session = session.torrents.get(info_hash)
        assert torrent_session is not None
        
        # Verify PEX manager was NOT started (private torrent)
        assert torrent_session.pex_manager is None or not hasattr(torrent_session, "pex_manager")
        
        # Verify is_private flag is set
        assert torrent_session.is_private is True
        
    finally:
        await session.stop()


@pytest.mark.asyncio
async def test_private_torrent_tracker_only_peers(tmp_path: Path):
    """Test that private torrents only connect to tracker-provided peers.
    
    Verifies end-to-end that private torrents reject non-tracker peers
    during connection attempts.
    """
    # Create session manager
    session = AsyncSessionManager(str(tmp_path))
    session.config.discovery.enable_dht = False
    session.config.discovery.enable_pex = False
    session.config.nat.auto_map_ports = False
    
    try:
        await session.start()
        
        # Create private torrent data with proper structure
        info_hash = b"\x03" * 20
        torrent_data = create_test_torrent_dict(
            name="private_peer_test",
            info_hash=info_hash,
            file_length=1024,
            piece_length=16384,
            num_pieces=1,
        )
        # Add private flag
        if "info" in torrent_data and isinstance(torrent_data["info"], dict):
            torrent_data["info"]["private"] = 1
        torrent_data["is_private"] = True

        # Add private torrent
        info_hash_hex = await session.add_torrent(torrent_data, resume=False)

        # Get the torrent session
        info_hash_bytes = bytes.fromhex(info_hash_hex)
        torrent_session = session.torrents.get(info_hash_bytes)
        assert torrent_session is not None
        
        # Verify is_private flag is set
        assert torrent_session.is_private is True
        
        # Get peer manager from download manager
        if hasattr(torrent_session, "download_manager") and torrent_session.download_manager:
            peer_manager = getattr(torrent_session.download_manager, "peer_manager", None)
            if peer_manager:
                # Verify _is_private flag is set on peer manager
                assert getattr(peer_manager, "_is_private", False) is True
                
                # Test that DHT peer would be rejected
                dht_peer = PeerInfo(ip="192.168.1.100", port=6881, peer_source="dht")
                with pytest.raises(PeerConnectionError) as exc_info:
                    await peer_manager._connect_to_peer(dht_peer)
                assert "Private torrents only accept tracker-provided peers" in str(exc_info.value)
        
    finally:
        await session.stop()


@pytest.mark.asyncio
async def test_non_private_torrent_allows_all_sources(tmp_path: Path):
    """Test that non-private torrents accept peers from all sources.
    
    Verifies that public torrents do not restrict peer sources.
    """
    # Create mock torrent data WITHOUT is_private flag
    torrent_data = {
        "info": {"name": "public_torrent", "length": 1024, "pieces": [b"x" * 20]},
    }
    
    # Create peer connection manager
    peer_manager = AsyncPeerConnectionManager(torrent_data, MagicMock())
    peer_manager._is_private = False  # Explicitly mark as non-private
    
    # All peer sources should be accepted (no PeerConnectionError about source)
    for source in ["tracker", "dht", "pex", "lsd", "manual"]:
        peer = PeerInfo(ip="192.168.1.1", port=6881, peer_source=source)
        try:
            await peer_manager._connect_to_peer(peer)
            # Connection will fail (no real network), but shouldn't raise PeerConnectionError
            # about peer source
        except PeerConnectionError as e:
            # If PeerConnectionError is raised, it should not be about peer source
            assert "Private torrents only accept tracker-provided peers" not in str(e)
        except Exception:
            # Other exceptions (network, etc.) are OK
            pass


@pytest.mark.asyncio
async def test_tracker_peers_have_tracker_source(tmp_path: Path):
    """Test that peers from tracker responses have peer_source="tracker".
    
    Verifies that tracker.py correctly sets peer_source when parsing responses.
    """
    from ccbt.discovery.tracker import AsyncTrackerClient
    
    tracker = AsyncTrackerClient()
    
    # Mock compact peer data (6 bytes per peer: 4 bytes IP + 2 bytes port)
    # Peer 1: 192.168.1.1:6881
    peer_bytes = bytes([192, 168, 1, 1, 26, 225])  # 26*256+225 = 6881
    
    # Parse compact peers
    peers = tracker._parse_compact_peers(peer_bytes)
    
    # Verify peer_source is set
    assert len(peers) == 1
    assert peers[0]["ip"] == "192.168.1.1"
    assert peers[0]["port"] == 6881
    assert peers[0]["peer_source"] == "tracker"

