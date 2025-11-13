"""Additional tests for missing coverage lines in async_main.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ccbt.session.download_manager import AsyncDownloadManager


@pytest.mark.unit
@pytest.mark.session
class TestAsyncMainMissingCoverage:
    """Test specific missing coverage lines in async_main.py."""

    @pytest.mark.asyncio
    async def test_start_download_exception_handling(self, tmp_path):
        """Test start_download lines 140-141: Exception handling when peer_manager creation fails."""
        td = {
            "name": "test",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }
        
        manager = AsyncDownloadManager(td, str(tmp_path))
        await manager.start()
        
        # Mock AsyncPeerConnectionManager to raise exception
        with patch("ccbt.session.download_manager.AsyncPeerConnectionManager") as mock_peer_mgr:
            mock_peer_mgr.side_effect = RuntimeError("Failed to create peer manager")
            
            # start_download should handle the exception
            with pytest.raises(RuntimeError):
                await manager.start_download([{"ip": "127.0.0.1", "port": 6881}])

    @pytest.mark.asyncio
    async def test_main_error_handling(self, tmp_path, tmp_path_factory):
        """Test main() lines 482-484: Error handling in main function."""
        from ccbt.cli.main import main
        
        # Create a test torrent file
        test_file = tmp_path / "test.torrent"
        test_file.write_bytes(b"d4:infod6:lengthi100e4:name4:test12:piece lengthi16384e6:pieces20:xxxxxxxxxxxxxxxxxxxxee")
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Test with invalid torrent file
        with patch("sys.argv", ["ccbt", "download", str(test_file), "-o", str(output_dir)]):
            with pytest.raises(SystemExit):
                main()

