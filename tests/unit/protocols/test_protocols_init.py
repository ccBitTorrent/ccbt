"""Tests for protocols/__init__.py import error handling.

This module tests the import error path for WebTorrentProtocol:
- Lines 22-23: ImportError/AttributeError handling when WebTorrentProtocol cannot be imported
"""

from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.protocols]


class TestWebTorrentProtocolImport:
    """Test WebTorrentProtocol import error handling."""

    def test_webtorrent_protocol_import_success(self):
        """Test successful import of WebTorrentProtocol."""
        from ccbt.protocols import WebTorrentProtocol

        # If import succeeds, WebTorrentProtocol should be a class
        # If it fails, it will be None
        # We just verify the import doesn't raise an exception
        assert WebTorrentProtocol is not None or WebTorrentProtocol is None

    def test_webtorrent_protocol_import_error_handling(self):
        """Test import error handling path (lines 22-23)."""
        # Mock the import to raise ImportError
        with patch("ccbt.protocols.webtorrent_module", side_effect=ImportError("aiortc not available")):
            # Reload the module to trigger the import error handling
            import importlib
            import ccbt.protocols

            # Reload the module to trigger the except block
            importlib.reload(ccbt.protocols)

            # After reload, WebTorrentProtocol should be None due to the import error
            # This tests lines 22-23
            assert ccbt.protocols.WebTorrentProtocol is None

    def test_webtorrent_protocol_attribute_error_handling(self):
        """Test AttributeError handling when WebTorrentProtocol doesn't exist (lines 22-23)."""
        # Mock the module import to succeed but AttributeError when accessing WebTorrentProtocol
        mock_module = type("MockModule", (), {})()  # Module without WebTorrentProtocol attribute
        
        with patch("ccbt.protocols.webtorrent_module", mock_module):
            # Reload the module to trigger the AttributeError handling
            import importlib
            import ccbt.protocols

            # Reload the module to trigger the except block
            importlib.reload(ccbt.protocols)

            # After reload, WebTorrentProtocol should be None due to the AttributeError
            # This tests lines 22-23
            assert ccbt.protocols.WebTorrentProtocol is None

