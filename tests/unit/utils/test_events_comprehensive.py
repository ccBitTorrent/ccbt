"""Comprehensive tests for events.py to achieve 99% coverage.

Covers:
- Event dataclass methods (to_dict, to_json, from_dict, from_json)
- Typed event classes __post_init__ methods
- EventHandler base class
- EventBus lifecycle and all methods
- Global event bus and convenience functions
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit]

from ccbt.utils.events import (
    Event,
    EventBus,
    EventHandler,
    EventPriority,
    EventType,
    PeerConnectedEvent,
    PeerDisconnectedEvent,
    PerformanceMetricEvent,
    PieceDownloadedEvent,
    TorrentCompletedEvent,
    emit_event,
    emit_peer_connected,
    emit_peer_disconnected,
    emit_performance_metric,
    emit_piece_downloaded,
    emit_torrent_completed,
    get_event_bus,
)


class TestEvent:
    """Test Event dataclass methods."""

    def test_event_to_dict(self):
        """Test Event.to_dict() - verify all fields included (lines 215-225)."""
        event = Event(
            event_type="test_event",
            timestamp=1234567890.0,
            event_id="test-id-123",
            priority=EventPriority.HIGH,
            source="test_source",
            data={"key": "value"},
            correlation_id="corr-123",
        )
        
        result = event.to_dict()
        
        assert result["event_type"] == "test_event"
        assert result["timestamp"] == 1234567890.0
        assert result["event_id"] == "test-id-123"
        assert result["priority"] == EventPriority.HIGH.value
        assert result["source"] == "test_source"
        assert result["data"] == {"key": "value"}
        assert result["correlation_id"] == "corr-123"

    def test_event_to_json(self):
        """Test Event.to_json() - verify JSON serialization (lines 227-229)."""
        event = Event(
            event_type="test_event",
            data={"key": "value"},
        )
        
        result = event.to_json()
        
        # Should be valid JSON
        data = json.loads(result)
        assert data["event_type"] == "test_event"
        assert data["data"] == {"key": "value"}

    def test_event_from_dict(self):
        """Test Event.from_dict() - verify deserialization (lines 231-242)."""
        data = {
            "event_type": "test_event",
            "timestamp": 1234567890.0,
            "event_id": "test-id-123",
            "priority": EventPriority.NORMAL.value,
            "source": "test_source",
            "data": {"key": "value"},
            "correlation_id": "corr-123",
        }
        
        event = Event.from_dict(data)
        
        assert event.event_type == "test_event"
        assert event.timestamp == 1234567890.0
        assert event.event_id == "test-id-123"
        assert event.priority == EventPriority.NORMAL
        assert event.source == "test_source"
        assert event.data == {"key": "value"}
        assert event.correlation_id == "corr-123"

    def test_event_from_dict_with_optional_fields(self):
        """Test Event.from_dict() - with optional fields missing (lines 240-241)."""
        data = {
            "event_type": "test_event",
            "timestamp": 1234567890.0,
            "event_id": "test-id",
            "priority": EventPriority.NORMAL.value,
            "data": {},
        }
        
        event = Event.from_dict(data)
        
        assert event.event_type == "test_event"
        assert event.source is None
        assert event.correlation_id is None

    def test_event_from_json(self):
        """Test Event.from_json() - verify JSON deserialization (lines 244-247)."""
        json_str = json.dumps({
            "event_type": "test_event",
            "timestamp": 1234567890.0,
            "event_id": "test-id",
            "priority": EventPriority.NORMAL.value,
            "data": {"key": "value"},
        })
        
        event = Event.from_json(json_str)
        
        assert event.event_type == "test_event"
        assert event.data == {"key": "value"}


class TestTypedEvents:
    """Test typed event classes __post_init__ methods."""

    def test_peer_connected_event_post_init(self):
        """Test PeerConnectedEvent.__post_init__() (lines 259-268)."""
        event = PeerConnectedEvent(
            peer_ip="192.168.1.1",
            peer_port=6881,
            peer_id="test-peer-id",
        )
        
        assert event.event_type == EventType.PEER_CONNECTED.value
        assert event.data["peer_ip"] == "192.168.1.1"
        assert event.data["peer_port"] == 6881
        assert event.data["peer_id"] == "test-peer-id"

    def test_peer_disconnected_event_post_init(self):
        """Test PeerDisconnectedEvent.__post_init__() (lines 279-288)."""
        event = PeerDisconnectedEvent(
            peer_ip="192.168.1.1",
            peer_port=6881,
            reason="Connection closed",
        )
        
        assert event.event_type == EventType.PEER_DISCONNECTED.value
        assert event.data["peer_ip"] == "192.168.1.1"
        assert event.data["peer_port"] == 6881
        assert event.data["reason"] == "Connection closed"

    def test_piece_downloaded_event_post_init(self):
        """Test PieceDownloadedEvent.__post_init__() (lines 300-310)."""
        event = PieceDownloadedEvent(
            piece_index=5,
            piece_size=16384,
            download_time=1.5,
            peer_ip="192.168.1.1",
        )
        
        assert event.event_type == EventType.PIECE_DOWNLOADED.value
        assert event.data["piece_index"] == 5
        assert event.data["piece_size"] == 16384
        assert event.data["download_time"] == 1.5
        assert event.data["peer_ip"] == "192.168.1.1"

    def test_torrent_completed_event_post_init(self):
        """Test TorrentCompletedEvent.__post_init__() (lines 322-332)."""
        event = TorrentCompletedEvent(
            torrent_name="test.torrent",
            total_size=1048576,
            download_time=60.0,
            average_speed=1000.0,
        )
        
        assert event.event_type == EventType.TORRENT_COMPLETED.value
        assert event.data["torrent_name"] == "test.torrent"
        assert event.data["total_size"] == 1048576
        assert event.data["download_time"] == 60.0
        assert event.data["average_speed"] == 1000.0

    def test_performance_metric_event_post_init(self):
        """Test PerformanceMetricEvent.__post_init__() (lines 344-354)."""
        event = PerformanceMetricEvent(
            metric_name="download_rate",
            metric_value=1024.0,
            metric_unit="bytes/s",
            tags={"host": "localhost"},
        )
        
        assert event.event_type == EventType.PERFORMANCE_METRIC.value
        assert event.data["metric_name"] == "download_rate"
        assert event.data["metric_value"] == 1024.0
        assert event.data["metric_unit"] == "bytes/s"
        assert event.data["tags"] == {"host": "localhost"}


class TestEventHandler:
    """Test EventHandler base class."""

    def test_event_handler_init(self):
        """Test EventHandler.__init__() - verify logger creation (lines 360-363)."""
        # Create concrete implementation for testing
        class TestHandler(EventHandler):
            async def handle(self, event):
                pass
        
        handler = TestHandler("test_handler")
        
        assert handler.name == "test_handler"
        assert handler.logger is not None

    def test_event_handler_can_handle_default(self):
        """Test EventHandler.can_handle() - default True (lines 369-371)."""
        class TestHandler(EventHandler):
            async def handle(self, event):
                pass
        
        handler = TestHandler("test_handler")
        event = Event(event_type="test")
        
        result = handler.can_handle(event)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_event_handler_handle_abstract(self):
        """Test EventHandler.handle() - abstract method must be implemented."""
        # EventHandler is abstract - verify by checking ABC registration
        from abc import ABC
        
        assert issubclass(EventHandler, ABC)
        assert hasattr(EventHandler.handle, '__isabstractmethod__')
        
        # Create a concrete implementation to verify it works
        class TestHandler(EventHandler):
            async def handle(self, event):
                return "handled"
        
        handler = TestHandler("test")
        result = await handler.handle(Event(event_type="test"))
        assert result == "handled"


class TestEventBus:
    """Test EventBus class."""

    @pytest.fixture
    def event_bus(self):
        """Create EventBus instance."""
        return EventBus(max_queue_size=100)

    def test_event_bus_init(self):
        """Test EventBus.__init__() - verify initialization (lines 377-399)."""
        bus = EventBus(max_queue_size=50)
        
        assert bus.max_queue_size == 50
        assert bus.handlers == {}
        assert bus.replay_buffer == []
        assert bus.max_replay_events == 1000
        assert bus.running is False
        assert bus.stats["events_processed"] == 0
        assert bus.stats["events_dropped"] == 0
        assert bus.stats["handlers_registered"] == 0
        assert bus.stats["queue_size"] == 0

    def test_register_handler_specific_event_type(self):
        """Test EventBus.register_handler() - register for specific event type (lines 401-417)."""
        bus = EventBus()
        handler = MagicMock(spec=EventHandler)
        handler.name = "test_handler"
        
        bus.register_handler("test_event", handler)
        
        assert "test_event" in bus.handlers
        assert handler in bus.handlers["test_event"]
        assert bus.stats["handlers_registered"] == 1

    def test_register_handler_multiple_handlers(self):
        """Test EventBus.register_handler() - multiple handlers for same type."""
        bus = EventBus()
        handler1 = MagicMock(spec=EventHandler)
        handler1.name = "handler1"
        handler2 = MagicMock(spec=EventHandler)
        handler2.name = "handler2"
        
        bus.register_handler("test_event", handler1)
        bus.register_handler("test_event", handler2)
        
        assert len(bus.handlers["test_event"]) == 2
        assert bus.stats["handlers_registered"] == 2

    def test_unregister_handler(self):
        """Test EventBus.unregister_handler() - remove handler (lines 419-435)."""
        bus = EventBus()
        handler = MagicMock(spec=EventHandler)
        handler.name = "test_handler"
        
        bus.register_handler("test_event", handler)
        bus.unregister_handler("test_event", handler)
        
        assert handler not in bus.handlers.get("test_event", [])

    def test_unregister_handler_not_found(self):
        """Test EventBus.unregister_handler() - remove non-existent handler (ValueError path, line 434)."""
        bus = EventBus()
        handler = MagicMock(spec=EventHandler)
        handler.name = "test_handler"
        
        # Should not raise, just pass silently
        bus.unregister_handler("test_event", handler)

    @pytest.mark.asyncio
    async def test_emit_normal_emission(self, event_bus):
        """Test EventBus.emit() - normal emission (lines 437-482)."""
        await event_bus.start()
        event = Event(event_type="test_event")
        
        await event_bus.emit(event)
        
        # Event should be in replay buffer
        assert event in event_bus.replay_buffer
        # Event should be in queue
        assert event_bus.event_queue.qsize() > 0
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_emit_queue_full(self, event_bus):
        """Test EventBus.emit() - queue full path (drop event, lines 450-456)."""
        # Create bus with very small queue
        bus = EventBus(max_queue_size=1)
        await bus.stop()  # Don't start processing
        
        # Fill queue completely (without processing)
        event1 = Event(event_type="event1")
        await bus.event_queue.put(event1)
        
        # Now queue is full - emit another should be dropped
        initial_dropped = bus.stats["events_dropped"]
        event2 = Event(event_type="event2")
        await bus.emit(event2)
        
        # Event should be in replay buffer even if dropped
        assert event2 in bus.replay_buffer
        assert bus.stats["events_dropped"] == initial_dropped + 1
        
        await bus.stop()

    @pytest.mark.asyncio
    async def test_emit_exception_handling(self, event_bus):
        """Test EventBus.emit() - exception handling path (lines 484-485)."""
        await event_bus.start()
        
        # Mock event_queue.put to raise exception
        with patch.object(event_bus.event_queue, "put", side_effect=Exception("Test error")):
            event = Event(event_type="test_event")
            # Should not raise, just log exception
            await event_bus.emit(event)
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_emit_loop_rebinding(self, event_bus):
        """Test EventBus.emit() - loop rebinding when loop changes (lines 458-480)."""
        await event_bus.start()
        original_loop = event_bus._loop
        
        # Simulate loop change by manually setting _loop to None first
        event_bus._loop = None
        
        event = Event(event_type="test_event")
        await event_bus.emit(event)
        
        # Should handle loop initialization and rebinding
        assert event in event_bus.replay_buffer
        assert event_bus._loop is not None
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, event_bus):
        """Test EventBus.start() - already running path (lines 487-490)."""
        await event_bus.start()
        assert event_bus.running is True
        
        # Start again should be no-op
        await event_bus.start()
        assert event_bus.running is True
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_start_loop_rebinding(self, event_bus):
        """Test EventBus.start() - loop rebinding on start (lines 492-512)."""
        # Start in current loop
        await event_bus.start()
        original_loop = event_bus._loop
        
        await event_bus.stop()
        
        # Simulate different loop scenario by setting _loop to None
        event_bus._loop = None
        event_bus.event_queue = None  # Clear queue
        
        # Start again - should rebind to current loop
        await event_bus.start()
        
        # Should have a loop assigned (lines 495-496)
        assert event_bus._loop is not None
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, event_bus):
        """Test EventBus.stop() - not running path (lines 514-517)."""
        # Stop when not running should be no-op
        await event_bus.stop()
        assert event_bus.running is False

    @pytest.mark.asyncio
    async def test_stop_task_cancellation(self, event_bus):
        """Test EventBus.stop() - task cancellation handling (lines 514-527)."""
        await event_bus.start()
        
        task = event_bus._task
        assert task is not None
        
        await event_bus.stop()
        
        # Task should be cancelled or done
        assert task.cancelled() or task.done()
        assert event_bus._task is None

    @pytest.mark.asyncio
    async def test_process_events_normal(self, event_bus):
        """Test EventBus._process_events() - normal processing (lines 529-544)."""
        handler = MagicMock(spec=EventHandler)
        handler.name = "test_handler"
        handler.can_handle = MagicMock(return_value=True)
        handler.handle = AsyncMock()
        
        await event_bus.start()
        event_bus.register_handler("test_event", handler)
        
        event = Event(event_type="test_event")
        await event_bus.emit(event)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Handler should have been called
        handler.handle.assert_called()
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_process_events_timeout(self, event_bus):
        """Test EventBus._process_events() - TimeoutError handling (lines 538-539)."""
        await event_bus.start()
        
        # The timeout occurs when queue is empty (wait_for with timeout=1.0)
        # Process will catch TimeoutError and continue (line 539)
        await asyncio.sleep(1.2)  # Wait longer than timeout
        
        # Should still be running (continues loop after timeout)
        assert event_bus.running
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_process_events_cancelled(self, event_bus):
        """Test EventBus._process_events() - CancelledError handling (lines 540-541)."""
        await event_bus.start()
        
        # Cancel the processing task
        if event_bus._task:
            event_bus._task.cancel()
            await asyncio.sleep(0.05)
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_process_events_exception(self, event_bus):
        """Test EventBus._process_events() - exception in processing (lines 542-543)."""
        await event_bus.start()
        
        # Mock queue.get to raise exception first time, then normal
        original_get = event_bus.event_queue.get
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Test exception")
            return await original_get(*args, **kwargs)
        
        event_bus.event_queue.get = mock_get
        
        # Emit event to trigger processing
        event = Event(event_type="test_event")
        await event_bus.emit(event)
        
        await asyncio.sleep(0.1)
        
        # Should handle exception and continue
        assert event_bus.running
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_handle_event_with_handlers(self, event_bus):
        """Test EventBus._handle_event() - event with handlers (lines 545-580)."""
        handler = MagicMock(spec=EventHandler)
        handler.name = "test_handler"
        handler.can_handle = MagicMock(return_value=True)
        handler.handle = AsyncMock()
        
        await event_bus.start()
        event_bus.register_handler("test_event", handler)
        
        event = Event(event_type="test_event")
        await event_bus._handle_event(event)
        
        handler.handle.assert_called_once_with(event)
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_handle_event_no_handlers(self, event_bus):
        """Test EventBus._handle_event() - event with no handlers (lines 560-565)."""
        await event_bus.start()
        
        event = Event(event_type="unknown_event")
        # Should not raise, just log debug
        await event_bus._handle_event(event)
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_handle_event_wildcard_handlers(self, event_bus):
        """Test EventBus._handle_event() - wildcard handlers (lines 556-558)."""
        handler = MagicMock(spec=EventHandler)
        handler.name = "wildcard_handler"
        handler.can_handle = MagicMock(return_value=True)
        handler.handle = AsyncMock()
        
        await event_bus.start()
        event_bus.register_handler("*", handler)
        
        event = Event(event_type="test_event")
        await event_bus._handle_event(event)
        
        handler.handle.assert_called_once_with(event)
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_handle_event_can_handle_filtering(self, event_bus):
        """Test EventBus._handle_event() - handler can_handle() filtering (lines 569-574)."""
        handler1 = MagicMock(spec=EventHandler)
        handler1.name = "handler1"
        handler1.can_handle = MagicMock(return_value=True)
        handler1.handle = AsyncMock()
        
        handler2 = MagicMock(spec=EventHandler)
        handler2.name = "handler2"
        handler2.can_handle = MagicMock(return_value=False)  # Won't handle
        handler2.handle = AsyncMock()
        
        await event_bus.start()
        event_bus.register_handler("test_event", handler1)
        event_bus.register_handler("test_event", handler2)
        
        event = Event(event_type="test_event")
        await event_bus._handle_event(event)
        
        handler1.handle.assert_called_once()
        handler2.handle.assert_not_called()
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_handle_event_exception(self, event_bus):
        """Test EventBus._handle_event() - exception handling (lines 579-580)."""
        await event_bus.start()
        
        # Create event that causes exception in LoggingContext or handler processing
        # Mock LoggingContext to raise exception
        with patch("ccbt.utils.events.LoggingContext", side_effect=Exception("Context error")):
            event = Event(event_type="test_event")
            # Should handle exceptions gracefully (lines 579-580)
            await event_bus._handle_event(event)
        
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_handle_with_handler_success(self, event_bus):
        """Test EventBus._handle_with_handler() - successful handling (lines 582-585)."""
        handler = MagicMock(spec=EventHandler)
        handler.name = "test_handler"
        handler.handle = AsyncMock()
        
        event = Event(event_type="test_event")
        await event_bus._handle_with_handler(event, handler)
        
        handler.handle.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_handle_with_handler_exception(self, event_bus):
        """Test EventBus._handle_with_handler() - handler exception (lines 586-591)."""
        handler = MagicMock(spec=EventHandler)
        handler.name = "test_handler"
        handler.handle = AsyncMock(side_effect=ValueError("Handler error"))
        
        event = Event(event_type="test_event")
        # Should not raise, just log exception
        await event_bus._handle_with_handler(event, handler)

    def test_get_replay_events_all(self, event_bus):
        """Test EventBus.get_replay_events() - all events (lines 593-612)."""
        events = [Event(event_type=f"event_{i}") for i in range(5)]
        event_bus.replay_buffer = events
        
        result = event_bus.get_replay_events()
        
        assert len(result) == 5
        assert result == events

    def test_get_replay_events_filtered(self, event_bus):
        """Test EventBus.get_replay_events() - filtered by event_type (lines 609-610)."""
        events = [
            Event(event_type="type1"),
            Event(event_type="type2"),
            Event(event_type="type1"),
        ]
        event_bus.replay_buffer = events
        
        result = event_bus.get_replay_events(event_type="type1")
        
        assert len(result) == 2
        assert all(e.event_type == "type1" for e in result)

    def test_get_replay_events_with_limit(self, event_bus):
        """Test EventBus.get_replay_events() - with limit (line 607)."""
        events = [Event(event_type=f"event_{i}") for i in range(10)]
        event_bus.replay_buffer = events
        
        result = event_bus.get_replay_events(limit=3)
        
        assert len(result) == 3
        # Should return last 3 events
        assert result == events[-3:]

    @pytest.mark.asyncio
    async def test_emit_replay_buffer_overflow(self, event_bus):
        """Test EventBus.emit() - replay buffer overflow (pop oldest, lines 445-447)."""
        await event_bus.start()
        event_bus.max_replay_events = 3
        
        # Emit more events than max_replay_events
        for i in range(5):
            event = Event(event_type=f"event_{i}")
            await event_bus.emit(event)
            await asyncio.sleep(0.01)  # Small delay to ensure processing
        
        # Buffer should be capped at max_replay_events
        assert len(event_bus.replay_buffer) == 3
        # Oldest events should be removed (event_0 and event_1)
        assert event_bus.replay_buffer[0].event_type in ["event_2", "event_3", "event_4"]
        
        await event_bus.stop()

    def test_get_stats(self, event_bus):
        """Test EventBus.get_stats() - verify all stats fields (lines 614-623)."""
        event_bus.stats["events_processed"] = 10
        event_bus.stats["events_dropped"] = 2
        event_bus.stats["handlers_registered"] = 5
        event_bus.replay_buffer = [Event(event_type="test")] * 3
        
        stats = event_bus.get_stats()
        
        assert stats["running"] is False
        assert stats["queue_size"] == 0
        assert stats["events_processed"] == 10
        assert stats["events_dropped"] == 2
        assert stats["handlers_registered"] == 5
        assert stats["replay_buffer_size"] == 3


class TestGlobalFunctions:
    """Test global event bus and convenience functions."""

    def test_get_event_bus_singleton(self):
        """Test get_event_bus() - singleton behavior (lines 630-635)."""
        # Reset global
        from ccbt.utils.events import _event_bus
        import ccbt.utils.events as events_module
        events_module._event_bus = None
        
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        
        assert bus1 is bus2
        assert isinstance(bus1, EventBus)

    @pytest.mark.asyncio
    async def test_emit_event(self):
        """Test emit_event() - emit to global bus (lines 638-641)."""
        bus = get_event_bus()
        await bus.start()
        
        handler = MagicMock(spec=EventHandler)
        handler.name = "test_handler"
        handler.can_handle = MagicMock(return_value=True)
        handler.handle = AsyncMock()
        
        bus.register_handler("test_event", handler)
        
        event = Event(event_type="test_event")
        await emit_event(event)
        
        await asyncio.sleep(0.1)
        
        handler.handle.assert_called()
        
        await bus.stop()

    @pytest.mark.asyncio
    async def test_emit_peer_connected(self):
        """Test emit_peer_connected() - convenience function (lines 644-656)."""
        bus = get_event_bus()
        await bus.start()
        
        received_events = []
        
        class TestHandler(EventHandler):
            def __init__(self):
                super().__init__("test_handler")
            
            async def handle(self, event):
                received_events.append(event)
        
        handler = TestHandler()
        bus.register_handler(EventType.PEER_CONNECTED.value, handler)
        
        await emit_peer_connected("192.168.1.1", 6881, "peer-id-123")
        
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].data["peer_ip"] == "192.168.1.1"
        assert received_events[0].data["peer_port"] == 6881
        assert received_events[0].data["peer_id"] == "peer-id-123"
        
        await bus.stop()

    @pytest.mark.asyncio
    async def test_emit_peer_disconnected(self):
        """Test emit_peer_disconnected() - convenience function (lines 659-671)."""
        bus = get_event_bus()
        await bus.start()
        
        received_events = []
        
        class TestHandler(EventHandler):
            def __init__(self):
                super().__init__("test_handler")
            
            async def handle(self, event):
                received_events.append(event)
        
        handler = TestHandler()
        bus.register_handler(EventType.PEER_DISCONNECTED.value, handler)
        
        await emit_peer_disconnected("192.168.1.1", 6881, "Connection timeout")
        
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].data["reason"] == "Connection timeout"
        
        await bus.stop()

    @pytest.mark.asyncio
    async def test_emit_piece_downloaded(self):
        """Test emit_piece_downloaded() - convenience function (lines 674-688)."""
        bus = get_event_bus()
        await bus.start()
        
        received_events = []
        
        class TestHandler(EventHandler):
            def __init__(self):
                super().__init__("test_handler")
            
            async def handle(self, event):
                received_events.append(event)
        
        handler = TestHandler()
        bus.register_handler(EventType.PIECE_DOWNLOADED.value, handler)
        
        await emit_piece_downloaded(5, 16384, 1.5, "192.168.1.1")
        
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].data["piece_index"] == 5
        
        await bus.stop()

    @pytest.mark.asyncio
    async def test_emit_torrent_completed(self):
        """Test emit_torrent_completed() - convenience function (lines 691-705)."""
        bus = get_event_bus()
        await bus.start()
        
        received_events = []
        
        class TestHandler(EventHandler):
            def __init__(self):
                super().__init__("test_handler")
            
            async def handle(self, event):
                received_events.append(event)
        
        handler = TestHandler()
        bus.register_handler(EventType.TORRENT_COMPLETED.value, handler)
        
        await emit_torrent_completed("test.torrent", 1048576, 60.0, 1000.0)
        
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].data["torrent_name"] == "test.torrent"
        
        await bus.stop()

    @pytest.mark.asyncio
    async def test_emit_performance_metric(self):
        """Test emit_performance_metric() - convenience function (lines 708-722)."""
        bus = get_event_bus()
        await bus.start()
        
        received_events = []
        
        class TestHandler(EventHandler):
            def __init__(self):
                super().__init__("test_handler")
            
            async def handle(self, event):
                received_events.append(event)
        
        handler = TestHandler()
        bus.register_handler(EventType.PERFORMANCE_METRIC.value, handler)
        
        await emit_performance_metric("download_rate", 1024.0, "bytes/s", {"host": "localhost"})
        
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].data["metric_name"] == "download_rate"
        assert received_events[0].data["tags"] == {"host": "localhost"}
        
        await bus.stop()

