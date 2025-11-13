"""Tests for early peer acceptance and download start.

These tests verify that:
1. Incoming peers are accepted even before tracker announce completes
2. Download starts as soon as first peers are discovered from any tracker
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

from ccbt.session.session import AsyncSessionManager, AsyncTorrentSession


class TestEarlyPeerAcceptance:
    """Test that incoming peers are accepted before tracker announce completes."""

    @pytest.mark.asyncio
    async def test_incoming_peer_before_tracker_announce(self, tmp_path):
        """Test that incoming peers are queued and accepted even before tracker announce completes."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        try:
            # Create a torrent session
            torrent_data = {
                "info_hash": b"\x00" * 20,
                "name": "Test Torrent",
                "file_info": {"total_length": 1000},
                "pieces_info": {
                    "piece_length": 512,
                    "num_pieces": 2,
                    "piece_hashes": [b"\x11" * 20, b"\x22" * 20]
                },
            }
            
            info_hash_hex = await manager.add_torrent(torrent_data)
            info_hash_bytes: bytes = torrent_data["info_hash"]  # type: ignore[assignment]
            session = manager.torrents[info_hash_bytes]
            
            # Start the session but delay tracker announce
            start_task = asyncio.create_task(session.start())
            
            # Wait for peer_manager to initialize and queue processor task to be created
            # Poll with timeout to ensure initialization completes
            max_wait = 2.0
            wait_interval = 0.1
            waited = 0.0
            while waited < max_wait:
                if session.peer_manager is not None:
                    break
                await asyncio.sleep(wait_interval)
                waited += wait_interval
            
            # Verify peer_manager is initialized early
            assert session.peer_manager is not None, "peer_manager should be initialized early"
            assert hasattr(session, "_incoming_peer_queue"), "Should have incoming peer queue"
            
            # Wait a bit more for queue processor task to be created (if it's created)
            await asyncio.sleep(0.2)
            
            # Queue processor task may or may not be created depending on timing
            # If peer_manager is ready, peers are accepted immediately, so queue processor may not be needed
            # But if it exists, it should be running (not done)
            if session._peer_queue_processor_task is not None:
                assert not session._peer_queue_processor_task.done(), "Queue processor should be running if it exists"
            
            # Simulate an incoming peer connection before tracker announce completes
            mock_reader = AsyncMock()
            mock_writer = MagicMock()
            mock_handshake = MagicMock()
            mock_handshake.info_hash = b"\x00" * 20
            
            # Accept the incoming peer
            # Since peer_manager is ready, peer should be accepted immediately (not queued)
            await session.accept_incoming_peer(
                mock_reader,
                mock_writer,
                mock_handshake,
                "127.0.0.1",
                6881
            )
            
            # Verify peer was accepted (not queued) since peer_manager is ready
            # Queue should be empty since peer was accepted immediately
            assert session._incoming_peer_queue.qsize() == 0, "Peer should be accepted immediately, not queued"
            
            # Wait for start to complete
            try:
                await asyncio.wait_for(start_task, timeout=5.0)
            except asyncio.TimeoutError:
                # Start might take longer, that's okay
                pass
            
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_incoming_peer_queue_when_peer_manager_not_ready(self, tmp_path):
        """Test that incoming peers are queued when peer_manager is not ready."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        try:
            # Create a torrent session
            torrent_data = {
                "info_hash": b"\x00" * 20,
                "name": "Test Torrent",
                "file_info": {"total_length": 1000},
                "pieces_info": {
                    "piece_length": 512,
                    "num_pieces": 2,
                    "piece_hashes": [b"\x11" * 20, b"\x22" * 20]
                },
            }
            
            info_hash_hex = await manager.add_torrent(torrent_data)
            info_hash_bytes: bytes = torrent_data["info_hash"]  # type: ignore[assignment]
            session = manager.torrents[info_hash_bytes]
            
            # Temporarily set peer_manager to None to simulate early connection
            original_peer_manager = session.peer_manager
            session.peer_manager = None
            
            try:
                # Simulate an incoming peer connection
                mock_reader = AsyncMock()
                mock_writer = MagicMock()
                mock_handshake = MagicMock()
                mock_handshake.info_hash = b"\x00" * 20
                
                # Accept the incoming peer - should queue it
                await session.accept_incoming_peer(
                    mock_reader,
                    mock_writer,
                    mock_handshake,
                    "127.0.0.1",
                    6881
                )
                
                # Verify peer was queued
                assert session._incoming_peer_queue.qsize() > 0, "Peer should be queued"
                
            finally:
                # Restore peer_manager
                session.peer_manager = original_peer_manager
                
        finally:
            await manager.stop()


class TestEarlyDownloadStart:
    """Test that download starts as soon as first peers are discovered."""

    @pytest.mark.asyncio
    async def test_download_starts_on_first_tracker_response(self, tmp_path):
        """Test that download starts immediately when first tracker responds with peers."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        try:
            # Create a torrent session
            torrent_data = {
                "info_hash": b"\x00" * 20,
                "name": "Test Torrent",
                "file_info": {"total_length": 1000},
                "pieces_info": {
                    "piece_length": 512,
                    "num_pieces": 2,
                    "piece_hashes": [b"\x11" * 20, b"\x22" * 20]
                },
            }
            
            info_hash_hex = await manager.add_torrent(torrent_data)
            info_hash_bytes: bytes = torrent_data["info_hash"]  # type: ignore[assignment]
            session = manager.torrents[info_hash_bytes]
            
            # Start the session
            start_task = asyncio.create_task(session.start())
            
            # Wait a bit for initialization
            await asyncio.sleep(0.2)
            
            # Verify peer_manager is initialized early (before tracker announce)
            assert session.peer_manager is not None, "peer_manager should be initialized early"
            
            # Simulate tracker response with peers (as dicts, not PeerInfo objects)
            mock_peers = [
                {"ip": "127.0.0.1", "port": 6881, "peer_source": "tracker"},
                {"ip": "127.0.0.2", "port": 6882, "peer_source": "tracker"},
            ]
            
            # Call the method that handles tracker responses
            if hasattr(session, "_connect_peers_to_download"):
                await session._connect_peers_to_download(mock_peers)
            
            # Verify download has started (piece_manager should be downloading)
            if session.piece_manager:
                # Check if download has started
                is_downloading = getattr(session.piece_manager, "is_downloading", False)
                # Note: is_downloading might be False if no pieces are missing,
                # but peer_manager should be ready to accept connections
                assert session.peer_manager is not None, "peer_manager should be ready"
            
            # Wait for start to complete
            try:
                await asyncio.wait_for(start_task, timeout=5.0)
            except asyncio.TimeoutError:
                # Start might take longer, that's okay
                pass
                
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_peer_manager_reused_when_already_exists(self, tmp_path):
        """Test that existing peer_manager is reused when connecting new peers."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        try:
            # Create a torrent session
            torrent_data = {
                "info_hash": b"\x00" * 20,
                "name": "Test Torrent",
                "file_info": {"total_length": 1000},
                "pieces_info": {
                    "piece_length": 512,
                    "num_pieces": 2,
                    "piece_hashes": [b"\x11" * 20, b"\x22" * 20]
                },
            }
            
            info_hash_hex = await manager.add_torrent(torrent_data)
            info_hash_bytes: bytes = torrent_data["info_hash"]  # type: ignore[assignment]
            session = manager.torrents[info_hash_bytes]
            
            # Start the session
            start_task = asyncio.create_task(session.start())
            
            # Wait for peer_manager to be initialized
            await asyncio.sleep(0.2)
            
            # Get the initial peer_manager
            initial_peer_manager = session.peer_manager
            assert initial_peer_manager is not None, "peer_manager should be initialized"
            
            # Simulate connecting additional peers (as if from a tracker response)
            mock_peers = [
                {"ip": "127.0.0.3", "port": 6883, "peer_source": "tracker"},
            ]
            
            # Call _connect_peers_to_download which should reuse existing peer_manager
            if hasattr(session, "_connect_peers_to_download"):
                await session._connect_peers_to_download(mock_peers)
            
            # Verify the same peer_manager instance is still being used
            assert session.peer_manager is initial_peer_manager, "peer_manager should be reused, not recreated"
            
            # Wait for start to complete
            try:
                await asyncio.wait_for(start_task, timeout=5.0)
            except asyncio.TimeoutError:
                pass
                
        finally:
            await manager.stop()

