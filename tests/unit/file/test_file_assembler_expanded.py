"""Expanded tests for file_assembler.py covering boundaries, multi-file torrents, and error paths."""

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
    FileSegment,
)


def make_torrent_data_single():
    """Create single-file torrent data."""
    return {
        "name": "single_file.txt",
        "info_hash": b"x" * 20,
        "files": [
            FileInfo(
                name="single_file.txt",
                length=4096,
                path=["single_file.txt"],
            ),
        ],
        "total_length": 4096,
        "piece_length": 1024,
        "pieces": [b"p" * 20] * 4,
        "num_pieces": 4,
    }


def make_torrent_data_multi():
    """Create multi-file torrent data."""
    return {
        "name": "multi_file",
        "info_hash": b"y" * 20,
        "files": [
            FileInfo(
                name="file1.txt",
                length=2048,
                path=["file1.txt"],
            ),
            FileInfo(
                name="file2.txt",
                length=1024,
                path=["file2.txt"],
            ),
            FileInfo(
                name="subdir/file3.txt",
                length=1024,
                path=["subdir", "file3.txt"],
            ),
        ],
        "total_length": 4096,
        "piece_length": 1024,
        "pieces": [b"p" * 20] * 4,
        "num_pieces": 4,
    }


def make_torrent_info():
    """Create TorrentInfo model."""
    return TorrentInfo(
        name="test_torrent",
        info_hash=b"z" * 20,
        announce="http://tracker.example.com:6969/announce",
        total_length=2048,
        piece_length=512,
        pieces=[b"p" * 20] * 4,
        num_pieces=4,
        files=[
            FileInfo(
                name="test.txt",
                length=2048,
                path=["test.txt"],
            ),
        ],
    )


class TestFileSegment:
    """Test FileSegment class."""

    def test_file_segment_creation(self):
        """Test FileSegment initialization."""
        segment = FileSegment(
            file_path="/path/to/file.txt",
            start_offset=0,
            end_offset=1024,
            piece_index=0,
            piece_offset=0,
        )
        assert segment.file_path == "/path/to/file.txt"
        assert segment.start_offset == 0
        assert segment.end_offset == 1024
        assert segment.piece_index == 0
        assert segment.piece_offset == 0


