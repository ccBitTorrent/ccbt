"""Tests for session/__init__.py lazy imports.

This module tests the __getattr__ function for lazy imports:
- Lines 24-26: TorrentParser import
- Lines 35-40: Path import and AttributeError for invalid attributes
"""

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]


class TestLazyImports:
    """Test lazy import functionality via __getattr__."""

    def test_import_async_dht_client(self):
        """Test importing AsyncDHTClient via lazy import (line 19-22)."""
        # This should trigger __getattr__("AsyncDHTClient")
        from ccbt.session import AsyncDHTClient

        # Verify it's the correct class
        from ccbt.discovery.dht import AsyncDHTClient as DirectImport

        assert AsyncDHTClient is DirectImport

    def test_import_torrent_parser(self):
        """Test importing TorrentParser via lazy import (lines 24-26)."""
        # This should trigger __getattr__("TorrentParser")
        from ccbt.session import TorrentParser

        # Verify it's the correct class
        from ccbt.core.torrent import TorrentParser as DirectImport

        assert TorrentParser is DirectImport

    def test_import_parse_magnet(self):
        """Test importing parse_magnet via lazy import (lines 27-30)."""
        # This should trigger __getattr__("parse_magnet")
        from ccbt.session import parse_magnet

        # Verify it's the correct function
        from ccbt.core.magnet import parse_magnet as DirectImport

        assert parse_magnet is DirectImport

    def test_import_build_minimal_torrent_data(self):
        """Test importing build_minimal_torrent_data via lazy import (lines 31-34)."""
        # This should trigger __getattr__("build_minimal_torrent_data")
        from ccbt.session import build_minimal_torrent_data

        # Verify it's the correct function
        from ccbt.core.magnet import build_minimal_torrent_data as DirectImport

        assert build_minimal_torrent_data is DirectImport

    def test_import_path(self):
        """Test importing Path via lazy import (lines 35-38)."""
        # This should trigger __getattr__("Path")
        from ccbt.session import Path

        # Verify it's pathlib.Path
        from pathlib import Path as DirectImport

        assert Path is DirectImport

    def test_invalid_attribute_raises_error(self):
        """Test that accessing invalid attribute raises AttributeError (lines 39-40)."""
        import ccbt.session

        # Accessing a non-existent attribute should raise AttributeError
        with pytest.raises(AttributeError, match="module 'ccbt.session' has no attribute 'InvalidAttribute'"):
            _ = ccbt.session.InvalidAttribute

