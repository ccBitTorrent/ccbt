"""Extension Protocol (BEP 10) implementation.

Provides support for:
- Extension handshake
- Extension message handling
- Custom extension registration
"""

import json
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Dict, Optional, Tuple

from ..events import Event, EventType, emit_event


class ExtensionMessageType(IntEnum):
    """Extension Protocol message types."""
    EXTENDED = 20


@dataclass
class ExtensionInfo:
    """Extension information."""
    name: str
    version: str
    message_id: int
    handler: Optional[Callable] = None


class ExtensionProtocol:
    """Extension Protocol implementation (BEP 10)."""

    def __init__(self):
        self.extensions: Dict[str, ExtensionInfo] = {}
        self.message_handlers: Dict[int, Callable] = {}
        self.next_message_id = 1
        self.peer_extensions: Dict[str, Dict[str, Any]] = {}

    def register_extension(self, name: str, version: str, handler: Optional[Callable] = None) -> int:
        """Register a new extension."""
        if name in self.extensions:
            raise ValueError(f"Extension '{name}' already registered")

        message_id = self.next_message_id
        self.next_message_id += 1

        extension_info = ExtensionInfo(
            name=name,
            version=version,
            message_id=message_id,
            handler=handler,
        )

        self.extensions[name] = extension_info

        if handler:
            self.message_handlers[message_id] = handler

        return message_id

    def unregister_extension(self, name: str) -> None:
        """Unregister an extension."""
        if name not in self.extensions:
            return

        extension_info = self.extensions[name]
        if extension_info.message_id in self.message_handlers:
            del self.message_handlers[extension_info.message_id]

        del self.extensions[name]

    def get_extension_info(self, name: str) -> Optional[ExtensionInfo]:
        """Get extension information."""
        return self.extensions.get(name)

    def list_extensions(self) -> Dict[str, ExtensionInfo]:
        """List all registered extensions."""
        return self.extensions.copy()

    def encode_handshake(self) -> bytes:
        """Encode extension handshake."""
        # Create extension dictionary
        extensions = {}
        for name, info in self.extensions.items():
            extensions[name] = {
                "version": info.version,
                "message_id": info.message_id,
            }

        # Convert to JSON
        extensions_json = json.dumps(extensions).encode("utf-8")

        # Pack message: <length><message_id><extensions_json>
        message = struct.pack("!IB", len(extensions_json) + 1, ExtensionMessageType.EXTENDED) + extensions_json

        return message

    def decode_handshake(self, data: bytes) -> Dict[str, Any]:
        """Decode extension handshake."""
        if len(data) < 5:
            raise ValueError("Invalid extension handshake")

        length, message_id = struct.unpack("!IB", data[:5])

        if message_id != ExtensionMessageType.EXTENDED:
            raise ValueError("Invalid message type for extension handshake")

        if len(data) < 5 + length - 1:
            raise ValueError("Incomplete extension handshake")

        extensions_json = data[5:5 + length - 1].decode("utf-8")
        extensions = json.loads(extensions_json)

        return extensions

    def encode_extension_message(self, message_id: int, payload: bytes) -> bytes:
        """Encode extension message."""
        # Pack message: <length><message_id><payload>
        message = struct.pack("!IB", len(payload) + 1, message_id) + payload
        return message

    def decode_extension_message(self, data: bytes) -> Tuple[int, bytes]:
        """Decode extension message."""
        if len(data) < 5:
            raise ValueError("Invalid extension message")

        length, message_id = struct.unpack("!IB", data[:5])

        if len(data) < 5 + length - 1:
            raise ValueError("Incomplete extension message")

        payload = data[5:5 + length - 1]
        return message_id, payload

    async def handle_extension_handshake(self, peer_id: str, extensions: Dict[str, Any]) -> None:
        """Handle extension handshake from peer."""
        self.peer_extensions[peer_id] = extensions

        # Emit event for extension handshake
        await emit_event(Event(
            event_type=EventType.EXTENSION_HANDSHAKE.value,
            data={
                "peer_id": peer_id,
                "extensions": extensions,
                "timestamp": time.time(),
            },
        ))

    async def handle_extension_message(self, peer_id: str, message_id: int, payload: bytes) -> None:
        """Handle extension message from peer."""
        # Find extension by message ID
        extension_name = None
        for name, info in self.extensions.items():
            if info.message_id == message_id:
                extension_name = name
                break

        if not extension_name:
            # Unknown extension message
            await emit_event(Event(
                event_type=EventType.UNKNOWN_EXTENSION_MESSAGE.value,
                data={
                    "peer_id": peer_id,
                    "message_id": message_id,
                    "payload": payload,
                    "timestamp": time.time(),
                },
            ))
            return

        # Call extension handler if available
        if message_id in self.message_handlers:
            try:
                await self.message_handlers[message_id](peer_id, payload)
            except Exception as e:
                await emit_event(Event(
                    event_type=EventType.EXTENSION_ERROR.value,
                    data={
                        "peer_id": peer_id,
                        "extension_name": extension_name,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ))

    def get_peer_extensions(self, peer_id: str) -> Dict[str, Any]:
        """Get extensions supported by peer."""
        return self.peer_extensions.get(peer_id, {})

    def peer_supports_extension(self, peer_id: str, extension_name: str) -> bool:
        """Check if peer supports specific extension."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        return extension_name in peer_extensions

    def get_peer_extension_info(self, peer_id: str, extension_name: str) -> Optional[Dict[str, Any]]:
        """Get peer extension information."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        return peer_extensions.get(extension_name)

    def send_extension_message(self, peer_id: str, extension_name: str, payload: bytes) -> bytes:
        """Send extension message to peer."""
        if extension_name not in self.extensions:
            raise ValueError(f"Extension '{extension_name}' not registered")

        extension_info = self.extensions[extension_name]
        return self.encode_extension_message(extension_info.message_id, payload)

    def create_extension_handler(self, extension_name: str) -> Callable:
        """Create extension handler function."""
        def handler(peer_id: str, payload: bytes) -> None:
            # Default handler - can be overridden
            pass

        return handler

    def register_message_handler(self, message_id: int, handler: Callable) -> None:
        """Register message handler for specific message ID."""
        self.message_handlers[message_id] = handler

    def unregister_message_handler(self, message_id: int) -> None:
        """Unregister message handler."""
        if message_id in self.message_handlers:
            del self.message_handlers[message_id]

    def get_message_handlers(self) -> Dict[int, Callable]:
        """Get all message handlers."""
        return self.message_handlers.copy()

    def clear_peer_extensions(self, peer_id: str) -> None:
        """Clear peer extensions."""
        if peer_id in self.peer_extensions:
            del self.peer_extensions[peer_id]

    def clear_all_peer_extensions(self) -> None:
        """Clear all peer extensions."""
        self.peer_extensions.clear()

    def get_extension_statistics(self) -> Dict[str, Any]:
        """Get extension statistics."""
        return {
            "total_extensions": len(self.extensions),
            "total_peers": len(self.peer_extensions),
            "extensions": list(self.extensions.keys()),
            "message_handlers": len(self.message_handlers),
        }


# Import time module for timestamps
import time
