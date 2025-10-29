"""End-to-end integration tests for ccBitTorrent.

Tests complete workflows from torrent parsing to download completion.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
import pytest_asyncio

from ccbt.events import EventType, get_event_bus
from ccbt.plugins import PluginManager
from ccbt.services import get_service_manager
from ccbt.session import AsyncSessionManager
from ccbt.torrent import TorrentParser
from tests.conftest import create_test_torrent_dict


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.fixture(autouse=True)
    def cleanup_resources(self):
        """Cleanup resources after each test."""
        yield
        # Force cleanup of any remaining async resources
        try:
            import asyncio
            import gc

            # Give a moment for cleanup
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule cleanup for later
                loop.call_later(0.1, lambda: gc.collect())
            else:
                # Run cleanup immediately
                asyncio.run(asyncio.sleep(0.1))
                gc.collect()
        except Exception:
            pass

    @pytest_asyncio.fixture
    async def event_bus(self):
        """Create and start event bus."""
        bus = get_event_bus()
        await bus.start()
        yield bus
        await bus.stop()

    @pytest_asyncio.fixture
    async def plugin_manager(self):
        """Create and start plugin manager."""
        manager = PluginManager()
        yield manager
        await manager.shutdown()

    @pytest_asyncio.fixture
    async def service_manager(self):
        """Create and start service manager."""
        manager = get_service_manager()
        yield manager
        await manager.shutdown()

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_torrent_data(self):
        """Create sample torrent data."""
        return create_test_torrent_dict(name="test_torrent", file_length=1024)

    @pytest.mark.asyncio
    async def test_torrent_parsing_integration(self, temp_dir, sample_torrent_data):
        """Test torrent parsing integration."""
        # Create a sample torrent file
        test_data_dir = temp_dir / "tests" / "data"
        test_data_dir.mkdir(parents=True, exist_ok=True)
        torrent_file = test_data_dir / "test.torrent"

        # Use proper bencode encoding instead of manual bytestring
        from ccbt.bencode import encode

        torrent_data = {
            "announce": "http://tracker.example.com/announce",
            "info": {
                "name": "test_torrent",
                "length": 1024,
                "piece length": 16384,
                "pieces": b"\x00" * 20,
            },
        }

        with open(torrent_file, "wb") as f:
            f.write(encode(torrent_data))

        # Parse torrent
        parser = TorrentParser()
        torrent_info = parser.parse(torrent_file)

        assert torrent_info.name == "test_torrent"
        assert torrent_info.total_length == 1024
        assert torrent_info.piece_length == 16384
        assert len(torrent_info.pieces) == 1

    @pytest.mark.asyncio
    async def test_session_management_integration(self, temp_dir, sample_torrent_data):
        """Test session management integration."""
        # Clean up any existing checkpoints to ensure fresh state
        import shutil

        checkpoint_dir = Path(".ccbt/checkpoints")
        if checkpoint_dir.exists():
            shutil.rmtree(checkpoint_dir, ignore_errors=True)

        # Mock DHT client to avoid bootstrapping delays
        with patch("ccbt.session.AsyncDHTClient") as mock_dht_class:
            mock_dht = mock_dht_class.return_value
            mock_dht.start = AsyncMock()
            mock_dht.stop = AsyncMock()
            
            # Create session manager
            session_manager = AsyncSessionManager(str(temp_dir))

            try:
                # Start session manager
                await session_manager.start()

                # Add torrent session
                info_hash = await session_manager.add_torrent(
                    sample_torrent_data,
                    resume=False,
                )

                assert info_hash is not None
                assert len(session_manager.torrents) == 1
                session = next(iter(session_manager.torrents.values()))
                assert session.info.name == "test_torrent"
                # Session automatically starts and goes to downloading state
                assert session.info.status in ["starting", "downloading"]

            finally:
                await session_manager.stop()

    @pytest.mark.asyncio
    async def test_event_system_integration(self, event_bus):
        """Test event system integration."""
        # Register event handler
        events_received = []

        class TestEventHandler:
            def __init__(self):
                self.name = "test_event_handler"

            def can_handle(self, event):
                return True

            async def handle(self, event):
                events_received.append(event)

        handler = TestEventHandler()
        event_bus.register_handler(EventType.PEER_CONNECTED.value, handler)

        # Emit test event
        from ccbt.events import emit_peer_connected

        await emit_peer_connected("192.168.1.1", 6881, "test_peer_id")

        # Wait for event processing
        await asyncio.sleep(0.1)

        # Check event was received
        assert len(events_received) == 1
        assert events_received[0].event_type == EventType.PEER_CONNECTED.value
        assert events_received[0].data["peer_ip"] == "192.168.1.1"
        assert events_received[0].data["peer_port"] == 6881

    @pytest.mark.asyncio
    async def test_plugin_system_integration(self, plugin_manager, event_bus):
        """Test plugin system integration."""
        # Load logging plugin
        from ccbt.plugins.logging_plugin import LoggingPlugin

        LoggingPlugin()
        plugin_name = await plugin_manager.load_plugin(LoggingPlugin)

        assert plugin_name == "LoggingPlugin"
        assert plugin_manager.get_plugin(plugin_name) is not None

        # Start plugin
        await plugin_manager.start_plugin(plugin_name)

        # Check plugin is running
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        assert plugin_info.state.value in ["running", "loading"]

        # Stop plugin
        await plugin_manager.stop_plugin(plugin_name)

        # Check plugin is stopped
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        assert plugin_info.state.value in ["stopped", "loading"]

    @pytest.mark.asyncio
    async def test_service_system_integration(self, service_manager):
        """Test service system integration."""
        # Register peer service
        from ccbt.services.peer_service import PeerService

        peer_service = PeerService()
        await service_manager.register_service(peer_service)

        # Start service
        await service_manager.start_service("peer_service")

        # Check service is running
        service_info = service_manager.get_service_info("peer_service")
        assert service_info.state.value in ["running", "stopped"]

        # Perform health check
        health_check = await peer_service.health_check()
        assert health_check.healthy

        # Stop service
        await service_manager.stop_service("peer_service")

        # Check service is stopped
        service_info = service_manager.get_service_info("peer_service")
        assert service_info.state.value == "stopped"

    @pytest.mark.asyncio
    async def test_complete_workflow_integration(
        self,
        temp_dir,
        sample_torrent_data,
        event_bus,
    ):
        """Test complete workflow integration."""
        # Start event bus
        await event_bus.start()

        # Create session manager
        # Mock DHT client to avoid bootstrapping delays
        with patch("ccbt.session.AsyncDHTClient") as mock_dht_class:
            mock_dht = mock_dht_class.return_value
            mock_dht.start = AsyncMock()
            mock_dht.stop = AsyncMock()
            
            session_manager = AsyncSessionManager(str(temp_dir))

            try:
                # Start session manager
                await session_manager.start()

                # Add torrent session
                await session_manager.add_torrent(
                    sample_torrent_data,
                    resume=False,
                )

                # Get the session object
                session = next(iter(session_manager.torrents.values()))

                # Start session
                await session.start()

                # Check session is running
                assert session.info.status == "downloading"

                # Simulate some activity
                await asyncio.sleep(0.1)

                # Stop session
                await session.stop()

                # Check session is stopped
                assert session.info.status == "stopped"

            finally:
                await session_manager.stop()
                await event_bus.stop()

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, temp_dir):
        """Test error handling integration."""
        # Test invalid torrent data
        invalid_torrent_data = create_test_torrent_dict(
            name="invalid_torrent",
            file_length=0,
            piece_length=0,
            num_pieces=0,
        )
        # Clear files to make it invalid
        invalid_torrent_data["files"] = []

        # Mock DHT client to avoid bootstrapping delays
        with patch("ccbt.session.AsyncDHTClient") as mock_dht_class:
            mock_dht = mock_dht_class.return_value
            mock_dht.start = AsyncMock()
            mock_dht.stop = AsyncMock()
            
            session_manager = AsyncSessionManager(str(temp_dir))

            try:
                await session_manager.start()

                # Add invalid torrent - should succeed but checkpoint operations should fail
                await session_manager.add_torrent(
                    invalid_torrent_data,
                    resume=False,
                )

                # Get the session object
                session = next(iter(session_manager.torrents.values()))

                # Start session - should succeed but log validation errors
                await session.start()

                # Stop session - checkpoint save should fail but not crash
                await session.stop()

                # Test passed if we get here without exceptions
                assert True

            finally:
                await session_manager.stop()

    @pytest.mark.asyncio
    async def test_concurrent_sessions_integration(self, temp_dir, sample_torrent_data):
        """Test concurrent sessions integration."""
        # Mock DHT client to avoid bootstrapping delays
        with patch("ccbt.session.AsyncDHTClient") as mock_dht_class:
            mock_dht = mock_dht_class.return_value
            mock_dht.start = AsyncMock()
            mock_dht.stop = AsyncMock()
            
            session_manager = AsyncSessionManager(str(temp_dir))

            try:
                await session_manager.start()

                # Create multiple sessions
                sessions = []
                for i in range(3):
                    torrent_data = create_test_torrent_dict(
                        name=f"test_torrent_{i}",
                        info_hash=b"\x00" * 20 + bytes([i]),
                        file_length=1024,
                    )

                    await session_manager.add_torrent(torrent_data, resume=False)
                    session = list(session_manager.torrents.values())[
                        -1
                    ]  # Get the last added session
                    sessions.append(session)

                # Check all sessions are created
                assert len(session_manager.torrents) == 3

                # Start all sessions
                for session in sessions:
                    await session.start()

                # Check all sessions are running
                for session in sessions:
                    assert session.info.status in ["starting", "downloading"]

                # Stop all sessions
                for session in sessions:
                    await session.stop()

                # Check all sessions are stopped
                for session in sessions:
                    assert session.info.status == "stopped"

            finally:
                await session_manager.stop()

    @pytest.mark.asyncio
    async def test_resource_cleanup_integration(self, temp_dir, sample_torrent_data):
        """Test resource cleanup integration."""
        # Mock DHT client to avoid bootstrapping delays
        with patch("ccbt.session.AsyncDHTClient") as mock_dht_class:
            mock_dht = mock_dht_class.return_value
            mock_dht.start = AsyncMock()
            mock_dht.stop = AsyncMock()
            
            session_manager = AsyncSessionManager(str(temp_dir))

            try:
                await session_manager.start()

                # Add torrent session
                await session_manager.add_torrent(
                    sample_torrent_data,
                    resume=False,
                )

                # Get the session object
                session = next(iter(session_manager.torrents.values()))

                # Start session
                await session.start()

                # Check session is running
                assert session.info.status in ["starting", "downloading"]

            finally:
                # Stop session manager (should cleanup all resources)
                await session_manager.stop()

                # Check session is stopped
                assert session.info.status == "stopped"

    @pytest.mark.asyncio
    async def test_performance_integration(self, temp_dir, sample_torrent_data):
        """Test performance integration."""
        # Mock DHT client to avoid bootstrapping delays
        with patch("ccbt.session.AsyncDHTClient") as mock_dht_class:
            mock_dht = mock_dht_class.return_value
            mock_dht.start = AsyncMock()
            mock_dht.stop = AsyncMock()
            
            session_manager = AsyncSessionManager(str(temp_dir))

            try:
                await session_manager.start()

                # Add torrent session
                await session_manager.add_torrent(
                    sample_torrent_data,
                    resume=False,
                )

                # Get the session object
                session = next(iter(session_manager.torrents.values()))

                # Start session
                start_time = asyncio.get_event_loop().time()
                await session.start()
                start_duration = asyncio.get_event_loop().time() - start_time

                # Check session started quickly
                assert start_duration < 1.0  # Should start within 1 second

                # Stop session
                stop_time = asyncio.get_event_loop().time()
                await session.stop()
                stop_duration = asyncio.get_event_loop().time() - stop_time

                # Check session stopped quickly
                assert stop_duration < 1.0  # Should stop within 1 second

            finally:
                await session_manager.stop()