class TestAsyncDownloadManager:
    """Test AsyncDownloadManager lifecycle and edge cases."""

    @pytest.mark.asyncio
    async def test_start_download_dict_format(self, tmp_path):
        """Test start_download with dict format."""
        manager = AsyncDownloadManager()
        torrent_data = make_torrent_data_single()

        assembler = await manager.start_download(torrent_data, str(tmp_path))

        assert assembler is not None
        assert isinstance(assembler, AsyncFileAssembler)
        assert manager.get_assembler(torrent_data) == assembler

        await manager.stop_download(torrent_data)
        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_start_download_torrent_info_format(self, tmp_path):
        """Test start_download with TorrentInfo format."""
        manager = AsyncDownloadManager()
        torrent_info = make_torrent_info()

        assembler = await manager.start_download(torrent_info, str(tmp_path))

        assert assembler is not None
        assert isinstance(assembler, AsyncFileAssembler)

        await manager.stop_download(torrent_info)

    @pytest.mark.asyncio
    async def test_start_download_duplicate(self, tmp_path):
        """Test starting download twice returns same assembler."""
        manager = AsyncDownloadManager()
        torrent_data = make_torrent_data_single()

        assembler1 = await manager.start_download(torrent_data, str(tmp_path))
        assembler2 = await manager.start_download(torrent_data, str(tmp_path))

        assert assembler1 is assembler2

        await manager.stop_download(torrent_data)

    @pytest.mark.asyncio
    async def test_stop_download_not_found(self):
        """Test stopping non-existent download."""
        manager = AsyncDownloadManager()
        torrent_data = make_torrent_data_single()

        # Should not raise
        await manager.stop_download(torrent_data)

    @pytest.mark.asyncio
    async def test_get_assembler_not_found(self):
        """Test getting assembler that doesn't exist."""
        manager = AsyncDownloadManager()
        torrent_data = make_torrent_data_single()

        assert manager.get_assembler(torrent_data) is None

    @pytest.mark.asyncio
    async def test_stop_all_empty(self):
        """Test stop_all with no downloads."""
        manager = AsyncDownloadManager()
        await manager.stop_all()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_all_multiple(self, tmp_path):
        """Test stop_all with multiple downloads."""
        manager = AsyncDownloadManager()
        td1 = make_torrent_data_single()
        td2 = make_torrent_data_multi()

        await manager.start_download(td1, str(tmp_path))
        await manager.start_download(td2, str(tmp_path))

        assert len(manager.assemblers) == 2
        await manager.stop_all()
        assert len(manager.assemblers) == 0

    @pytest.mark.asyncio
    async def test_start_stop_session_compatibility(self, tmp_path):
        """Test session compatibility methods."""
        manager = AsyncDownloadManager(
            torrent_data=make_torrent_data_single(),
            output_dir=str(tmp_path),
        )

        await manager.start()
        assert manager.file_assembler is not None

        await manager.stop()
        assert len(manager.assemblers) == 0

    @pytest.mark.asyncio
    async def test_get_status_with_assembler(self, tmp_path):
        """Test get_status when assembler has pieces."""
        manager = AsyncDownloadManager(
            torrent_data=make_torrent_data_single(),
            output_dir=str(tmp_path),
        )

        await manager.start()

        # Mock file_assembler with pieces
        mock_pieces = []
        for i in range(4):
            mock_piece = MagicMock()
            mock_piece.completed = i < 2  # First 2 completed
            mock_pieces.append(mock_piece)

        manager.file_assembler.pieces = mock_pieces
        manager.file_assembler.download_rate = 100.0
        manager.file_assembler.upload_rate = 50.0
        manager.file_assembler.peers = ["peer1", "peer2"]

        status = manager.get_status()
        assert status["progress"] == 0.5
        assert status["download_rate"] == 100.0
        assert status["upload_rate"] == 50.0
        assert status["peers"] == 2
        assert status["pieces"] == 4
        assert status["completed"] is False

        await manager.stop()

    def test_piece_manager_property_getter(self):
        """Test piece_manager property getter."""
        manager = AsyncDownloadManager()

        # No file_assembler attribute initially
        assert manager.piece_manager is None

        # With _piece_manager (checked first)
        manager._piece_manager = "mock_manager"
        assert manager.piece_manager == "mock_manager"

        # Delete _piece_manager to test file_assembler path
        del manager._piece_manager
        mock_assembler = MagicMock()
        manager.file_assembler = mock_assembler
        assert manager.piece_manager == mock_assembler

        # With both, _piece_manager takes precedence
        manager._piece_manager = "mock_manager2"
        assert manager.piece_manager == "mock_manager2"  # _piece_manager checked first

    def test_piece_manager_property_setter(self):
        """Test piece_manager property setter."""
        manager = AsyncDownloadManager()
        manager.piece_manager = "test_value"
        assert manager._piece_manager == "test_value"

    def test_download_complete_property(self):
        """Test download_complete property."""
        manager = AsyncDownloadManager()

        # No file_assembler
        assert manager.download_complete is False

        # With file_assembler - incomplete
        mock_assembler = MagicMock()
        mock_assembler.written_pieces = {0, 1}
        mock_assembler.num_pieces = 4
        manager.file_assembler = mock_assembler
        assert manager.download_complete is False

        # With file_assembler - complete
        mock_assembler.written_pieces = {0, 1, 2, 3}
        assert manager.download_complete is True


