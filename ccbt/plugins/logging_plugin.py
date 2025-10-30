"""Logging plugin for ccBitTorrent.

from __future__ import annotations

Provides structured logging of events for debugging and monitoring.
"""

from __future__ import annotations

import json
from pathlib import Path

from ccbt.plugins.base import Plugin
from ccbt.utils.events import Event, EventHandler, EventType
from ccbt.utils.logging_config import get_logger


class EventLoggingHandler(EventHandler):
    """Handler for logging events."""

    def __init__(self, log_file: str | None = None):
        """Initialize event logging handler."""
        super().__init__("event_logging_handler")
        self.log_file = log_file
        self.logger = get_logger(__name__)
        self.event_count = 0

    async def handle(self, event: Event) -> None:
        """Log an event."""
        self.event_count += 1

        # Create log entry
        log_entry = {
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "event_id": event.event_id,
            "priority": event.priority.value,
            "source": event.source,
            "data": event.data,
            "correlation_id": event.correlation_id,
        }

        # Log to console
        self.logger.info("Event: %s - %s", event.event_type, json.dumps(event.data))

        # Log to file if specified
        if self.log_file:
            try:
                with open(self.log_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except Exception:
                self.logger.exception("Failed to write to log file")


class LoggingPlugin(Plugin):
    """Plugin for structured event logging."""

    def __init__(
        self,
        name: str = "logging_plugin",
        log_file: str | None = None,
        log_level: str = "INFO",
    ):
        """Initialize logging plugin."""
        super().__init__(
            name=name,
            version="1.0.0",
            description="Structured event logging plugin",
        )
        self.log_file = log_file
        self.log_level = log_level
        self.handler: EventLoggingHandler | None = None

    async def initialize(self) -> None:
        """Initialize the logging plugin."""
        self.logger.info("Initializing logging plugin")

        # Create log directory if needed
        if self.log_file:
            log_path = Path(self.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """Start the logging plugin."""
        self.logger.info("Starting logging plugin")

        # Create event handler
        self.handler = EventLoggingHandler(self.log_file)

        # Register for all events
        from ccbt.utils.events import get_event_bus

        event_bus = get_event_bus()

        # Register handler for all event types
        for event_type in EventType:
            event_bus.register_handler(event_type.value, self.handler)

        # Also register for wildcard events
        event_bus.register_handler("*", self.handler)

    async def stop(self) -> None:
        """Stop the logging plugin."""
        self.logger.info("Stopping logging plugin")

        if self.handler:
            from ccbt.utils.events import get_event_bus

            event_bus = get_event_bus()

            # Unregister handler
            for event_type in EventType:
                event_bus.unregister_handler(event_type.value, self.handler)
            event_bus.unregister_handler("*", self.handler)

    async def cleanup(self) -> None:
        """Cleanup logging plugin resources."""
        self.logger.info("Cleaning up logging plugin")
        self.handler = None
