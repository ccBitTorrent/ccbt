"""Comprehensive unit tests for DaemonSessionAdapter methods.

Tests all newly implemented methods in DaemonSessionAdapter following
the established testing patterns.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from ccbt.daemon.ipc_protocol import (
    FileInfo,
    FileListResponse,
    NATStatusResponse,
    ProtocolInfo,
    QueueEntry,
    QueueListResponse,
    ScrapeListResponse,
    ScrapeResult,
    TorrentStatusResponse,
)
from ccbt.executor.session_adapter import DaemonSessionAdapter

pytestmark = [pytest.mark.unit, pytest.mark.executor]


class TestDaemonSessionAdapterBasicTorrentOps:
    """Test basic torrent operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_list_torrents_delegates(self, adapter, mock_ipc_client):
        """Test list_torrents delegates to IPC client."""
        expected_torrents = [
            TorrentStatusResponse(
                info_hash="a" * 40,
                name="Test Torrent",
                status="active",
                progress=0.5,
                download_rate=100.0,
                upload_rate=50.0,
                num_peers=10,
                num_seeds=5,
                total_size=1000000,
                downloaded=500000,
                uploaded=250000,
            )
        ]
        mock_ipc_client.list_torrents = AsyncMock(return_value=expected_torrents)

        result = await adapter.list_torrents()

        assert result == expected_torrents
        mock_ipc_client.list_torrents.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_torrent_status_delegates(self, adapter, mock_ipc_client):
        """Test get_torrent_status delegates to IPC client."""
        info_hash = "a" * 40
        expected_status = TorrentStatusResponse(
            info_hash=info_hash,
            name="Test Torrent",
            status="active",
            progress=0.5,
            download_rate=100.0,
            upload_rate=50.0,
            num_peers=10,
            num_seeds=5,
            total_size=1000000,
            downloaded=500000,
            uploaded=250000,
        )
        mock_ipc_client.get_torrent_status = AsyncMock(return_value=expected_status)

        result = await adapter.get_torrent_status(info_hash)

        assert result == expected_status
        mock_ipc_client.get_torrent_status.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_get_torrent_status_not_found(self, adapter, mock_ipc_client):
        """Test get_torrent_status returns None when not found."""
        info_hash = "a" * 40
        mock_ipc_client.get_torrent_status = AsyncMock(return_value=None)

        result = await adapter.get_torrent_status(info_hash)

        assert result is None
        mock_ipc_client.get_torrent_status.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_pause_torrent_delegates(self, adapter, mock_ipc_client):
        """Test pause_torrent delegates to IPC client."""
        info_hash = "a" * 40
        mock_ipc_client.pause_torrent = AsyncMock(return_value=True)

        result = await adapter.pause_torrent(info_hash)

        assert result is True
        mock_ipc_client.pause_torrent.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_resume_torrent_delegates(self, adapter, mock_ipc_client):
        """Test resume_torrent delegates to IPC client."""
        info_hash = "a" * 40
        mock_ipc_client.resume_torrent = AsyncMock(return_value=True)

        result = await adapter.resume_torrent(info_hash)

        assert result is True
        mock_ipc_client.resume_torrent.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_cancel_torrent_delegates(self, adapter, mock_ipc_client):
        """Test cancel_torrent delegates to IPC client."""
        info_hash = "a" * 40
        mock_ipc_client.cancel_torrent = AsyncMock(return_value=True)

        result = await adapter.cancel_torrent(info_hash)

        assert result is True
        mock_ipc_client.cancel_torrent.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_force_start_torrent_delegates(self, adapter, mock_ipc_client):
        """Test force_start_torrent delegates to IPC client."""
        info_hash = "a" * 40
        mock_ipc_client.force_start_torrent = AsyncMock(return_value=True)

        result = await adapter.force_start_torrent(info_hash)

        assert result is True
        mock_ipc_client.force_start_torrent.assert_called_once_with(info_hash)


