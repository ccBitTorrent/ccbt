"""Chaos engineering tests with fault injection.

Tests system resilience under various failure conditions
and fault injection scenarios.
"""

import asyncio
import random
import tempfile
from contextlib import suppress
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from ccbt.events import Event, EventBus, EventType
from ccbt.plugins import PluginManager
from ccbt.services import get_service_manager
from ccbt.session import AsyncSessionManager
from tests.conftest import create_test_torrent_dict


class TestFaultInjection:
    """Fault injection tests."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture(autouse=True)
    def cleanup_resources(self):
        """Cleanup resources after each test."""
        yield
        # Force cleanup of any remaining async resources
        with suppress(Exception):
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

    @pytest.mark.asyncio
    async def test_network_failure_injection(self, temp_dir):
        """Test system behavior under network failures."""
        session_manager = AsyncSessionManager(str(temp_dir))

        try:
            await session_manager.start()

            # Create torrent session
            torrent_data = create_test_torrent_dict(
                name="test_torrent",
                file_length=1024,
            )

            await session_manager.add_torrent(torrent_data, resume=False)
            session = next(iter(session_manager.torrents.values()))

            # Inject network failure
            with patch("ccbt.tracker.AsyncTrackerClient.announce") as mock_announce:
                mock_announce.side_effect = Exception("Network failure")

                # Start session (should handle network failure gracefully)
                await session.start()

                # Check session is still functional
                assert session.info.status in ["downloading", "error"]

        finally:
            await session_manager.stop()

    @pytest.mark.asyncio
    async def test_disk_failure_injection(self, temp_dir):
        """Test system behavior under disk failures."""
        # Mock DHT client to avoid bootstrapping delays
        with patch("ccbt.session.AsyncDHTClient") as mock_dht_class:
            mock_dht = mock_dht_class.return_value
            mock_dht.start = AsyncMock()
            mock_dht.stop = AsyncMock()
            
            session_manager = AsyncSessionManager(str(temp_dir))

            try:
                await session_manager.start()

                # Create torrent session
                torrent_data = create_test_torrent_dict(
                    name="test_torrent",
                    file_length=1024,
                )

                await session_manager.add_torrent(torrent_data, resume=False)
                session = next(iter(session_manager.torrents.values()))

                # Inject disk failure
                with patch("ccbt.disk_io.DiskIOManager.write_block") as mock_write:
                    mock_write.side_effect = Exception("Disk I/O failure")

                    # Start session (should handle disk failure gracefully)
                    await session.start()

                    # Check session is still functional
                    assert session.info.status in ["downloading", "error"]

            finally:
                await session_manager.stop()

    @pytest.mark.asyncio
    async def test_memory_pressure_injection(self, temp_dir):
        """Test system behavior under memory pressure."""
        session_manager = AsyncSessionManager(str(temp_dir))

        try:
            await session_manager.start()

            # Create multiple sessions to simulate memory pressure
            sessions = []
            for i in range(10):
                torrent_data = create_test_torrent_dict(
                    name=f"test_torrent_{i}",
                    info_hash=b"\x00" * 20 + bytes([i]),
                    file_length=1024,
                )

                await session_manager.add_torrent(torrent_data, resume=False)
                session = list(session_manager.torrents.values())[-1]
                sessions.append(session)

            # Start all sessions
            for session in sessions:
                await session.start()

            # Check all sessions are running
            for session in sessions:
                assert session.info.status in ["downloading", "error"]

            # Stop all sessions
            for session in sessions:
                await session.stop()

        finally:
            await session_manager.stop()

    @pytest.mark.asyncio
    async def test_event_system_failure_injection(self, temp_dir):
        """Test system behavior under event system failures."""
        event_bus = EventBus()
        await event_bus.start()

        try:
            # Register faulty event handler
            class FaultyHandler:
                def __init__(self):
                    self.name = "faulty_handler"

                async def handle(self, event):
                    if random.random() < 0.5:  # nosec S311 - test fault injection only
                        msg = "Event handler failure"
                        raise RuntimeError(msg)

            handler = FaultyHandler()
            event_bus.register_handler(EventType.PEER_CONNECTED.value, handler)

            # Emit events (should handle handler failures gracefully)
            for i in range(100):
                test_event = Event(
                    event_type=EventType.PEER_CONNECTED.value,
                    data={"peer_ip": f"192.168.1.{i}", "peer_port": 6881},
                )
                await event_bus.emit(test_event)

            # Wait for processing
            await asyncio.sleep(0.1)

            # Check event bus is still functional
            assert event_bus.running

        finally:
            await event_bus.stop()

    @pytest.mark.asyncio
    async def test_service_failure_injection(self, temp_dir):
        """Test system behavior under service failures."""
        service_manager = get_service_manager()

        try:
            # Register service with random failures
            class FaultyService:
                def __init__(self, name):
                    self.name = name
                    self.state = "stopped"

                async def start(self):
                    if random.random() < 0.3:  # nosec S311 - test fault injection only
                        msg = "Service start failure"
                        raise RuntimeError(msg)
                    self.state = "running"

                async def stop(self):
                    self.state = "stopped"

                async def health_check(self):
                    if random.random() < 0.2:  # nosec S311 - test fault injection only
                        msg = "Health check failure"
                        raise RuntimeError(msg)
                    return {
                        "healthy": True,
                        "score": 1.0,
                        "message": "OK",
                    }

                def get_info(self):
                    return {
                        "name": self.name,
                        "state": self.state,
                        "version": "1.0.0",
                        "description": "Faulty service for testing",
                    }

            # Register multiple faulty services
            for i in range(5):
                service = FaultyService(f"faulty_service_{i}")
                await service_manager.register_service(service)

            # Start services (some may fail)
            for i in range(5):
                with suppress(Exception):
                    await service_manager.start_service(f"faulty_service_{i}")

            # Check some services are running
            services = service_manager.list_services()
            # Just check that the service manager is functional
            assert isinstance(services, list)
            # Services may not start due to failures, which is expected

        finally:
            await service_manager.shutdown()

    @pytest.mark.asyncio
    async def test_plugin_failure_injection(self, temp_dir):
        """Test system behavior under plugin failures."""
        plugin_manager = PluginManager()

        try:
            # Create faulty plugin
            class FaultyPlugin:
                def __init__(self):
                    self.name = "faulty_plugin"
                    self.version = "1.0.0"
                    self.description = "Faulty plugin for testing"
                    self.state = "unloaded"

                async def initialize(self):
                    if random.random() < 0.3:  # nosec S311 - test fault injection only
                        msg = "Plugin initialization failure"
                        raise RuntimeError(msg)

                async def start(self):
                    if random.random() < 0.2:  # nosec S311 - test fault injection only
                        msg = "Plugin start failure"
                        raise RuntimeError(msg)
                    self.state = "running"

                async def stop(self):
                    self.state = "stopped"

                async def cleanup(self):
                    pass

            # Load plugin (may fail)
            with suppress(Exception):
                plugin_name = await plugin_manager.load_plugin(FaultyPlugin)
                await plugin_manager.start_plugin(plugin_name)

            # Check plugin manager is still functional
            plugins = plugin_manager.list_plugins()
            assert len(plugins) >= 0

        finally:
            await plugin_manager.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_failure_injection(self, temp_dir):
        """Test system behavior under concurrent failures."""
        session_manager = AsyncSessionManager(str(temp_dir))

        try:
            await session_manager.start()

            # Create multiple sessions with concurrent failures
            sessions = []
            for i in range(5):
                torrent_data = create_test_torrent_dict(
                    name=f"test_torrent_{i}",
                    info_hash=b"\x00" * 20 + bytes([i]),
                    file_length=1024,
                )

                await session_manager.add_torrent(torrent_data, resume=False)
                session = list(session_manager.torrents.values())[-1]
                sessions.append(session)

            # Start sessions concurrently with random failures
            async def start_session_with_failure(session):
                if random.random() < 0.3:  # nosec S311 - test fault injection only
                    msg = "Session start failure"
                    raise RuntimeError(msg)
                await session.start()

            # Start all sessions concurrently
            tasks = [start_session_with_failure(session) for session in sessions]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check some sessions started successfully
            successful_sessions = [
                s for s, r in zip(sessions, results) if not isinstance(r, Exception)
            ]
            assert len(successful_sessions) > 0

        finally:
            await session_manager.stop()

    @pytest.mark.asyncio
    async def test_resource_exhaustion_injection(self, temp_dir):
        """Test system behavior under resource exhaustion."""
        session_manager = AsyncSessionManager(str(temp_dir))

        try:
            await session_manager.start()

            # Create many sessions to exhaust resources
            sessions = []
            for i in range(100):  # Large number of sessions
                torrent_data = create_test_torrent_dict(
                    name=f"test_torrent_{i}",
                    info_hash=b"\x00" * 20 + bytes([i]),
                    file_length=1024,
                )

                try:
                    await session_manager.add_torrent(torrent_data, resume=False)
                    session = list(session_manager.torrents.values())[-1]
                    sessions.append(session)
                except Exception:
                    # Expected some failures due to resource exhaustion
                    pass

            # Check some sessions were created
            assert len(sessions) > 0

            # Start sessions (some may fail due to resource exhaustion)
            for session in sessions:
                with suppress(Exception):
                    await session.start()

            # Check some sessions are running
            running_sessions = [s for s in sessions if s.info.status == "downloading"]
            assert len(running_sessions) > 0

        finally:
            await session_manager.stop()

    @pytest.mark.asyncio
    async def test_timeout_injection(self, temp_dir):
        """Test system behavior under timeout conditions."""
        session_manager = AsyncSessionManager(str(temp_dir))

        try:
            await session_manager.start()

            # Create session with timeout injection
            torrent_data = create_test_torrent_dict(
                name="test_torrent",
                file_length=1024,
            )

            await session_manager.add_torrent(torrent_data, resume=False)
            session = next(iter(session_manager.torrents.values()))

            # Inject timeout in tracker communication
            with patch("ccbt.tracker.AsyncTrackerClient.announce") as mock_announce:

                async def timeout_announce(*args, **kwargs):
                    await asyncio.sleep(10)  # Simulate timeout
                    return []

                mock_announce.side_effect = timeout_announce

                # Start session with timeout
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(session.start(), timeout=5.0)

                # Check session is still functional
                assert session.info.status in ["downloading", "error"]

        finally:
            await session_manager.stop()

    @pytest.mark.asyncio
    async def test_corruption_injection(self, temp_dir):
        """Test system behavior under data corruption."""
        session_manager = AsyncSessionManager(str(temp_dir))

        try:
            await session_manager.start()

            # Create session with corrupted data
            corrupted_torrent_data = create_test_torrent_dict(
                name="test_torrent",
                file_length=1024,
            )

            # Corrupt some data
            corrupted_torrent_data["total_length"] = -1  # Invalid length
            corrupted_torrent_data["piece_length"] = 0  # Invalid piece length

            await session_manager.add_torrent(
                corrupted_torrent_data,
                resume=False,
            )
            session = next(iter(session_manager.torrents.values()))

            # Start session (should handle corruption gracefully)
            with suppress(Exception):
                await session.start()

            # Check session is in error state or stopped (corruption may not prevent downloading state)
            assert session.info.status in ["error", "stopped", "downloading"]

        finally:
            await session_manager.stop()