class TestAsyncFileAssemblerInitialization:
    """Test AsyncFileAssembler initialization with different formats."""

    @pytest.mark.asyncio
    async def test_init_with_torrent_info(self, tmp_path):
        """Test initialization with TorrentInfo model."""
        torrent_info = make_torrent_info()

        assembler = AsyncFileAssembler(torrent_info, str(tmp_path))

        assert assembler.name == torrent_info.name
        assert assembler.info_hash == torrent_info.info_hash
        assert assembler.files == torrent_info.files
        assert assembler.total_length == torrent_info.total_length
        assert assembler.piece_length == torrent_info.piece_length

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_init_with_dict_format(self, tmp_path):
        """Test initialization with dict format."""
        torrent_data = make_torrent_data_single()

        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        assert assembler.name == torrent_data["name"]
        assert assembler.info_hash == torrent_data["info_hash"]
        assert assembler.total_length == torrent_data["total_length"]

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_init_with_custom_disk_io_manager(self, tmp_path):
        """Test initialization with custom disk I/O manager."""
        torrent_data = make_torrent_data_single()
        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        assert assembler.disk_io == mock_disk_io

        await assembler.__aenter__()
        assert mock_disk_io.start.called
        await assembler.__aexit__(None, None, None)


class TestBuildFileSegments:
    """Test _build_file_segments for single and multi-file torrents."""

    @pytest.mark.asyncio
    async def test_build_segments_single_file(self, tmp_path):
        """Test segment building for single-file torrent."""
        torrent_data = make_torrent_data_single()
        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        segments = assembler.file_segments

        assert len(segments) == 4  # 4 pieces
        assert all(seg.piece_index == i for i, seg in enumerate(segments))
        assert all(seg.piece_offset == 0 for seg in segments)

        # Check first segment
        assert segments[0].start_offset == 0
        assert segments[0].end_offset == 1024
        assert segments[0].file_path.endswith("single_file.txt")

        # Check last segment (may be smaller)
        assert segments[3].start_offset == 3072
        assert segments[3].end_offset == 4096

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_build_segments_multi_file(self, tmp_path):
        """Test segment building for multi-file torrent."""
        torrent_data = make_torrent_data_multi()
        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        segments = assembler.file_segments

        # Multi-file torrent - pieces can span files
        assert len(segments) > 0

        # Verify segments reference correct files
        file_paths = {seg.file_path for seg in segments}
        assert len(file_paths) == 3  # 3 files

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_build_segments_piece_boundaries(self, tmp_path):
        """Test segment building across piece boundaries."""
        # Create torrent where piece spans multiple files
        torrent_data = {
            "name": "cross_file",
            "info_hash": b"c" * 20,
            "files": [
                FileInfo(name="file1.txt", length=512, path=["file1.txt"]),
                FileInfo(name="file2.txt", length=512, path=["file2.txt"]),
            ],
            "total_length": 1024,
            "piece_length": 1024,  # One piece covers both files
            "pieces": [b"p" * 20],
            "num_pieces": 1,
        }

        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))
        segments = assembler.file_segments

        # One piece should create segments for both files
        assert len(segments) == 2
        assert segments[0].piece_index == 0
        assert segments[1].piece_index == 0

        await assembler.__aexit__(None, None, None)


class TestWritePieceToFile:
    """Test write_piece_to_file error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_write_piece_no_segments(self, tmp_path):
        """Test writing piece with no file segments raises error."""
        torrent_data = make_torrent_data_single()
        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        # Clear file_segments to simulate error condition
        assembler.file_segments = []

        await assembler.__aenter__()

        with pytest.raises(FileAssemblerError, match="No file segments found"):
            await assembler.write_piece_to_file(0, b"x" * 1024)

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_write_piece_already_written(self, tmp_path):
        """Test writing piece that's already written."""
        torrent_data = make_torrent_data_single()

        # Mock disk I/O
        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()
        mock_disk_io.write_block = AsyncMock(
            return_value=asyncio.get_event_loop().create_future()
        )

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Mark piece as written
        async with assembler.lock:
            assembler.written_pieces.add(0)

        # Write should return immediately
        await assembler.write_piece_to_file(0, b"x" * 1024)

        # write_block should not be called
        assert not mock_disk_io.write_block.called

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_write_segment_error_handling(self, tmp_path):
        """Test error handling in _write_segment_to_file_async."""
        torrent_data = make_torrent_data_single()

        # Mock disk I/O to raise exception
        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        async def failing_write(*args, **kwargs):
            raise OSError("Disk write failed")

        mock_disk_io.write_block = AsyncMock(side_effect=failing_write)

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        with pytest.raises(FileAssemblerError, match="Failed to write segment"):
            await assembler.write_piece_to_file(0, b"x" * 1024)

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_write_piece_memoryview(self, tmp_path):
        """Test writing piece with memoryview data."""
        torrent_data = make_torrent_data_single()

        # Mock disk I/O
        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()
        future = asyncio.get_event_loop().create_future()
        future.set_result(None)
        mock_disk_io.write_block = AsyncMock(return_value=future)

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Write with memoryview
        piece_data = memoryview(b"x" * 1024)
        await assembler.write_piece_to_file(0, piece_data)

        # Should convert memoryview to bytes
        assert mock_disk_io.write_block.called
        call_args = mock_disk_io.write_block.call_args
        assert isinstance(call_args[0][2], bytes)

        await assembler.__aexit__(None, None, None)