class TestDaemonSessionAdapterFileOps:
    """Test file operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_get_torrent_files_delegates(self, adapter, mock_ipc_client):
        """Test get_torrent_files delegates to IPC client."""
        info_hash = "a" * 40
        expected_response = FileListResponse(
            info_hash=info_hash,
            files=[
                FileInfo(
                    index=0,
                    name="file1.txt",
                    size=1000,
                    selected=True,
                    priority="normal",
                    progress=0.5,
                )
            ],
        )
        mock_ipc_client.get_torrent_files = AsyncMock(return_value=expected_response)

        result = await adapter.get_torrent_files(info_hash)

        assert result == expected_response
        mock_ipc_client.get_torrent_files.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_select_files_delegates(self, adapter, mock_ipc_client):
        """Test select_files delegates to IPC client."""
        info_hash = "a" * 40
        file_indices = [0, 1, 2]
        expected_result = {"status": "selected", "file_indices": file_indices}
        mock_ipc_client.select_files = AsyncMock(return_value=expected_result)

        result = await adapter.select_files(info_hash, file_indices)

        assert result == expected_result
        mock_ipc_client.select_files.assert_called_once_with(info_hash, file_indices)

    @pytest.mark.asyncio
    async def test_deselect_files_delegates(self, adapter, mock_ipc_client):
        """Test deselect_files delegates to IPC client."""
        info_hash = "a" * 40
        file_indices = [0, 1]
        expected_result = {"status": "deselected", "file_indices": file_indices}
        mock_ipc_client.deselect_files = AsyncMock(return_value=expected_result)

        result = await adapter.deselect_files(info_hash, file_indices)

        assert result == expected_result
        mock_ipc_client.deselect_files.assert_called_once_with(info_hash, file_indices)

    @pytest.mark.asyncio
    async def test_set_file_priority_delegates(self, adapter, mock_ipc_client):
        """Test set_file_priority delegates to IPC client."""
        info_hash = "a" * 40
        file_index = 0
        priority = "high"
        expected_result = {
            "status": "priority_set",
            "file_index": file_index,
            "priority": priority,
        }
        mock_ipc_client.set_file_priority = AsyncMock(return_value=expected_result)

        result = await adapter.set_file_priority(info_hash, file_index, priority)

        assert result == expected_result
        mock_ipc_client.set_file_priority.assert_called_once_with(
            info_hash, file_index, priority
        )

    @pytest.mark.asyncio
    async def test_verify_files_delegates(self, adapter, mock_ipc_client):
        """Test verify_files delegates to IPC client."""
        info_hash = "a" * 40
        expected_result = {
            "status": "completed",
            "info_hash": info_hash,
            "verified_files": ["file1.txt"],
            "failed_files": [],
        }
        mock_ipc_client.verify_files = AsyncMock(return_value=expected_result)

        result = await adapter.verify_files(info_hash)

        assert result == expected_result
        mock_ipc_client.verify_files.assert_called_once_with(info_hash)


class TestDaemonSessionAdapterQueueOps:
    """Test queue operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_get_queue_delegates(self, adapter, mock_ipc_client):
        """Test get_queue delegates to IPC client."""
        expected_response = QueueListResponse(
            entries=[
                QueueEntry(
                    info_hash="a" * 40,
                    queue_position=0,
                    priority="high",
                    status="active",
                    allocated_down_kib=100,
                    allocated_up_kib=50,
                )
            ],
            statistics={"total": 1, "active": 1},
        )
        mock_ipc_client.get_queue = AsyncMock(return_value=expected_response)

        result = await adapter.get_queue()

        assert result == expected_response
        mock_ipc_client.get_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_queue_delegates(self, adapter, mock_ipc_client):
        """Test add_to_queue delegates to IPC client."""
        info_hash = "a" * 40
        priority = "high"
        expected_result = {"status": "added", "info_hash": info_hash}
        mock_ipc_client.add_to_queue = AsyncMock(return_value=expected_result)

        result = await adapter.add_to_queue(info_hash, priority)

        assert result == expected_result
        mock_ipc_client.add_to_queue.assert_called_once_with(info_hash, priority)

    @pytest.mark.asyncio
    async def test_remove_from_queue_delegates(self, adapter, mock_ipc_client):
        """Test remove_from_queue delegates to IPC client."""
        info_hash = "a" * 40
        expected_result = {"status": "removed", "info_hash": info_hash}
        mock_ipc_client.remove_from_queue = AsyncMock(return_value=expected_result)

        result = await adapter.remove_from_queue(info_hash)

        assert result == expected_result
        mock_ipc_client.remove_from_queue.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_move_in_queue_delegates(self, adapter, mock_ipc_client):
        """Test move_in_queue delegates to IPC client."""
        info_hash = "a" * 40
        new_position = 5
        expected_result = {
            "status": "moved",
            "info_hash": info_hash,
            "new_position": new_position,
        }
        mock_ipc_client.move_in_queue = AsyncMock(return_value=expected_result)

        result = await adapter.move_in_queue(info_hash, new_position)

        assert result == expected_result
        mock_ipc_client.move_in_queue.assert_called_once_with(info_hash, new_position)

    @pytest.mark.asyncio
    async def test_clear_queue_delegates(self, adapter, mock_ipc_client):
        """Test clear_queue delegates to IPC client."""
        expected_result = {"status": "cleared"}
        mock_ipc_client.clear_queue = AsyncMock(return_value=expected_result)

        result = await adapter.clear_queue()

        assert result == expected_result
        mock_ipc_client.clear_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_torrent_in_queue_delegates(self, adapter, mock_ipc_client):
        """Test pause_torrent_in_queue delegates to IPC client."""
        info_hash = "a" * 40
        expected_result = {"status": "paused", "info_hash": info_hash}
        mock_ipc_client.pause_torrent_in_queue = AsyncMock(return_value=expected_result)

        result = await adapter.pause_torrent_in_queue(info_hash)

        assert result == expected_result
        mock_ipc_client.pause_torrent_in_queue.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_resume_torrent_in_queue_delegates(self, adapter, mock_ipc_client):
        """Test resume_torrent_in_queue delegates to IPC client."""
        info_hash = "a" * 40
        expected_result = {"status": "resumed", "info_hash": info_hash}
        mock_ipc_client.resume_torrent_in_queue = AsyncMock(return_value=expected_result)

        result = await adapter.resume_torrent_in_queue(info_hash)

        assert result == expected_result
        mock_ipc_client.resume_torrent_in_queue.assert_called_once_with(info_hash)


