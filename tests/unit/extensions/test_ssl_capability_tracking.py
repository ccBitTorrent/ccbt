"""Unit tests for SSL capability tracking in extension handshake.

Tests SSL capability extraction and storage from extension handshake data.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.extensions, pytest.mark.security]

from ccbt.extensions.manager import ExtensionManager
from ccbt.extensions.ssl import SSLExtension


class TestSSLCapabilityTracking:
    """Tests for SSL capability tracking in ExtensionManager."""

    def test_set_peer_extensions_extracts_ssl_from_m_dict(self):
        """Test that set_peer_extensions extracts SSL capability from 'm' dict."""
        manager = ExtensionManager()
        peer_id = "test_peer_123"
        
        # Extension handshake with SSL in message map
        extensions = {
            "m": {
                "ut_metadata": 1,
                "ssl": 2,  # SSL extension registered with message ID 2
            }
        }
        
        manager.set_peer_extensions(peer_id, extensions)
        
        # Check SSL capability was extracted
        peer_extensions = manager.get_peer_extensions(peer_id)
        assert peer_extensions.get("ssl") is True

    def test_set_peer_extensions_extracts_ssl_from_bytes_m_dict(self):
        """Test that set_peer_extensions handles bytes keys in 'm' dict."""
        manager = ExtensionManager()
        peer_id = "test_peer_456"
        
        # Extension handshake with bytes keys (BEP 10 allows both)
        extensions = {
            b"m": {
                b"ut_metadata": 1,
                b"ssl": 2,
            }
        }
        
        manager.set_peer_extensions(peer_id, extensions)
        
        # Check SSL capability was extracted
        peer_extensions = manager.get_peer_extensions(peer_id)
        assert peer_extensions.get("ssl") is True

    def test_set_peer_extensions_no_ssl_in_m_dict(self):
        """Test that set_peer_extensions returns False when SSL not in 'm' dict."""
        manager = ExtensionManager()
        peer_id = "test_peer_789"
        
        # Extension handshake without SSL
        extensions = {
            "m": {
                "ut_metadata": 1,
                "pex": 2,
            }
        }
        
        manager.set_peer_extensions(peer_id, extensions)
        
        # Check SSL capability is False
        peer_extensions = manager.get_peer_extensions(peer_id)
        assert peer_extensions.get("ssl") is False

    def test_set_peer_extensions_ssl_decode_handshake(self):
        """Test that set_peer_extensions uses SSL extension decode_handshake."""
        manager = ExtensionManager()
        peer_id = "test_peer_ssl_decode"
        
        # Extension handshake with direct SSL extension data
        extensions = {
            "ssl": {
                "supports_ssl": True,
                "version": "1.0",
            }
        }
        
        # Mock SSL extension decode_handshake to return True
        ssl_ext = manager.extensions["ssl"]
        original_decode = ssl_ext.decode_handshake
        ssl_ext.decode_handshake = MagicMock(return_value=True)
        
        try:
            manager.set_peer_extensions(peer_id, extensions)
            
            # Check SSL capability was extracted via decode_handshake
            peer_extensions = manager.get_peer_extensions(peer_id)
            assert peer_extensions.get("ssl") is True
            ssl_ext.decode_handshake.assert_called_once()
        finally:
            ssl_ext.decode_handshake = original_decode

    def test_peer_supports_extension_ssl(self):
        """Test peer_supports_extension returns True for SSL when set."""
        manager = ExtensionManager()
        peer_id = "test_peer_supports"
        
        # Set peer extensions with SSL
        extensions = {
            "m": {
                "ssl": 2,
            }
        }
        manager.set_peer_extensions(peer_id, extensions)
        
        # Check peer_supports_extension
        assert manager.peer_supports_extension(peer_id, "ssl") is True

    def test_peer_supports_extension_ssl_false(self):
        """Test peer_supports_extension returns False for SSL when not set."""
        manager = ExtensionManager()
        peer_id = "test_peer_no_ssl"
        
        # Set peer extensions without SSL
        extensions = {
            "m": {
                "ut_metadata": 1,
            }
        }
        manager.set_peer_extensions(peer_id, extensions)
        
        # Check peer_supports_extension
        assert manager.peer_supports_extension(peer_id, "ssl") is False

    def test_peer_supports_extension_ssl_unknown(self):
        """Test peer_supports_extension returns False for SSL when peer not known."""
        manager = ExtensionManager()
        peer_id = "unknown_peer"
        
        # Check peer_supports_extension for unknown peer
        assert manager.peer_supports_extension(peer_id, "ssl") is False


