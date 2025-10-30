"""Tests for CLI progress module."""

from unittest.mock import MagicMock

import pytest
from rich.console import Console

pytestmark = [pytest.mark.unit, pytest.mark.cli]

from ccbt.cli.progress import ProgressManager
from ccbt.models import TorrentInfo


class TestProgressManager:
    """Test ProgressManager class."""

    @pytest.fixture
    def console(self):
        """Create a console for testing."""
        return Console()

    @pytest.fixture
    def progress_manager(self, console):
        """Create a ProgressManager instance."""
        return ProgressManager(console)

    @pytest.fixture
    def sample_torrent(self):
        """Create a sample torrent for testing."""
        return TorrentInfo(
            name="test_torrent",
            info_hash=b"test_hash_1234567890",
            announce="http://tracker.example.com/announce",
            piece_length=16384,
            pieces=[b"piece_hash_1", b"piece_hash_2"],
            num_pieces=2,
            files=[],
            total_length=1024,
            created_by="test",
            creation_date=1234567890,
            comment="test comment",
        )

    def test_init(self, console):
        """Test ProgressManager initialization."""
        pm = ProgressManager(console)
        assert pm.console is console
        assert pm.active_progress == {}
        assert pm.progress_tasks == {}

    def test_create_progress(self, progress_manager):
        """Test create_progress method."""
        progress = progress_manager.create_progress()
        assert progress is not None
        # Check that it has the expected columns
        assert len(progress.columns) == 6  # SpinnerColumn, TextColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

    def test_create_download_progress(self, progress_manager, sample_torrent):
        """Test create_download_progress method."""
        progress = progress_manager.create_download_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 8  # Includes downloaded and speed fields

    def test_create_download_progress_with_mapping(self, progress_manager):
        """Test create_download_progress with Mapping."""
        torrent_dict = {"name": "test", "info_hash": b"hash"}
        progress = progress_manager.create_download_progress(torrent_dict)
        assert progress is not None

    def test_create_upload_progress(self, progress_manager, sample_torrent):
        """Test create_upload_progress method."""
        progress = progress_manager.create_upload_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 7  # Includes uploaded and speed fields

    def test_create_upload_progress_with_mapping(self, progress_manager):
        """Test create_upload_progress with Mapping."""
        torrent_dict = {"name": "test", "info_hash": b"hash"}
        progress = progress_manager.create_upload_progress(torrent_dict)
        assert progress is not None

    def test_create_piece_progress(self, progress_manager, sample_torrent):
        """Test create_piece_progress method."""
        progress = progress_manager.create_piece_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes pieces field

    def test_create_speed_progress(self, progress_manager, sample_torrent):
        """Test create_speed_progress method."""
        progress = progress_manager.create_speed_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 7  # Includes download_speed and upload_speed fields

    def test_create_peer_progress(self, progress_manager, sample_torrent):
        """Test create_peer_progress method."""
        progress = progress_manager.create_peer_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes peers field

    def test_create_verification_progress(self, progress_manager, sample_torrent):
        """Test create_verification_progress method."""
        progress = progress_manager.create_verification_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes verified field

    def test_create_metadata_progress(self, progress_manager, sample_torrent):
        """Test create_metadata_progress method."""
        progress = progress_manager.create_metadata_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes metadata field

    def test_create_tracker_progress(self, progress_manager, sample_torrent):
        """Test create_tracker_progress method."""
        progress = progress_manager.create_tracker_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes trackers field

    def test_create_dht_progress(self, progress_manager, sample_torrent):
        """Test create_dht_progress method."""
        progress = progress_manager.create_dht_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes dht_nodes field

    def test_create_pex_progress(self, progress_manager, sample_torrent):
        """Test create_pex_progress method."""
        progress = progress_manager.create_pex_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes pex_peers field

    def test_create_webseed_progress(self, progress_manager, sample_torrent):
        """Test create_webseed_progress method."""
        progress = progress_manager.create_webseed_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes webseeds field

    def test_create_encryption_progress(self, progress_manager, sample_torrent):
        """Test create_encryption_progress method."""
        progress = progress_manager.create_encryption_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes encrypted field

    def test_create_security_progress(self, progress_manager, sample_torrent):
        """Test create_security_progress method."""
        progress = progress_manager.create_security_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes security_checks field

    def test_create_ml_progress(self, progress_manager, sample_torrent):
        """Test create_ml_progress method."""
        progress = progress_manager.create_ml_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes ml_predictions field

    def test_create_monitoring_progress(self, progress_manager, sample_torrent):
        """Test create_monitoring_progress method."""
        progress = progress_manager.create_monitoring_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes metrics field

    def test_create_observability_progress(self, progress_manager, sample_torrent):
        """Test create_observability_progress method."""
        progress = progress_manager.create_observability_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes traces field

    def test_create_dashboard_progress(self, progress_manager, sample_torrent):
        """Test create_dashboard_progress method."""
        progress = progress_manager.create_dashboard_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes dashboards field

    def test_create_alert_progress(self, progress_manager, sample_torrent):
        """Test create_alert_progress method."""
        progress = progress_manager.create_alert_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes alerts field

    def test_create_tracing_progress(self, progress_manager, sample_torrent):
        """Test create_tracing_progress method."""
        progress = progress_manager.create_tracing_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes spans field

    def test_create_profiling_progress(self, progress_manager, sample_torrent):
        """Test create_profiling_progress method."""
        progress = progress_manager.create_profiling_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes profiles field

    def test_create_debug_progress(self, progress_manager, sample_torrent):
        """Test create_debug_progress method."""
        progress = progress_manager.create_debug_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes debug_info field

    def test_create_completion_progress(self, progress_manager, sample_torrent):
        """Test create_completion_progress method."""
        progress = progress_manager.create_completion_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes completion field

    def test_create_cleanup_progress(self, progress_manager, sample_torrent):
        """Test create_cleanup_progress method."""
        progress = progress_manager.create_cleanup_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes cleanup field

    def test_create_finalization_progress(self, progress_manager, sample_torrent):
        """Test create_finalization_progress method."""
        progress = progress_manager.create_finalization_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes finalization field

    def test_create_verification_final_progress(self, progress_manager, sample_torrent):
        """Test create_verification_final_progress method."""
        progress = progress_manager.create_verification_final_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes final_verification field

    def test_create_success_progress(self, progress_manager, sample_torrent):
        """Test create_success_progress method."""
        progress = progress_manager.create_success_progress(sample_torrent)
        assert progress is not None
        assert len(progress.columns) == 6  # Includes success field

    def test_progress_manager_state(self, progress_manager, sample_torrent):
        """Test that progress manager maintains state correctly."""
        # Initially empty
        assert len(progress_manager.active_progress) == 0
        assert len(progress_manager.progress_tasks) == 0
        
        # Create some progress bars
        progress1 = progress_manager.create_progress()
        progress2 = progress_manager.create_download_progress(sample_torrent)
        
        # State should still be empty as we're not tracking them
        assert len(progress_manager.active_progress) == 0
        assert len(progress_manager.progress_tasks) == 0

    def test_all_progress_types_created(self, progress_manager, sample_torrent):
        """Test that all progress types can be created without errors."""
        progress_methods = [
            'create_progress',
            'create_download_progress',
            'create_upload_progress',
            'create_piece_progress',
            'create_speed_progress',
            'create_peer_progress',
            'create_verification_progress',
            'create_metadata_progress',
            'create_tracker_progress',
            'create_dht_progress',
            'create_pex_progress',
            'create_webseed_progress',
            'create_encryption_progress',
            'create_security_progress',
            'create_ml_progress',
            'create_monitoring_progress',
            'create_observability_progress',
            'create_dashboard_progress',
            'create_alert_progress',
            'create_tracing_progress',
            'create_profiling_progress',
            'create_debug_progress',
            'create_completion_progress',
            'create_cleanup_progress',
            'create_finalization_progress',
            'create_verification_final_progress',
            'create_success_progress',
        ]
        
        for method_name in progress_methods:
            method = getattr(progress_manager, method_name)
            if method_name == 'create_progress':
                progress = method()
            else:
                progress = method(sample_torrent)
            
            assert progress is not None
            assert hasattr(progress, 'columns')
            assert len(progress.columns) > 0