class TestDaemonSessionAdapterNATOps:
    """Test NAT operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_get_nat_status_delegates(self, adapter, mock_ipc_client):
        """Test get_nat_status delegates to IPC client."""
        expected_response = NATStatusResponse(
            enabled=True,
            method="UPnP",
            external_ip="192.168.1.1",
            mapped_port=6881,
            mappings=[],
        )
        mock_ipc_client.get_nat_status = AsyncMock(return_value=expected_response)

        result = await adapter.get_nat_status()

        assert result == expected_response
        mock_ipc_client.get_nat_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_nat_delegates(self, adapter, mock_ipc_client):
        """Test discover_nat delegates to IPC client."""
        expected_result = {"status": "discovered", "result": {"method": "UPnP"}}
        mock_ipc_client.discover_nat = AsyncMock(return_value=expected_result)

        result = await adapter.discover_nat()

        assert result == expected_result
        mock_ipc_client.discover_nat.assert_called_once()

    @pytest.mark.asyncio
    async def test_map_nat_port_delegates(self, adapter, mock_ipc_client):
        """Test map_nat_port delegates to IPC client."""
        internal_port = 6881
        external_port = 6881
        protocol = "tcp"
        expected_result = {"status": "mapped", "result": {"port": external_port}}
        mock_ipc_client.map_nat_port = AsyncMock(return_value=expected_result)

        result = await adapter.map_nat_port(internal_port, external_port, protocol)

        assert result == expected_result
        mock_ipc_client.map_nat_port.assert_called_once_with(
            internal_port, external_port, protocol
        )

    @pytest.mark.asyncio
    async def test_unmap_nat_port_delegates(self, adapter, mock_ipc_client):
        """Test unmap_nat_port delegates to IPC client."""
        port = 6881
        protocol = "tcp"
        expected_result = {"status": "unmapped", "result": {"port": port}}
        mock_ipc_client.unmap_nat_port = AsyncMock(return_value=expected_result)

        result = await adapter.unmap_nat_port(port, protocol)

        assert result == expected_result
        mock_ipc_client.unmap_nat_port.assert_called_once_with(port, protocol)

    @pytest.mark.asyncio
    async def test_refresh_nat_mappings_delegates(self, adapter, mock_ipc_client):
        """Test refresh_nat_mappings delegates to IPC client."""
        expected_result = {"status": "refreshed", "result": {"mappings": []}}
        mock_ipc_client.refresh_nat_mappings = AsyncMock(return_value=expected_result)

        result = await adapter.refresh_nat_mappings()

        assert result == expected_result
        mock_ipc_client.refresh_nat_mappings.assert_called_once()


class TestDaemonSessionAdapterScrapeOps:
    """Test scrape operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_scrape_torrent_delegates(self, adapter, mock_ipc_client):
        """Test scrape_torrent delegates to IPC client."""
        info_hash = "a" * 40
        force = False
        expected_result = ScrapeResult(
            info_hash=info_hash,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=1234567890,
            scrape_count=1,
        )
        mock_ipc_client.scrape_torrent = AsyncMock(return_value=expected_result)

        result = await adapter.scrape_torrent(info_hash, force=force)

        assert result == expected_result
        mock_ipc_client.scrape_torrent.assert_called_once_with(info_hash, force=force)

    @pytest.mark.asyncio
    async def test_list_scrape_results_delegates(self, adapter, mock_ipc_client):
        """Test list_scrape_results delegates to IPC client."""
        expected_response = ScrapeListResponse(
            results=[
                ScrapeResult(
                    info_hash="a" * 40,
                    seeders=100,
                    leechers=50,
                    completed=1000,
                    last_scrape_time=1234567890,
                    scrape_count=1,
                )
            ]
        )
        mock_ipc_client.list_scrape_results = AsyncMock(return_value=expected_response)

        result = await adapter.list_scrape_results()

        assert result == expected_response
        mock_ipc_client.list_scrape_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_scrape_result_delegates(self, adapter, mock_ipc_client):
        """Test get_scrape_result delegates to IPC client."""
        info_hash = "a" * 40
        expected_result = ScrapeResult(
            info_hash=info_hash,
            seeders=100,
            leechers=50,
            completed=1000,
            last_scrape_time=1234567890,
            scrape_count=1,
        )
        mock_ipc_client.get_scrape_result = AsyncMock(return_value=expected_result)

        result = await adapter.get_scrape_result(info_hash)

        assert result == expected_result
        mock_ipc_client.get_scrape_result.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_get_scrape_result_not_found(self, adapter, mock_ipc_client):
        """Test get_scrape_result returns None when not found."""
        info_hash = "a" * 40
        mock_ipc_client.get_scrape_result = AsyncMock(return_value=None)

        result = await adapter.get_scrape_result(info_hash)

        assert result is None
        mock_ipc_client.get_scrape_result.assert_called_once_with(info_hash)