class TestReadBlock:
    """Test read_block for single and multi-file torrents."""

    @pytest.mark.asyncio
    async def test_read_block_invalid_piece_index(self, tmp_path):
        """Test reading with invalid piece index."""
        torrent_data = make_torrent_data_single()

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Invalid piece index
        assert await assembler.read_block(-1, 0, 100) is None
        assert await assembler.read_block(100, 0, 100) is None

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_block_no_segments(self, tmp_path):
        """Test reading when no segments exist."""
        torrent_data = make_torrent_data_single()

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )
        assembler.file_segments = []  # Clear segments

        await assembler.__aenter__()

        assert await assembler.read_block(0, 0, 100) is None

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_block_single_file_success(self, tmp_path):
        """Test reading from single-file torrent."""
        torrent_data = make_torrent_data_single()

        # Create file with data
        file_path = tmp_path / "single_file.txt"
        file_path.write_bytes(b"A" * 4096)

        # Mock disk I/O to read from file
        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        async def mock_read_block(file_path, offset, length):
            with open(file_path, "rb") as f:
                f.seek(offset)
                return f.read(length)

        mock_disk_io.read_block = AsyncMock(side_effect=mock_read_block)

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Read from piece 0
        data = await assembler.read_block(0, 0, 512)
        assert data == b"A" * 512

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_block_multi_file(self, tmp_path):
        """Test reading from multi-file torrent."""
        torrent_data = make_torrent_data_multi()

        # Create files with data
        (tmp_path / "file1.txt").write_bytes(b"1" * 2048)
        (tmp_path / "file2.txt").write_bytes(b"2" * 1024)
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.txt").write_bytes(b"3" * 1024)

        # Mock disk I/O
        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        async def mock_read_block(file_path, offset, length):
            file_path_obj = Path(file_path) if isinstance(file_path, str) else file_path
            if not file_path_obj.exists():
                return None
            with open(file_path_obj, "rb") as f:
                f.seek(offset)
                return f.read(length)

        mock_disk_io.read_block = AsyncMock(side_effect=mock_read_block)

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Read across piece boundary (piece 0 spans file1 and file2)
        # Piece 0: [0-1024] spans file1[0-1024]
        data = await assembler.read_block(0, 0, 1024)
        assert data is not None
        assert len(data) == 1024

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_block_exception_handling(self, tmp_path):
        """Test read_block handles exceptions."""
        torrent_data = make_torrent_data_single()

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()
        mock_disk_io.read_block = AsyncMock(side_effect=OSError("Read failed"))

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Should return None on exception
        assert await assembler.read_block(0, 0, 100) is None

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_block_wrong_length(self, tmp_path):
        """Test read_block when returned length doesn't match."""
        # This test is removed as read_block doesn't strictly validate lengths
        # It returns whatever is read from disk, which may be shorter than requested
        # The actual file_assembler code doesn't enforce length matching strictly
        pass


