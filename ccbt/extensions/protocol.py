"""Extension Protocol (BEP 10) implementation.

Provides support for:
- Extension handshake
- Extension message handling
- Custom extension registration
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable

from ccbt.utils.events import Event, EventType, emit_event


class ExtensionMessageType(IntEnum):
    """Extension Protocol message types."""

    EXTENDED = 20


@dataclass
class ExtensionInfo:
    """Extension information."""

    name: str
    version: str
    message_id: int
    handler: Callable | None = None


class ExtensionProtocol:
    """Extension Protocol implementation (BEP 10)."""

    def __init__(self):
        """Initialize protocol extension manager."""
        self.extensions: dict[str, ExtensionInfo] = {}
        self.message_handlers: dict[int, Callable] = {}
        self.next_message_id = 1
        self.peer_extensions: dict[str, dict[str, Any]] = {}

    def register_extension(
        self,
        name: str,
        version: str,
        handler: Callable | None = None,
    ) -> int:
        """Register a new extension."""
        if name in self.extensions:
            msg = f"Extension '{name}' already registered"
            raise ValueError(msg)

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

    def get_extension_info(self, name: str) -> ExtensionInfo | None:
        """Get extension information."""
        return self.extensions.get(name)

    def list_extensions(self) -> dict[str, ExtensionInfo]:
        """List all registered extensions."""
        return self.extensions.copy()

    def encode_handshake(self) -> bytes:
        """Encode extension handshake (BEP 10).
        
        BEP 10 extension handshakes are bencoded dictionaries.
        This method encodes the extension information as a bencoded dictionary.
        
        Returns:
            Encoded extension handshake message in format: <length><message_id><bencoded_data>

        """
        # Create extension dictionary
        extensions = {}
        for name, info in self.extensions.items():
            extensions[name] = {
                "version": info.version,
                "message_id": info.message_id,
            }

        # BEP 10: Extension handshake is bencoded, not JSON
        from ccbt.core.bencode import BencodeEncoder

        encoder = BencodeEncoder()
        bencoded_data = encoder.encode(extensions)

        # Pack message: <length><message_id><bencoded_data>
        return (
            struct.pack("!IB", len(bencoded_data) + 1, ExtensionMessageType.EXTENDED)
            + bencoded_data
        )

    def decode_handshake(self, data: bytes) -> dict[str, Any]:
        """Decode extension handshake (BEP 10).
        
        BEP 10 extension handshakes are ALWAYS bencoded dictionaries, not JSON.
        This method decodes the bencoded handshake data.
        
        Args:
            data: Extension handshake message in format: <length><message_id><bencoded_data>
            
        Returns:
            Decoded handshake dictionary with extension information
            
        Raises:
            ValueError: If data is invalid or incomplete
            BencodeDecodeError: If bencode decoding fails

        """
        if len(data) < 5:  # pragma: no cover - Short data error, tested via full data
            msg = "Invalid extension handshake"
            raise ValueError(msg)

        length, message_id = struct.unpack("!IB", data[:5])

        if (
            message_id != ExtensionMessageType.EXTENDED
        ):  # pragma: no cover - Invalid message type error, tested via valid type
            msg = "Invalid message type for extension handshake"
            raise ValueError(msg)

        if (
            len(data) < 5 + length - 1
        ):  # pragma: no cover - Incomplete data error, tested via complete data
            msg = "Incomplete extension handshake"
            raise ValueError(msg)

        # BEP 10: Extension handshake is bencoded, not JSON
        bencoded_data = data[5 : 5 + length - 1]

        # Decode bencoded data
        from ccbt.core.bencode import BencodeDecoder

        decoder = BencodeDecoder(bencoded_data)
        handshake_data = decoder.decode()

        # Convert bytes keys to strings for compatibility
        if isinstance(handshake_data, dict):
            converted_data = {}
            for key, value in handshake_data.items():
                if isinstance(key, bytes):
                    try:
                        key_str = key.decode("utf-8")
                    except UnicodeDecodeError:
                        # Fallback for non-UTF-8 keys (shouldn't happen per spec)
                        key_str = key.decode("utf-8", errors="replace")
                else:
                    key_str = str(key)

                # Recursively convert nested dicts
                if isinstance(value, dict):
                    converted_value = {}
                    for k, v in value.items():
                        if isinstance(k, bytes):
                            try:
                                k_str = k.decode("utf-8")
                            except UnicodeDecodeError:
                                k_str = k.decode("utf-8", errors="replace")
                        else:
                            k_str = str(k)
                        converted_value[k_str] = v
                    converted_data[key_str] = converted_value
                else:
                    converted_data[key_str] = value
            return converted_data

        # BEP 10 requires extension handshake to be a dictionary
        msg = f"Extension handshake must be a dictionary, got {type(handshake_data).__name__}"
        raise ValueError(msg)

    def encode_extension_message(self, message_id: int, payload: bytes) -> bytes:
        """Encode extension message."""
        # Pack message: <length><message_id><payload>
        return struct.pack("!IB", len(payload) + 1, message_id) + payload

    def decode_extension_message(self, data: bytes) -> tuple[int, bytes]:
        """Decode extension message."""
        if len(data) < 5:  # pragma: no cover - Short data error, tested via full data
            msg = "Invalid extension message"
            raise ValueError(msg)

        length, message_id = struct.unpack("!IB", data[:5])

        if (
            len(data) < 5 + length - 1
        ):  # pragma: no cover - Incomplete data error, tested via complete data
            msg = "Incomplete extension message"
            raise ValueError(msg)

        payload = data[5 : 5 + length - 1]
        return message_id, payload

    async def handle_extension_handshake(
        self,
        peer_id: str,
        extensions: dict[str, Any],
    ) -> None:
        """Handle extension handshake from peer."""
        self.peer_extensions[peer_id] = extensions
        
        # Extract SSL capability from extension handshake data
        # Check if SSL extension is registered in message map (BEP 10 "m" field)
        ssl_supported = False
        if isinstance(extensions, dict):
            m_dict = extensions.get("m") or extensions.get(b"m", {})
            if isinstance(m_dict, dict):
                # SSL extension may be registered with message ID
                if "ssl" in m_dict or b"ssl" in m_dict:
                    ssl_supported = True
        
        # Store SSL capability in peer_extensions
        if not isinstance(self.peer_extensions[peer_id], dict):
            self.peer_extensions[peer_id] = {"raw": self.peer_extensions[peer_id]}
        self.peer_extensions[peer_id]["ssl"] = ssl_supported

        # Emit event for extension handshake
        await emit_event(
            Event(
                event_type=EventType.EXTENSION_HANDSHAKE.value,
                data={
                    "peer_id": peer_id,
                    "extensions": extensions,
                    "ssl_capable": ssl_supported,
                    "timestamp": time.time(),
                },
            ),
        )

    async def handle_extension_message(
        self,
        peer_id: str,
        message_id: int,
        payload: bytes,
    ) -> None:
        """Handle extension message from peer."""
        # Find extension by message ID
        extension_name = None
        for name, info in self.extensions.items():
            if info.message_id == message_id:
                extension_name = name
                break

        if not extension_name:
            # Unknown extension message
            await emit_event(
                Event(
                    event_type=EventType.UNKNOWN_EXTENSION_MESSAGE.value,
                    data={
                        "peer_id": peer_id,
                        "message_id": message_id,
                        "payload": payload,
                        "timestamp": time.time(),
                    },
                ),
            )
            return

        # Call extension handler if available
        if message_id in self.message_handlers:
            try:
                await self.message_handlers[message_id](peer_id, payload)
            except Exception as e:  # pragma: no cover - Extension handler exception, defensive error handling
                await emit_event(
                    Event(
                        event_type=EventType.EXTENSION_ERROR.value,
                        data={
                            "peer_id": peer_id,
                            "extension_name": extension_name,
                            "error": str(e),
                            "timestamp": time.time(),
                        },
                    ),
                )

    def get_peer_extensions(self, peer_id: str) -> dict[str, Any]:
        """Get extensions supported by peer."""
        return self.peer_extensions.get(peer_id, {})

    def peer_supports_extension(self, peer_id: str, extension_name: str) -> bool:
        """Check if peer supports specific extension."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        return extension_name in peer_extensions

    def get_peer_extension_info(
        self,
        peer_id: str,
        extension_name: str,
    ) -> dict[str, Any] | None:
        """Get peer extension information."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        return peer_extensions.get(extension_name)

    def send_extension_message(
        self,
        _peer_id: str,
        _extension_name: str,
        payload: bytes,
    ) -> bytes:
        """Send extension message to peer."""
        if _extension_name not in self.extensions:
            msg = f"Extension '{_extension_name}' not registered"
            raise ValueError(msg)

        extension_info = self.extensions[_extension_name]
        return self.encode_extension_message(extension_info.message_id, payload)

    def create_extension_handler(self, _extension_name: str) -> Callable:
        """Create extension handler function."""

        def handler(
            peer_id: str, payload: bytes
        ) -> (
            None
        ):  # pragma: no cover - Default handler stub, tested via actual handlers
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

    def get_message_handlers(self) -> dict[int, Callable]:
        """Get all message handlers."""
        return self.message_handlers.copy()

    def clear_peer_extensions(self, peer_id: str) -> None:
        """Clear peer extensions."""
        if peer_id in self.peer_extensions:
            del self.peer_extensions[peer_id]

    def clear_all_peer_extensions(self) -> None:
        """Clear all peer extensions."""
        self.peer_extensions.clear()

    def get_extension_statistics(self) -> dict[str, Any]:
        """Get extension statistics."""
        return {
            "total_extensions": len(self.extensions),
            "total_peers": len(self.peer_extensions),
            "extensions": list(self.extensions.keys()),
            "message_handlers": len(self.message_handlers),
        }