class TestDaemonSessionAdapterConfigOps:
    """Test config operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_get_config_delegates(self, adapter, mock_ipc_client):
        """Test get_config delegates to IPC client."""
        expected_config = {"network": {"enable_tcp": True}, "discovery": {"enable_dht": True}}
        mock_ipc_client.get_config = AsyncMock(return_value=expected_config)

        result = await adapter.get_config()

        assert result == expected_config
        mock_ipc_client.get_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_config_delegates(self, adapter, mock_ipc_client):
        """Test update_config delegates to IPC client."""
        config_dict = {"network": {"enable_tcp": False}}
        expected_result = {"status": "updated", "restart_required": False}
        mock_ipc_client.update_config = AsyncMock(return_value=expected_result)

        result = await adapter.update_config(config_dict)

        assert result == expected_result
        mock_ipc_client.update_config.assert_called_once_with(config_dict)


class TestDaemonSessionAdapterProtocolOps:
    """Test protocol operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_get_xet_protocol_delegates(self, adapter, mock_ipc_client):
        """Test get_xet_protocol delegates to IPC client."""
        expected_protocol = ProtocolInfo(
            enabled=True, status="active", details={"name": "XET", "version": "1.0"}
        )
        mock_ipc_client.get_xet_protocol = AsyncMock(return_value=expected_protocol)

        result = await adapter.get_xet_protocol()

        assert result == expected_protocol
        mock_ipc_client.get_xet_protocol.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_ipfs_protocol_delegates(self, adapter, mock_ipc_client):
        """Test get_ipfs_protocol delegates to IPC client."""
        expected_protocol = ProtocolInfo(
            enabled=False, status="inactive", details={"name": "IPFS", "version": "1.0"}
        )
        mock_ipc_client.get_ipfs_protocol = AsyncMock(return_value=expected_protocol)

        result = await adapter.get_ipfs_protocol()

        assert result == expected_protocol
        mock_ipc_client.get_ipfs_protocol.assert_called_once()


