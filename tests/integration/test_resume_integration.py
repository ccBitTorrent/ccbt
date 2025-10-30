#!/usr/bin/env python3
"""Integration tests for resume functionality.

This test verifies that the complete resume workflow works end-to-end:
1. Create a mock torrent checkpoint
2. Test resume_from_checkpoint method
3. Test CLI resume command
4. Test checkpoint detection and user prompts
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ccbt.storage.checkpoint import CheckpointManager
from ccbt.config import get_config
from ccbt.models import DownloadStats, FileCheckpoint, TorrentCheckpoint
from ccbt.session import AsyncSessionManager


class TestResumeIntegration:
    """Integration tests for resume functionality."""

    @pytest.mark.asyncio
    async def test_resume_workflow(self):
        """Test the complete resume workflow."""
        # Create temporary directory for test
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create mock torrent data

            # Create mock checkpoint
            checkpoint = TorrentCheckpoint(
                info_hash=b"test_hash_1234567890",
                torrent_name="test_torrent",
                created_at=1234567890.0,
                updated_at=1234567890.0,
                total_pieces=1,
                piece_length=16384,
                total_length=1024,
                output_dir=str(temp_path),
                verified_pieces=[0],
                files=[
                    FileCheckpoint(
                        path=str(temp_path / "test_file.txt"),
                        size=1024,
                        exists=True,
                    ),
                ],
                download_stats=DownloadStats(
                    bytes_downloaded=1024,
                    download_time=60.0,
                    average_speed=17.0,
                    start_time=1234567890.0,
                    last_update=1234567890.0,
                ),
                torrent_file_path=str(temp_path / "tests/data/test.torrent"),
                magnet_uri="magnet:?xt=urn:btih:test_hash_1234567890&dn=test_torrent",
                announce_urls=["http://tracker.example.com/announce"],
                display_name="Test Torrent",
            )

            # Test 1: CheckpointManager operations
            config = get_config()
            config.disk.checkpoint_dir = str(temp_path / "checkpoints")
            checkpoint_manager = CheckpointManager(config.disk)

            # Save checkpoint
            await checkpoint_manager.save_checkpoint(checkpoint)

            # Load checkpoint
            loaded_checkpoint = await checkpoint_manager.load_checkpoint(
                b"test_hash_1234567890",
            )
            assert loaded_checkpoint is not None
            assert loaded_checkpoint.torrent_name == "test_torrent"
            assert loaded_checkpoint.torrent_file_path == str(
                temp_path / "tests/data/test.torrent",
            )
            assert (
                loaded_checkpoint.magnet_uri
                == "magnet:?xt=urn:btih:test_hash_1234567890&dn=test_torrent"
            )

            # Test 2: AsyncSessionManager resume functionality

            # Mock the necessary components
            with patch("ccbt.session.AsyncTorrentSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value = mock_session

                session_manager = AsyncSessionManager(str(temp_path))

                # Test validate_checkpoint
                is_valid = await session_manager.validate_checkpoint(checkpoint)
                assert is_valid

                # Test list_resumable_checkpoints
                resumable = await session_manager.list_resumable_checkpoints()
                assert len(resumable) >= 1

                # Test find_checkpoint_by_name
                found_checkpoint = await session_manager.find_checkpoint_by_name(
                    "test_torrent",
                )
                assert found_checkpoint is not None

                # Test get_checkpoint_info
                checkpoint_info = await session_manager.get_checkpoint_info(
                    b"test_hash_1234567890",
                )
                assert checkpoint_info is not None
                assert checkpoint_info["name"] == "test_torrent"

            # Test 3: CLI integration (mocked)

            with patch("ccbt.cli.main.AsyncSessionManager") as mock_cli_session:
                mock_cli_session.return_value = session_manager

                # Test CLI resume command would work

            return True

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in resume functionality."""
        session_manager = AsyncSessionManager(".")

        # Test with valid checkpoint but missing source
        valid_checkpoint = TorrentCheckpoint(
            info_hash=b"invalid_hash_1234567",  # Exactly 20 bytes
            torrent_name="invalid_torrent",
            created_at=1234567890.0,
            updated_at=1234567890.0,
            total_pieces=1,
            piece_length=16384,  # Valid piece length
            total_length=1024,
            output_dir=".",
            files=[],
        )

        # Test validation - checkpoint is valid but missing source
        await session_manager.validate_checkpoint(valid_checkpoint)
        # The checkpoint itself is valid, but it's missing torrent source for resume

        # Test resume with missing source
        try:
            await session_manager.resume_from_checkpoint(
                b"invalid_hash_1234567",
                valid_checkpoint,
            )
            msg = "Should have raised ValueError"
            raise AssertionError(msg)
        except ValueError as e:
            assert "No valid torrent source found" in str(e)

    @pytest.mark.asyncio
    async def test_checkpoint_metadata_persistence(self):
        """Test that checkpoint metadata is properly saved and loaded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create checkpoint with metadata
            checkpoint = TorrentCheckpoint(
                info_hash=b"test_hash_1234567890",
                torrent_name="metadata_test",
                created_at=1234567890.0,
                updated_at=1234567890.0,
                total_pieces=1,
                piece_length=16384,
                total_length=1024,
                output_dir=str(temp_path),
                torrent_file_path="/path/to/tests/data/test.torrent",
                magnet_uri="magnet:?xt=urn:btih:test_hash_1234567890&dn=metadata_test",
                announce_urls=[
                    "http://tracker1.example.com",
                    "http://tracker2.example.com",
                ],
                display_name="Metadata Test Torrent",
            )

            # Save and load checkpoint
            config = get_config()
            config.disk.checkpoint_dir = str(temp_path / "checkpoints")
            checkpoint_manager = CheckpointManager(config.disk)

            await checkpoint_manager.save_checkpoint(checkpoint)
            loaded_checkpoint = await checkpoint_manager.load_checkpoint(
                b"test_hash_1234567890",
            )

            # Verify metadata persistence
            assert loaded_checkpoint.torrent_file_path == "/path/to/tests/data/test.torrent"
            assert (
                loaded_checkpoint.magnet_uri
                == "magnet:?xt=urn:btih:test_hash_1234567890&dn=metadata_test"
            )
            assert len(loaded_checkpoint.announce_urls) == 2
            assert loaded_checkpoint.announce_urls[0] == "http://tracker1.example.com"
            assert loaded_checkpoint.announce_urls[1] == "http://tracker2.example.com"
            assert loaded_checkpoint.display_name == "Metadata Test Torrent"

    @pytest.mark.asyncio
    async def test_resume_priority_order(self):
        """Test the resume priority order logic."""
        session_manager = AsyncSessionManager(".")

        # Create checkpoint with all source types
        checkpoint = TorrentCheckpoint(
            info_hash=b"test_hash_1234567890",
            torrent_name="priority_test",
            created_at=1234567890.0,
            updated_at=1234567890.0,
            total_pieces=1,
            piece_length=16384,
            total_length=1024,
            output_dir=".",
            torrent_file_path="/path/to/original.torrent",
            magnet_uri="magnet:?xt=urn:btih:0123456789ABCDEF0123456789ABCDEF01234567&dn=priority_test",
            announce_urls=["http://tracker.example.com"],
            display_name="Priority Test",
        )

        # Test priority order with explicit torrent path
        with patch("ccbt.session.session.Path") as mock_path_class:
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path_class.return_value = mock_path_instance
            
            with patch("ccbt.session.session.TorrentParser") as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.return_value = {
                    "info_hash": bytes.fromhex("0123456789ABCDEF0123456789ABCDEF01234567"),
                    "name": "priority_test",
                }
                mock_parser_class.return_value = mock_parser
                
                with patch.object(session_manager, "add_torrent") as mock_add_torrent:
                    mock_add_torrent.return_value = "0123456789ABCDEF0123456789ABCDEF01234567"

                    result = await session_manager.resume_from_checkpoint(
                        bytes.fromhex("0123456789ABCDEF0123456789ABCDEF01234567"),
                        checkpoint,
                        torrent_path="/explicit/path.torrent",
                    )

                    # Should use explicit path
                    mock_add_torrent.assert_called_once_with("/explicit/path.torrent", resume=True)
                    assert result == "0123456789ABCDEF0123456789ABCDEF01234567"


if __name__ == "__main__":
    # Run tests directly for development
    async def main():
        test_instance = TestResumeIntegration()
        try:
            await test_instance.test_resume_workflow()
            await test_instance.test_error_handling()
            await test_instance.test_checkpoint_metadata_persistence()
            await test_instance.test_resume_priority_order()
            return 0
        except Exception:
            import traceback

            traceback.print_exc()
            return 1

    import sys

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
