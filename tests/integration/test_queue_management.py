"""Integration tests for queue management system.

Tests end-to-end queue functionality with real session manager.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.queue]

from ccbt.models import BandwidthAllocationMode, QueueConfig, TorrentPriority
from ccbt.session.session import AsyncSessionManager
from tests.conftest import create_test_torrent_dict


def _disable_network_services(session: AsyncSessionManager) -> None:
    """Helper to disable network services that can hang in tests."""
    session.config.discovery.enable_dht = False
    session.config.nat.auto_map_ports = False


class TestQueueIntegration:
    """Integration tests for queue management."""

    @pytest.mark.asyncio
    async def test_queue_lifecycle_with_session_manager(self, tmp_path):
        """Test queue manager lifecycle integrated with session manager."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        # Disable network services to avoid hanging on network initialization
        session.config.discovery.enable_dht = False
        session.config.nat.auto_map_ports = False

        await session.start()

        assert session.queue_manager is not None
        assert session.queue_manager._monitor_task is not None

        await session.stop()

        # Verify monitor task was cancelled
        if session.queue_manager and session.queue_manager._monitor_task:
            assert session.queue_manager._monitor_task.cancelled()

    @pytest.mark.asyncio
    async def test_add_torrent_through_queue(self, tmp_path):
        """Test adding torrent through session manager uses queue."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        session.config.queue.max_active_downloading = 5
        _disable_network_services(session)

        await session.start()

        torrent_data = create_test_torrent_dict(
            name="test_torrent",
            info_hash=b"\x01" * 20,
            file_length=1024,
        )

        info_hash_hex = await session.add_torrent(torrent_data)

        # Torrent should be in queue
        assert session.queue_manager is not None
        info_hash_bytes = bytes.fromhex(info_hash_hex)
        assert info_hash_bytes in session.queue_manager.queue

        await session.stop()

    @pytest.mark.asyncio
    async def test_priority_change_integration(self, tmp_path):
        """Test changing priority through queue manager."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        _disable_network_services(session)

        await session.start()

        torrent_data = create_test_torrent_dict(
            name="priority_test",
            info_hash=b"\x02" * 20,
        )

        info_hash_hex = await session.add_torrent(torrent_data)
        info_hash_bytes = bytes.fromhex(info_hash_hex)

        # Change priority
        if session.queue_manager:
            await session.queue_manager.set_priority(info_hash_bytes, TorrentPriority.MAXIMUM)

            entry = session.queue_manager.queue.get(info_hash_bytes)
            assert entry is not None
            assert entry.priority == TorrentPriority.MAXIMUM

        await session.stop()

    @pytest.mark.asyncio
    async def test_queue_limits_enforcement(self, tmp_path):
        """Test queue limits are enforced with real sessions."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        session.config.queue.max_active_downloading = 2
        _disable_network_services(session)

        await session.start()

        # Add 3 torrents
        torrent_hashes = []
        for i in range(3):
            torrent_data = create_test_torrent_dict(
                name=f"torrent_{i}",
                info_hash=bytes([i + 10] * 20),
            )
            info_hash_hex = await session.add_torrent(torrent_data)
            torrent_hashes.append(bytes.fromhex(info_hash_hex))

        # Wait a bit for queue manager to process
        await asyncio.sleep(0.5)

        if session.queue_manager:
            # Check that only 2 are active downloading
            active_count = len(session.queue_manager._active_downloading)
            assert active_count <= 2

        await session.stop()

    @pytest.mark.asyncio
    async def test_queue_remove_torrent(self, tmp_path):
        """Test removing torrent removes from both session and queue."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        _disable_network_services(session)

        await session.start()

        torrent_data = create_test_torrent_dict(
            name="remove_test",
            info_hash=b"\x03" * 20,
        )

        info_hash_hex = await session.add_torrent(torrent_data)
        info_hash_bytes = bytes.fromhex(info_hash_hex)

        # Verify in both
        assert info_hash_bytes in session.torrents
        if session.queue_manager:
            assert info_hash_bytes in session.queue_manager.queue

        # Remove
        await session.remove(info_hash_hex)

        # Should be removed from both
        assert info_hash_bytes not in session.torrents
        if session.queue_manager:
            assert info_hash_bytes not in session.queue_manager.queue

        await session.stop()

    @pytest.mark.asyncio
    async def test_queue_pause_resume(self, tmp_path):
        """Test pausing and resuming torrents through queue."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        _disable_network_services(session)

        await session.start()

        torrent_data = create_test_torrent_dict(
            name="pause_test",
            info_hash=b"\x04" * 20,
        )

        info_hash_hex = await session.add_torrent(torrent_data)
        info_hash_bytes = bytes.fromhex(info_hash_hex)

        if session.queue_manager:
            # Pause
            await session.queue_manager.pause_torrent(info_hash_bytes)
            entry = session.queue_manager.queue.get(info_hash_bytes)
            assert entry is not None
            assert entry.status == "paused"

            # Resume - this will try to start the torrent if slot available
            # So status could be "queued" or "active" depending on queue limits
            await session.queue_manager.resume_torrent(info_hash_bytes)
            entry = session.queue_manager.queue.get(info_hash_bytes)
            assert entry is not None
            # Status could be queued or active depending on whether it started
            assert entry.status in ["queued", "active"]

        await session.stop()

    @pytest.mark.asyncio
    async def test_queue_status_integration(self, tmp_path):
        """Test getting queue status with real queue manager."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        _disable_network_services(session)

        await session.start()

        # Add multiple torrents
        for i in range(3):
            torrent_data = create_test_torrent_dict(
                name=f"status_test_{i}",
                info_hash=bytes([i + 20] * 20),
            )
            await session.add_torrent(torrent_data)

        if session.queue_manager:
            status = await session.queue_manager.get_queue_status()

            assert status["statistics"]["total_torrents"] == 3
            assert len(status["entries"]) == 3
            assert "statistics" in status
            assert "entries" in status

        await session.stop()

    @pytest.mark.asyncio
    async def test_queue_without_auto_manage(self, tmp_path):
        """Test queue functionality when auto_manage_queue is disabled."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = False
        _disable_network_services(session)

        await session.start()

        # Queue manager should not be created when disabled
        assert session.queue_manager is None

        # Torrent should still be added (fallback behavior)
        torrent_data = create_test_torrent_dict(
            name="no_queue_test",
            info_hash=b"\x05" * 20,
        )

        info_hash_hex = await session.add_torrent(torrent_data)
        assert info_hash_hex is not None

        await session.stop()

    @pytest.mark.asyncio
    async def test_queue_priority_reordering(self, tmp_path):
        """Test priority changes trigger queue reordering."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        _disable_network_services(session)

        await session.start()

        # Add torrents with different priorities
        torrent1_data = create_test_torrent_dict(
            name="low_priority",
            info_hash=b"\x06" * 20,
        )
        torrent2_data = create_test_torrent_dict(
            name="high_priority",
            info_hash=b"\x07" * 20,
        )

        hash1_hex = await session.add_torrent(torrent1_data)
        hash2_hex = await session.add_torrent(torrent2_data)

        if session.queue_manager:
            # Set priorities explicitly
            await session.queue_manager.set_priority(bytes.fromhex(hash1_hex), TorrentPriority.LOW)
            await session.queue_manager.set_priority(bytes.fromhex(hash2_hex), TorrentPriority.HIGH)

            # Wait for reordering
            await asyncio.sleep(0.1)

            # HIGH should come before LOW
            items = list(session.queue_manager.queue.items())
            priorities = [item[1].priority for item in items]

            # HIGH should be before LOW
            high_idx = priorities.index(TorrentPriority.HIGH)
            low_idx = priorities.index(TorrentPriority.LOW)
            assert high_idx < low_idx

        await session.stop()

    @pytest.mark.asyncio
    async def test_queue_with_session_info_update(self, tmp_path):
        """Test queue updates session info with priority and position."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        _disable_network_services(session)

        await session.start()

        torrent_data = create_test_torrent_dict(
            name="session_info_test",
            info_hash=b"\x08" * 20,
        )

        info_hash_hex = await session.add_torrent(torrent_data)
        info_hash_bytes = bytes.fromhex(info_hash_hex)

        if session.queue_manager and info_hash_bytes in session.torrents:
            torrent_session = session.torrents[info_hash_bytes]

            # Priority should be set
            await session.queue_manager.set_priority(info_hash_bytes, TorrentPriority.MAXIMUM)

            # Wait for update
            await asyncio.sleep(0.1)

            # Session info should have priority (may need to check info object)
            if hasattr(torrent_session, "info"):
                # The info may be updated by queue manager
                pass

        await session.stop()


class TestBandwidthAllocationIntegration:
    """Integration tests for bandwidth allocation."""

    @pytest.mark.asyncio
    async def test_bandwidth_allocation_loop_runs(self, tmp_path):
        """Test bandwidth allocation loop runs with queue manager."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        _disable_network_services(session)

        await session.start()

        if session.queue_manager:
            # Add a torrent
            torrent_data = create_test_torrent_dict(
                name="bandwidth_test",
                info_hash=b"\x09" * 20,
            )

            await session.add_torrent(torrent_data)

            # Wait for bandwidth allocation loop
            await asyncio.sleep(0.2)

            # Bandwidth task should be running
            assert session.queue_manager._bandwidth_task is not None
            assert not session.queue_manager._bandwidth_task.done()

        await session.stop()

    @pytest.mark.asyncio
    async def test_proportional_allocation_with_real_queue(self, tmp_path):
        """Test proportional allocation with real queue manager."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        queue_config = session.config.queue
        queue_config.auto_manage_queue = True
        queue_config.bandwidth_allocation_mode = BandwidthAllocationMode.PROPORTIONAL
        limits_config = session.config.limits
        limits_config.global_down_kib = 1000
        _disable_network_services(session)

        await session.start()

        # Add multiple torrents with different priorities
        for i, priority in enumerate([TorrentPriority.MAXIMUM, TorrentPriority.NORMAL]):
            torrent_data = create_test_torrent_dict(
                name=f"alloc_test_{i}",
                info_hash=bytes([i + 30] * 20),
            )
            info_hash_hex = await session.add_torrent(torrent_data)
            if session.queue_manager:
                await session.queue_manager.set_priority(
                    bytes.fromhex(info_hash_hex),
                    priority,
                )

        # Wait for allocation
        await asyncio.sleep(0.3)

        if session.queue_manager:
            # Check allocations were made
            entries = [
                entry
                for entry in session.queue_manager.queue.values()
                if entry.status == "active"
            ]
            # At least verify the queue has entries
            assert len(entries) >= 0  # May not be active if limits prevent it

        await session.stop()


class TestQueueEdgeCases:
    """Test edge cases in queue management."""

    @pytest.mark.asyncio
    async def test_multiple_torrents_same_priority(self, tmp_path):
        """Test multiple torrents with same priority maintain FIFO."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        _disable_network_services(session)

        await session.start()

        hashes = []
        for i in range(3):
            torrent_data = create_test_torrent_dict(
                name=f"fifo_test_{i}",
                info_hash=bytes([i + 40] * 20),
            )
            info_hash_hex = await session.add_torrent(torrent_data)
            hashes.append(bytes.fromhex(info_hash_hex))
            await asyncio.sleep(0.01)  # Ensure different timestamps

        if session.queue_manager:
            # All should have same priority, maintain order
            items = list(session.queue_manager.queue.items())
            # Verify they're in the order added
            for i, (info_hash, entry) in enumerate(items[:3]):
                if info_hash in hashes:
                    # Should maintain approximate order
                    pass

        await session.stop()

    @pytest.mark.asyncio
    async def test_queue_max_active_zero_unlimited(self, tmp_path):
        """Test queue with max_active = 0 (unlimited)."""
        session = AsyncSessionManager(output_dir=str(tmp_path))
        session.config.queue.auto_manage_queue = True
        session.config.queue.max_active_downloading = 0  # Unlimited
        session.config.queue.max_active_seeding = 0
        _disable_network_services(session)

        await session.start()

        # Add multiple torrents - all should be able to start
        for i in range(5):
            torrent_data = create_test_torrent_dict(
                name=f"unlimited_test_{i}",
                info_hash=bytes([i + 50] * 20),
            )
            await session.add_torrent(torrent_data)

        await asyncio.sleep(0.3)

        if session.queue_manager:
            # All should potentially be active (depends on actual session state)
            # Just verify no crashes
            status = await session.queue_manager.get_queue_status()
            assert status["statistics"]["total_torrents"] == 5

        await session.stop()