class TestDaemonSessionAdapterPeerOps:
    """Test peer operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_get_peers_for_torrent_delegates_and_converts(self, adapter, mock_ipc_client):
        """Test get_peers_for_torrent delegates and converts response."""
        from ccbt.daemon.ipc_protocol import PeerInfo, PeerListResponse

        info_hash = "a" * 40
        peer_list_response = PeerListResponse(
            info_hash=info_hash,
            peers=[
                PeerInfo(
                    ip="192.168.1.1",
                    port=6881,
                    download_rate=1000.0,
                    upload_rate=500.0,
                    choked=False,
                    client="TestClient",
                ),
                PeerInfo(
                    ip="192.168.1.2",
                    port=6882,
                    download_rate=2000.0,
                    upload_rate=1000.0,
                    choked=True,
                    client=None,
                ),
            ],
            count=2,
        )
        mock_ipc_client.get_peers_for_torrent = AsyncMock(return_value=peer_list_response)

        result = await adapter.get_peers_for_torrent(info_hash)

        assert len(result) == 2
        assert result[0]["ip"] == "192.168.1.1"
        assert result[0]["port"] == 6881
        assert result[0]["download_rate"] == 1000.0
        assert result[0]["upload_rate"] == 500.0
        assert result[0]["choked"] is False
        assert result[0]["client"] == "TestClient"
        assert result[1]["ip"] == "192.168.1.2"
        assert result[1]["choked"] is True
        assert result[1]["client"] is None
        mock_ipc_client.get_peers_for_torrent.assert_called_once_with(info_hash)


class TestDaemonSessionAdapterXETOps:
    """Test XET folder operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_add_xet_folder_delegates(self, adapter, mock_ipc_client):
        """Test add_xet_folder delegates to IPC client."""
        folder_path = "/test/folder"
        result_dict = {"folder_key": folder_path, "info_hash": "a" * 40}
        mock_ipc_client.add_xet_folder = AsyncMock(return_value=result_dict)

        result = await adapter.add_xet_folder(folder_path)

        assert result["folder_key"] == folder_path
        mock_ipc_client.add_xet_folder.assert_called_once_with(
            folder_path=folder_path,
            tonic_file=None,
            tonic_link=None,
            sync_mode=None,
            source_peers=None,
            check_interval=None,
        )

    @pytest.mark.asyncio
    async def test_add_xet_folder_with_all_params(self, adapter, mock_ipc_client):
        """Test add_xet_folder with all parameters."""
        folder_path = "/test/folder"
        tonic_file = "/test/tonic.tonic"
        tonic_link = "tonic://test"
        sync_mode = "bidirectional"
        source_peers = ["peer1", "peer2"]
        check_interval = 60.0
        result_dict = {"folder_key": folder_path}
        mock_ipc_client.add_xet_folder = AsyncMock(return_value=result_dict)

        result = await adapter.add_xet_folder(
            folder_path,
            tonic_file=tonic_file,
            tonic_link=tonic_link,
            sync_mode=sync_mode,
            source_peers=source_peers,
            check_interval=check_interval,
        )

        assert result["folder_key"] == folder_path
        mock_ipc_client.add_xet_folder.assert_called_once_with(
            folder_path=folder_path,
            tonic_file=tonic_file,
            tonic_link=tonic_link,
            sync_mode=sync_mode,
            source_peers=source_peers,
            check_interval=check_interval,
        )

    @pytest.mark.asyncio
    async def test_remove_xet_folder_delegates(self, adapter, mock_ipc_client):
        """Test remove_xet_folder delegates to IPC client."""
        folder_key = "/test/folder"
        result_dict = {"success": True}
        mock_ipc_client.remove_xet_folder = AsyncMock(return_value=result_dict)

        result = await adapter.remove_xet_folder(folder_key)

        assert result is True
        mock_ipc_client.remove_xet_folder.assert_called_once_with(folder_key)

    @pytest.mark.asyncio
    async def test_remove_xet_folder_returns_false(self, adapter, mock_ipc_client):
        """Test remove_xet_folder returns False when not found."""
        folder_key = "/test/folder"
        result_dict = {"success": False}
        mock_ipc_client.remove_xet_folder = AsyncMock(return_value=result_dict)

        result = await adapter.remove_xet_folder(folder_key)

        assert result is False

    @pytest.mark.asyncio
    async def test_list_xet_folders_delegates(self, adapter, mock_ipc_client):
        """Test list_xet_folders delegates to IPC client."""
        expected_folders = [
            {"folder_key": "/test/folder1", "status": "active"},
            {"folder_key": "/test/folder2", "status": "paused"},
        ]
        result_dict = {"folders": expected_folders}
        mock_ipc_client.list_xet_folders = AsyncMock(return_value=result_dict)

        result = await adapter.list_xet_folders()

        assert result == expected_folders
        mock_ipc_client.list_xet_folders.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_xet_folders_returns_list_directly(self, adapter, mock_ipc_client):
        """Test list_xet_folders handles list response directly."""
        expected_folders = [
            {"folder_key": "/test/folder1", "status": "active"},
        ]
        mock_ipc_client.list_xet_folders = AsyncMock(return_value=expected_folders)

        result = await adapter.list_xet_folders()

        assert result == expected_folders

    @pytest.mark.asyncio
    async def test_get_xet_folder_status_delegates(self, adapter, mock_ipc_client):
        """Test get_xet_folder_status delegates to IPC client."""
        folder_key = "/test/folder"
        expected_status = {"status": "active", "sync_mode": "bidirectional"}
        mock_ipc_client.get_xet_folder_status = AsyncMock(return_value=expected_status)

        result = await adapter.get_xet_folder_status(folder_key)

        assert result == expected_status
        mock_ipc_client.get_xet_folder_status.assert_called_once_with(folder_key)

    @pytest.mark.asyncio
    async def test_get_xet_folder_status_not_found(self, adapter, mock_ipc_client):
        """Test get_xet_folder_status returns None when not found."""
        folder_key = "/test/folder"
        mock_ipc_client.get_xet_folder_status = AsyncMock(return_value=None)

        result = await adapter.get_xet_folder_status(folder_key)

        assert result is None

    @pytest.mark.asyncio
    async def test_set_xet_folder_sync_mode_delegates(self, adapter, mock_ipc_client):
        """Test set_xet_folder_sync_mode delegates to IPC client."""
        folder_key = "/test/folder"
        expected = {
            "folder_key": folder_key,
            "sync_mode": "designated",
            "source_peers": ["peer-a"],
        }
        mock_ipc_client.set_xet_folder_sync_mode = AsyncMock(return_value=expected)

        result = await adapter.set_xet_folder_sync_mode(
            folder_key,
            "designated",
            source_peers=["peer-a"],
        )

        assert result == expected
        mock_ipc_client.set_xet_folder_sync_mode.assert_called_once_with(
            folder_key,
            "designated",
            source_peers=["peer-a"],
        )


