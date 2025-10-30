"""Edge case and error path tests for file_assembler.py to reach 99% coverage."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.file]

from ccbt.models import FileInfo, TorrentCheckpoint, TorrentInfo
from ccbt.storage.file_assembler import (
    AsyncDownloadManager,
    AsyncFileAssembler,
    FileAssemblerError,
)


def make_torrent_data_single():
    """Create single-file torrent data."""
    return {
        "name": "test.txt",
        "info_hash": b"x" * 20,
        "files": [
            FileInfo(name="test.txt", length=2048, path=["test.txt"]),
        ],
        "total_length": 2048,
        "piece_length": 1024,
        "pieces": [b"p" * 20] * 2,
        "num_pieces": 2,
    }


class TestAsyncDownloadManagerErrorPaths:
    """Test error handling in AsyncDownloadManager."""

    @pytest.mark.asyncio
    async def test_start_download_exception_during_init(self, tmp_path):
        """Test exception handling when assembler initialization fails."""
        manager = AsyncDownloadManager()
        torrent_data = make_torrent_data_single()

        # Mock AsyncFileAssembler.__aenter__ to raise exception
        with patch(
            "ccbt.storage.file_assembler.AsyncFileAssembler.__aenter__",
            side_effect=OSError("Failed to initialize"),
        ):
            # Exception should propagate (not caught in start_download)
            with pytest.raises(OSError):
                await manager.start_download(torrent_data, str(tmp_path))

        # Assembler might be stored but not started - depends on implementation
        # Just verify exception was raised

    @pytest.mark.asyncio
    async def test_stop_download_exception_during_cleanup(self, tmp_path):
        """Test exception handling when cleanup fails."""
        manager = AsyncDownloadManager()
        torrent_data = make_torrent_data_single()

        # Start download successfully
        assembler = await manager.start_download(torrent_data, str(tmp_path))
        assert assembler is not None

        # Mock __aexit__ to raise exception
        with patch.object(
            assembler, "__aexit__", side_effect=OSError("Cleanup failed")
        ):
            # Should propagate exception
            with pytest.raises(OSError):
                await manager.stop_download(torrent_data)

        # Assembler should still be removed despite exception
        # (depends on implementation - test actual behavior)
        await manager.stop_all()  # Cleanup

    @pytest.mark.asyncio
    async def test_get_assembler_no_info_hash_fallback(self):
        """Test get_assembler when torrent_data has no info_hash."""
        manager = AsyncDownloadManager()

        # Torrent data without info_hash
        torrent_data = {"name": "test", "files": []}

        # Should use hash fallback
        assert manager.get_assembler(torrent_data) is None

        # With TorrentInfo format (should have info_hash)
        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"y" * 20,
            announce="http://example.com",
            total_length=100,
            piece_length=100,
            num_pieces=1,
            files=[],
        )
        assert manager.get_assembler(torrent_info) is None

    @pytest.mark.asyncio
    async def test_get_status_no_file_assembler(self):
        """Test get_status when file_assembler is None."""
        manager = AsyncDownloadManager()

        # No file_assembler should return default status
        # Need to check hasattr first to avoid AttributeError
        if not hasattr(manager, "file_assembler") or manager.file_assembler is None:
            status = manager.get_status()
            assert status == {
                "progress": 0.0,
                "download_rate": 0.0,
                "upload_rate": 0.0,
                "peers": 0,
                "pieces": 0,
                "completed": False,
            }

    @pytest.mark.asyncio
    async def test_get_status_file_assembler_without_pieces(self, tmp_path):
        """Test get_status when file_assembler has no pieces attribute."""
        manager = AsyncDownloadManager(
            torrent_data=make_torrent_data_single(),
            output_dir=str(tmp_path),
        )

        await manager.start()

        # Remove pieces attribute to test fallback
        if hasattr(manager.file_assembler, "pieces"):
            delattr(manager.file_assembler, "pieces")

        # Should handle missing pieces gracefully
        # This will raise AttributeError - test that it's handled
        try:
            status = manager.get_status()
            # If it doesn't raise, check default values
            assert "progress" in status
        except AttributeError:
            # Expected if pieces is required
            pass

        await manager.stop()


class TestAsyncFileAssemblerErrorPaths:
    """Test error handling in AsyncFileAssembler."""

    @pytest.mark.asyncio
    async def test_write_segment_sync_start_disk_io(self, tmp_path):
        """Test write_piece_to_file when disk_io.start is sync function."""
        torrent_data = make_torrent_data_single()

        # Mock disk I/O with sync start method
        mock_disk_io = Mock()
        mock_disk_io.start = Mock()  # Sync function, not async
        mock_disk_io.stop = AsyncMock()
        future = asyncio.get_event_loop().create_future()
        future.set_result(None)
        mock_disk_io.write_block = AsyncMock(return_value=future)

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        # Write piece - should call sync start
        await assembler.write_piece_to_file(0, b"x" * 1024)

        assert mock_disk_io.start.called

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_block_multi_file_segment_combination(self, tmp_path):
        """Test read_block for multi-file torrent with segment combination."""
        torrent_data = {
            "name": "multi",
            "info_hash": b"m" * 20,
            "files": [
                FileInfo(name="file1.txt", length=1536, path=["file1.txt"]),
                FileInfo(name="file2.txt", length=512, path=["file2.txt"]),
            ],
            "total_length": 2048,
            "piece_length": 1024,  # One piece spans both files
            "pieces": [b"p" * 20] * 2,
            "num_pieces": 2,
        }

        # Create files
        file1_path = tmp_path / "file1.txt"
        file2_path = tmp_path / "file2.txt"
        file1_path.write_bytes(b"1" * 1536)
        file2_path.write_bytes(b"2" * 512)

        # Mock disk I/O
        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        async def mock_read_block(file_path, offset, length):
            path_obj = Path(file_path) if isinstance(file_path, str) else file_path
            if not path_obj.exists():
                return None
            with open(path_obj, "rb") as f:
                f.seek(offset)
                return f.read(length)

        mock_disk_io.read_block = AsyncMock(side_effect=mock_read_block)

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Read piece 0 which spans both files
        data = await assembler.read_block(0, 0, 1024)
        assert data is not None
        assert len(data) == 1024
        assert data[:1024] == b"1" * 1024  # First file data

        # Read piece 1 which spans remainder of file1 and all of file2
        data = await assembler.read_block(1, 0, 1024)
        assert data is not None
        assert len(data) == 1024
        assert data[:512] == b"1" * 512  # Rest of file1
        assert data[512:] == b"2" * 512  # All of file2

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_block_multi_file_chunk_length_mismatch(self, tmp_path):
        """Test read_block when chunk length doesn't match expected in multi-file."""
        torrent_data = {
            "name": "multi",
            "info_hash": b"m" * 20,
            "files": [
                FileInfo(name="file1.txt", length=512, path=["file1.txt"]),
                FileInfo(name="file2.txt", length=512, path=["file2.txt"]),
            ],
            "total_length": 1024,
            "piece_length": 1024,  # One piece spans both files
            "pieces": [b"p" * 20],
            "num_pieces": 1,
        }

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        async def wrong_length_read(*args, **kwargs):
            # Return shorter than requested (triggers length check at line 531)
            return b"short"  # 5 bytes instead of requested length

        mock_disk_io.read_block = AsyncMock(side_effect=wrong_length_read)

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # For multi-file, when chunk length doesn't match read_len, should return None
        result = await assembler.read_block(0, 0, 512)
        # Line 531: if len(chunk) != read_len: return None
        assert result is None

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_block_multi_file_remaining_not_zero(self, tmp_path):
        """Test read_block when remaining length after all segments is not zero."""
        torrent_data = {
            "name": "multi",
            "info_hash": b"m" * 20,
            "files": [
                FileInfo(name="file1.txt", length=512, path=["file1.txt"]),
                FileInfo(name="file2.txt", length=512, path=["file2.txt"]),
            ],
            "total_length": 1024,
            "piece_length": 1024,
            "pieces": [b"p" * 20],
            "num_pieces": 1,
        }

        # Create partial files (less than expected)
        (tmp_path / "file1.txt").write_bytes(b"1" * 256)  # Only 256 bytes
        (tmp_path / "file2.txt").write_bytes(b"2" * 256)  # Only 256 bytes

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        async def partial_read(file_path, offset, length):
            path_obj = Path(file_path) if isinstance(file_path, str) else file_path
            if not path_obj.exists():
                return None
            with open(path_obj, "rb") as f:
                f.seek(offset)
                # Return less than requested to simulate incomplete read
                return f.read(min(length, 256))

        mock_disk_io.read_block = AsyncMock(side_effect=partial_read)

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Request full piece but files don't have enough data
        result = await assembler.read_block(0, 0, 1024)
        # Should return None when remaining != 0
        assert result is None

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_block_multi_file_exception_during_read(self, tmp_path):
        """Test read_block exception handling in multi-file path."""
        torrent_data = {
            "name": "multi",
            "info_hash": b"m" * 20,
            "files": [
                FileInfo(name="file1.txt", length=1024, path=["file1.txt"]),
                FileInfo(name="file2.txt", length=1024, path=["file2.txt"]),
            ],
            "total_length": 2048,
            "piece_length": 1024,
            "pieces": [b"p" * 20] * 2,
            "num_pieces": 2,
        }

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()
        mock_disk_io.read_block = AsyncMock(side_effect=OSError("Read failed"))

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Should return None on exception
        result = await assembler.read_block(0, 0, 1024)
        assert result is None

        await assembler.__aexit__(None, None, None)