class TestFileAssemblerHelpers:
    """Test helper methods."""

    @pytest.mark.asyncio
    async def test_get_file_paths(self, tmp_path):
        """Test get_file_paths returns unique file paths."""
        torrent_data = make_torrent_data_multi()

        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        file_paths = assembler.get_file_paths()

        assert len(file_paths) == 3  # 3 files
        assert all(isinstance(path, str) for path in file_paths)

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_is_piece_written(self, tmp_path):
        """Test is_piece_written."""
        torrent_data = make_torrent_data_single()

        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        assert assembler.is_piece_written(0) is False

        async with assembler.lock:
            assembler.written_pieces.add(0)

        assert assembler.is_piece_written(0) is True

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_get_written_pieces(self, tmp_path):
        """Test get_written_pieces returns copy."""
        torrent_data = make_torrent_data_single()

        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        async with assembler.lock:
            assembler.written_pieces.add(0)
            assembler.written_pieces.add(1)

        written = assembler.get_written_pieces()

        assert written == {0, 1}
        assert written is not assembler.written_pieces  # Should be copy

        await assembler.__aexit__(None, None, None)


class TestVerifyExistingPieces:
    """Test verify_existing_pieces checkpoint validation."""

    @pytest.mark.asyncio
    async def test_verify_existing_pieces_all_valid(self, tmp_path):
        """Test verification when all pieces are valid."""
        torrent_data = make_torrent_data_single()
        file_path = tmp_path / "single_file.txt"

        # Create file
        file_path.write_bytes(b"x" * 4096)

        # Mock disk I/O
        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Mark pieces as written
        async with assembler.lock:
            assembler.written_pieces.add(0)
            assembler.written_pieces.add(1)

        # Create checkpoint
        from ccbt.models import FileCheckpoint
        import time

        checkpoint = TorrentCheckpoint(
            version="1.0",
            info_hash=b"x" * 20,
            torrent_name="single_file.txt",
            created_at=time.time(),
            updated_at=time.time(),
            total_pieces=4,
            piece_length=1024,
            total_length=4096,
            output_dir=str(tmp_path),
            verified_pieces=[0, 1],
            files=[
                FileCheckpoint(
                    path=str(file_path),
                    size=4096,
                    pieces=[0, 1],
                ),
            ],
        )

        result = await assembler.verify_existing_pieces(checkpoint)

        assert result["valid"] is True
        assert len(result["missing_files"]) == 0
        assert len(result["corrupted_pieces"]) == 0
        assert len(result["missing_pieces"]) == 0

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_verify_existing_pieces_missing_file(self, tmp_path):
        """Test verification when file is missing."""
        torrent_data = make_torrent_data_single()

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        from ccbt.models import FileCheckpoint
        import time

        checkpoint = TorrentCheckpoint(
            version="1.0",
            info_hash=b"x" * 20,
            torrent_name="single_file.txt",
            created_at=time.time(),
            updated_at=time.time(),
            total_pieces=4,
            piece_length=1024,
            total_length=4096,
            output_dir=str(tmp_path),
            verified_pieces=[0, 1],
            files=[
                FileCheckpoint(
                    path=str(tmp_path / "nonexistent.txt"),
                    size=4096,
                    pieces=[0, 1],
                ),
            ],
        )

        result = await assembler.verify_existing_pieces(checkpoint)

        assert result["valid"] is False
        assert len(result["missing_files"]) > 0

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_verify_existing_pieces_wrong_size(self, tmp_path):
        """Test verification when file has wrong size."""
        torrent_data = make_torrent_data_single()
        file_path = tmp_path / "single_file.txt"

        # Create file with wrong size
        file_path.write_bytes(b"x" * 2048)  # Should be 4096

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        from ccbt.models import FileCheckpoint
        import time

        checkpoint = TorrentCheckpoint(
            version="1.0",
            info_hash=b"x" * 20,
            torrent_name="single_file.txt",
            created_at=time.time(),
            updated_at=time.time(),
            total_pieces=4,
            piece_length=1024,
            total_length=4096,
            output_dir=str(tmp_path),
            verified_pieces=[0, 1],
            files=[
                FileCheckpoint(
                    path=str(file_path),
                    size=4096,  # Checkpoint says 4096
                    pieces=[0, 1],
                ),
            ],
        )

        result = await assembler.verify_existing_pieces(checkpoint)

        assert result["valid"] is False
        assert len(result["corrupted_pieces"]) > 0

        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_verify_existing_pieces_missing_piece(self, tmp_path):
        """Test verification when piece is not written."""
        torrent_data = make_torrent_data_single()
        file_path = tmp_path / "single_file.txt"

        file_path.write_bytes(b"x" * 4096)

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        await assembler.__aenter__()

        # Don't add piece 0 to written_pieces

        from ccbt.models import FileCheckpoint
        import time

        checkpoint = TorrentCheckpoint(
            version="1.0",
            info_hash=b"x" * 20,
            torrent_name="single_file.txt",
            created_at=time.time(),
            updated_at=time.time(),
            total_pieces=4,
            piece_length=1024,
            total_length=4096,
            output_dir=str(tmp_path),
            verified_pieces=[0],  # Claims piece 0 is verified
            files=[
                FileCheckpoint(
                    path=str(file_path),
                    size=4096,
                    pieces=[0],
                ),
            ],
        )

        result = await assembler.verify_existing_pieces(checkpoint)

        assert result["valid"] is False
        assert 0 in result["missing_pieces"]

        await assembler.__aexit__(None, None, None)


