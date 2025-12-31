"""Unit tests for PeerEventsBinder."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.session.models import SessionContext
from ccbt.session.peer_events import PeerEventsBinder


class TestPeerEventsBinder:
    """Test PeerEventsBinder functionality."""

    @pytest.fixture
    def ctx(self):
        """Create a mock session context."""
        return SessionContext(
            config=Mock(),
            torrent_data={"info_hash": b"x" * 20},
            output_dir=Mock(),
        )

    @pytest.fixture
    def binder(self, ctx):
        """Create PeerEventsBinder instance."""
        return PeerEventsBinder(ctx)

    @pytest.fixture
    def mock_peer_manager(self):
        """Create a mock peer manager."""
        pm = Mock()
        pm.on_peer_connected = None
        pm.on_peer_disconnected = None
        pm.on_piece_received = None
        pm.on_bitfield_received = None
        return pm

    @pytest.fixture
    def mock_piece_manager(self):
        """Create a mock piece manager."""
        pm = Mock()
        pm.on_piece_completed = None
        pm.on_piece_verified = None
        pm.on_download_complete = None
        return pm

    def test_bind_peer_manager_with_callbacks(self, binder, ctx, mock_peer_manager):
        """Test binding peer manager with callbacks."""
        def on_connected():
            pass

        def on_disconnected():
            pass

        def on_piece():
            pass

        def on_bitfield():
            pass

        binder.bind_peer_manager(
            mock_peer_manager,
            on_peer_connected=on_connected,
            on_peer_disconnected=on_disconnected,
            on_piece_received=on_piece,
            on_bitfield_received=on_bitfield,
        )

        assert mock_peer_manager.on_peer_connected == on_connected
        assert mock_peer_manager.on_peer_disconnected == on_disconnected
        assert mock_peer_manager.on_piece_received == on_piece
        assert mock_peer_manager.on_bitfield_received == on_bitfield
        assert ctx.peer_manager == mock_peer_manager

    def test_bind_peer_manager_without_callbacks(self, binder, ctx, mock_peer_manager):
        """Test binding peer manager without callbacks."""
        binder.bind_peer_manager(mock_peer_manager)

        assert mock_peer_manager.on_peer_connected is None
        assert mock_peer_manager.on_peer_disconnected is None
        assert ctx.peer_manager == mock_peer_manager

    def test_bind_peer_manager_partial_callbacks(self, binder, ctx, mock_peer_manager):
        """Test binding peer manager with partial callbacks."""
        def on_connected():
            pass

        binder.bind_peer_manager(
            mock_peer_manager,
            on_peer_connected=on_connected,
        )

        assert mock_peer_manager.on_peer_connected == on_connected
        assert mock_peer_manager.on_peer_disconnected is None
        assert ctx.peer_manager == mock_peer_manager

    def test_bind_piece_manager_with_callbacks(self, binder, ctx, mock_piece_manager):
        """Test binding piece manager with callbacks."""
        def on_completed(piece_idx: int):
            pass

        def on_verified(piece_idx: int):
            pass

        def on_complete():
            pass

        binder.bind_piece_manager(
            mock_piece_manager,
            on_piece_completed=on_completed,
            on_piece_verified=on_verified,
            on_download_complete=on_complete,
        )

        assert mock_piece_manager.on_piece_completed == on_completed
        assert mock_piece_manager.on_piece_verified == on_verified
        assert mock_piece_manager.on_download_complete == on_complete
        assert ctx.piece_manager == mock_piece_manager

    def test_bind_piece_manager_without_callbacks(self, binder, ctx, mock_piece_manager):
        """Test binding piece manager without callbacks."""
        binder.bind_piece_manager(mock_piece_manager)

        assert mock_piece_manager.on_piece_completed is None
        assert mock_piece_manager.on_piece_verified is None
        assert mock_piece_manager.on_download_complete is None
        assert ctx.piece_manager == mock_piece_manager

    def test_bind_piece_manager_partial_callbacks(self, binder, ctx, mock_piece_manager):
        """Test binding piece manager with partial callbacks."""
        def on_verified(piece_idx: int):
            pass

        binder.bind_piece_manager(
            mock_piece_manager,
            on_piece_verified=on_verified,
        )

        assert mock_piece_manager.on_piece_verified == on_verified
        assert mock_piece_manager.on_piece_completed is None
        assert ctx.piece_manager == mock_piece_manager


































