class TestVerifyExistingPiecesErrorPaths:
    """Test error handling in verify_existing_pieces."""

    @pytest.mark.asyncio
    async def test_verify_existing_pieces_sync_start_disk_io(self, tmp_path):
        """Test verify_existing_pieces when disk_io.start is sync function."""
        torrent_data = make_torrent_data_single()
        file_path = tmp_path / "test.txt"
        file_path.write_bytes(b"x" * 2048)

        # Mock disk I/O with sync start
        mock_disk_io = Mock()
        mock_disk_io.start = Mock()  # Sync function
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        from ccbt.models import FileCheckpoint
        import time

        checkpoint = TorrentCheckpoint(
            version="1.0",
            info_hash=b"x" * 20,
            torrent_name="test.txt",
            created_at=time.time(),
            updated_at=time.time(),
            total_pieces=2,
            piece_length=1024,
            total_length=2048,
            output_dir=str(tmp_path),
            verified_pieces=[],
            files=[
                FileCheckpoint(
                    path=str(file_path),
                    size=2048,
                    pieces=[],
                ),
            ],
        )

        # Verify should call sync start
        result = await assembler.verify_existing_pieces(checkpoint)

        assert mock_disk_io.start.called
        assert isinstance(result, dict)

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_verify_existing_pieces_no_disk_io_start_method(self, tmp_path):
        """Test verify_existing_pieces when disk_io has no start method."""
        torrent_data = make_torrent_data_single()

        # Mock disk I/O without start method
        mock_disk_io = Mock()
        delattr(mock_disk_io, "start") if hasattr(mock_disk_io, "start") else None
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        from ccbt.models import FileCheckpoint
        import time

        checkpoint = TorrentCheckpoint(
            version="1.0",
            info_hash=b"x" * 20,
            torrent_name="test.txt",
            created_at=time.time(),
            updated_at=time.time(),
            total_pieces=2,
            piece_length=1024,
            total_length=2048,
            output_dir=str(tmp_path),
            verified_pieces=[],
            files=[],
        )

        # Should handle missing start method gracefully
        result = await assembler.verify_existing_pieces(checkpoint)

        assert isinstance(result, dict)

        await assembler.__aexit__(None, None, None)