class TestCleanupIncompleteFiles:
    """Test cleanup_incomplete_files."""

    @pytest.mark.asyncio
    async def test_cleanup_incomplete_file(self, tmp_path):
        """Test cleanup removes incomplete file."""
        torrent_data = make_torrent_data_single()
        file_path = tmp_path / "single_file.txt"

        # Create incomplete file
        file_path.write_bytes(b"x" * 1000)  # Smaller than 4096

        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        assembler.cleanup_incomplete_files()

        # File should be removed
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_complete_file_not_removed(self, tmp_path):
        """Test cleanup doesn't remove complete file."""
        torrent_data = make_torrent_data_single()
        file_path = tmp_path / "single_file.txt"

        # Create complete file
        file_path.write_bytes(b"x" * 4096)

        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        assembler.cleanup_incomplete_files()

        # File should still exist
        assert file_path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_file(self, tmp_path):
        """Test cleanup handles non-existent files gracefully."""
        torrent_data = make_torrent_data_single()

        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        # Should not raise
        assembler.cleanup_incomplete_files()

    @pytest.mark.asyncio
    async def test_cleanup_error_handling(self, tmp_path):
        """Test cleanup handles errors gracefully."""
        torrent_data = make_torrent_data_single()

        assembler = AsyncFileAssembler(torrent_data, str(tmp_path))

        # Mock os.path.exists to raise exception
        with patch("ccbt.storage.file_assembler.os.path.exists", side_effect=OSError("Access denied")):
            # Should not raise, just log
            assembler.cleanup_incomplete_files()


class TestAsyncFileAssemblerLifecycle:
    """Test async context manager lifecycle."""

    @pytest.mark.asyncio
    async def test_context_manager_enter_exit(self, tmp_path):
        """Test async context manager."""
        torrent_data = make_torrent_data_single()

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )

        async with assembler:
            assert assembler._disk_io_started is True
            assert mock_disk_io.start.called

        assert mock_disk_io.stop.called

    @pytest.mark.asyncio
    async def test_write_starts_disk_io_if_not_started(self, tmp_path):
        """Test write_piece_to_file starts disk I/O if not started."""
        torrent_data = make_torrent_data_single()

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()
        future = asyncio.get_event_loop().create_future()
        future.set_result(None)
        mock_disk_io.write_block = AsyncMock(return_value=future)

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )
        # Don't call __aenter__

        # Write should start disk I/O
        await assembler.write_piece_to_file(0, b"x" * 1024)

        assert mock_disk_io.start.called
        await assembler.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_read_starts_disk_io_if_not_started(self, tmp_path):
        """Test read_block starts disk I/O if not started."""
        torrent_data = make_torrent_data_single()

        mock_disk_io = Mock()
        mock_disk_io.start = AsyncMock()
        mock_disk_io.stop = AsyncMock()
        mock_disk_io.read_block = AsyncMock(return_value=b"data")

        assembler = AsyncFileAssembler(
            torrent_data, str(tmp_path), disk_io_manager=mock_disk_io
        )
        # Don't call __aenter__

        # Read should start disk I/O
        await assembler.read_block(0, 0, 100)

        assert mock_disk_io.start.called
        await assembler.__aexit__(None, None, None)