class TestDaemonSessionAdapterRateLimitOps:
    """Test rate limit operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_set_rate_limits_delegates(self, adapter, mock_ipc_client):
        """Test set_rate_limits delegates to IPC client."""
        info_hash = "a" * 40
        download_kib = 100
        upload_kib = 50
        mock_ipc_client.set_rate_limits = AsyncMock(return_value=True)

        result = await adapter.set_rate_limits(info_hash, download_kib, upload_kib)

        assert result is True
        mock_ipc_client.set_rate_limits.assert_called_once_with(
            info_hash, download_kib, upload_kib
        )

    @pytest.mark.asyncio
    async def test_set_rate_limits_connection_error(self, adapter, mock_ipc_client):
        """Test set_rate_limits raises RuntimeError on connection failure."""
        info_hash = "a" * 40
        mock_ipc_client.set_rate_limits = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                "Connection refused",
                OSError("Connection refused"),
            )
        )

        with pytest.raises(RuntimeError, match="Cannot connect to daemon"):
            await adapter.set_rate_limits(info_hash, 100, 50)

    @pytest.mark.asyncio
    async def test_set_rate_limits_404_returns_false(self, adapter, mock_ipc_client):
        """Test set_rate_limits returns False on 404."""
        info_hash = "a" * 40
        mock_ipc_client.set_rate_limits = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=404,
                message="Not Found",
            )
        )

        result = await adapter.set_rate_limits(info_hash, 100, 50)
        assert result is False

    @pytest.mark.asyncio
    async def test_set_rate_limits_other_http_error_raises(self, adapter, mock_ipc_client):
        """Test set_rate_limits raises on non-404 HTTP errors."""
        info_hash = "a" * 40
        mock_ipc_client.set_rate_limits = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=500,
                message="Internal Server Error",
            )
        )

        with pytest.raises(RuntimeError, match="Daemon error"):
            await adapter.set_rate_limits(info_hash, 100, 50)


class TestDaemonSessionAdapterOtherOps:
    """Test other operations."""

    @pytest.fixture
    def mock_ipc_client(self):
        """Create mock IPC client."""
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_ipc_client):
        """Create DaemonSessionAdapter."""
        return DaemonSessionAdapter(mock_ipc_client)

    @pytest.mark.asyncio
    async def test_force_announce_delegates(self, adapter, mock_ipc_client):
        """Test force_announce delegates to IPC client."""
        info_hash = "a" * 40
        result_dict = {"success": True}
        mock_ipc_client.force_announce = AsyncMock(return_value=result_dict)

        result = await adapter.force_announce(info_hash)

        assert result is True
        mock_ipc_client.force_announce.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_force_announce_returns_false(self, adapter, mock_ipc_client):
        """Test force_announce returns False when unsuccessful."""
        info_hash = "a" * 40
        result_dict = {"success": False}
        mock_ipc_client.force_announce = AsyncMock(return_value=result_dict)

        result = await adapter.force_announce(info_hash)

        assert result is False

    @pytest.mark.asyncio
    async def test_export_session_state_delegates(self, adapter, mock_ipc_client):
        """Test export_session_state delegates to IPC client."""
        path = "/test/state.json"
        mock_ipc_client.export_session_state = AsyncMock(return_value=None)

        await adapter.export_session_state(path)

        mock_ipc_client.export_session_state.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_refresh_pex_delegates(self, adapter, mock_ipc_client):
        """Test refresh_pex delegates to IPC client."""
        info_hash = "a" * 40
        expected_result = {"success": True, "status": "refreshed"}
        mock_ipc_client.refresh_pex = AsyncMock(return_value=expected_result)

        result = await adapter.refresh_pex(info_hash)

        assert result == expected_result
        mock_ipc_client.refresh_pex.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_rehash_torrent_delegates(self, adapter, mock_ipc_client):
        """Test rehash_torrent delegates to IPC client."""
        info_hash = "a" * 40
        rehash_result = {
            "success": True,
            "info_hash": info_hash,
            "verified_files": ["file1.txt"],
            "failed_files": [],
        }
        mock_ipc_client.rehash_torrent = AsyncMock(return_value=rehash_result)

        result = await adapter.rehash_torrent(info_hash)

        assert result["success"] is True
        assert result["info_hash"] == info_hash
        mock_ipc_client.rehash_torrent.assert_called_once_with(info_hash)

    @pytest.mark.asyncio
    async def test_rehash_torrent_handles_error(self, adapter, mock_ipc_client):
        """Test rehash_torrent handles errors gracefully."""
        info_hash = "a" * 40
        mock_ipc_client.rehash_torrent = AsyncMock(side_effect=Exception("Test error"))

        result = await adapter.rehash_torrent(info_hash)

        assert result["success"] is False
        assert result["info_hash"] == info_hash
        assert "error" in result

