"""Extension Protocol (BEP 10) implementation.

Provides support for:
- Extension handshake
- Extension message handling
- Custom extension registration
"""

from __future__ import annotations

import struct
import time
import warnings
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Optional

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
    handler: Optional[Callable] = None


class ExtensionProtocol:
    """Extension Protocol implementation (BEP 10)."""

    def __init__(self):
        """Initialize protocol extension manager."""
        self.extensions: dict[str, ExtensionInfo] = {}
        self.message_handlers: dict[int, Callable] = {}
        self.next_message_id = 1
        self.peer_extensions: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _normalize_key(key: Any) -> str:
        """Normalize bencoded keys to text for internal lookups."""
        if isinstance(key, bytes):
            try:
                return key.decode("utf-8")
            except UnicodeDecodeError:
                return key.decode("utf-8", errors="replace")
        return str(key)

    @classmethod
    def _normalize_extension_dict(cls, data: dict[Any, Any]) -> dict[str, Any]:
        """Normalize a BEP 10 handshake dictionary for internal use."""
        normalized: dict[str, Any] = {}
        for key, value in data.items():
            key_str = cls._normalize_key(key)
            if isinstance(value, dict):
                normalized[key_str] = {
                    cls._normalize_key(nested_key): nested_value
                    for nested_key, nested_value in value.items()
                }
            else:
                normalized[key_str] = value
        return normalized

    @staticmethod
    def _normalize_encryption_preference(value: Any) -> Any:
        """Normalize top-level extended-handshake encryption preference."""
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.decode("utf-8", errors="replace")
        return value

    @staticmethod
    def _coerce_message_id(value: Any) -> Optional[int]:
        """Convert peer-advertised extension IDs to integers when possible."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, bytes):
            try:
                return int(value.decode("ascii"))
            except (UnicodeDecodeError, ValueError):
                return None
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def _build_peer_extension_state(self, extensions: dict[str, Any]) -> dict[str, Any]:
        """Create a canonical peer capability record from a handshake dictionary."""
        state = dict(extensions)
        message_map_raw = state.get("m", {})
        message_map: dict[str, int] = {}
        if isinstance(message_map_raw, dict):
            for name, message_id in message_map_raw.items():
                normalized_name = self._normalize_key(name)
                normalized_id = self._coerce_message_id(message_id)
                if normalized_id is not None:
                    message_map[normalized_name] = normalized_id
        state["m"] = message_map
        state["message_map"] = message_map
        state["reverse_message_map"] = {
            message_id: name for name, message_id in message_map.items()
        }
        if "e" in state:
            state["e"] = self._normalize_encryption_preference(state["e"])
        return state

    def register_extension(
        self,
        name: str,
        version: str,
        handler: Optional[Callable] = None,
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

    def get_extension_info(self, name: str) -> Optional[ExtensionInfo]:
        """Get extension information."""
        return self.extensions.get(name)

    def list_extensions(self) -> dict[str, ExtensionInfo]:
        """List all registered extensions."""
        return self.extensions.copy()

    def get_local_message_map(self) -> dict[str, int]:
        """Return the local BEP 10 message map."""
        return {
            name: info.message_id
            for name, info in self.extensions.items()
            if info.message_id > 0
        }

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
        normalized_extensions = self._normalize_extension_dict(extensions)
        self.peer_extensions[peer_id] = self._build_peer_extension_state(
            normalized_extensions
        )

        # Extract SSL capability from extension handshake data
        # Check if SSL extension is registered in message map (BEP 10 "m" field)
        # Note: BEP 10 extensions can have bytes keys, but type annotation is dict[str, Any]
        ssl_supported = False
        if isinstance(self.peer_extensions[peer_id], dict):
            m_dict = self.peer_extensions[peer_id].get("m", {})
            # SSL extension may be registered with message ID
            if isinstance(m_dict, dict) and "ssl" in m_dict:
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
                    "extensions": self.peer_extensions[peer_id],
                    "ssl_capable": ssl_supported,
                    "encryption_preference": self.peer_extensions[peer_id].get("e"),
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

    def get_peer_encryption_preference(self, peer_id: str) -> Optional[Any]:
        """Get peer encryption preference from extended-handshake `e`."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        if not isinstance(peer_extensions, dict):
            return None
        return peer_extensions.get("e")

    def peer_supports_extension(self, peer_id: str, extension_name: str) -> bool:
        """Check if peer supports specific extension."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        if not isinstance(peer_extensions, dict):
            return False
        if extension_name == "ssl":
            return peer_extensions.get("ssl") is True
        message_map = peer_extensions.get("message_map")
        if isinstance(message_map, dict):
            return extension_name in message_map
        return extension_name in peer_extensions

    def get_peer_message_id(self, peer_id: str, extension_name: str) -> Optional[int]:
        """Return the peer-advertised message ID for an extension."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        if not isinstance(peer_extensions, dict):
            return None
        message_map = peer_extensions.get("message_map")
        if not isinstance(message_map, dict):
            return None
        message_id = message_map.get(extension_name)
        return message_id if isinstance(message_id, int) else None

    def get_peer_extension_name(self, peer_id: str, message_id: int) -> Optional[str]:
        """Return the peer extension name for a message ID."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        if not isinstance(peer_extensions, dict):
            return None
        reverse_map = peer_extensions.get("reverse_message_map")
        if not isinstance(reverse_map, dict):
            return None
        extension_name = reverse_map.get(message_id)
        return extension_name if isinstance(extension_name, str) else None

    def get_peer_extension_info(
        self,
        peer_id: str,
        extension_name: str,
    ) -> Optional[dict[str, Any]]:
        """Get peer extension information."""
        peer_extensions = self.peer_extensions.get(peer_id, {})
        if not isinstance(peer_extensions, dict):
            return None
        message_id = self.get_peer_message_id(peer_id, extension_name)
        if message_id is None:
            return None
        return {"name": extension_name, "message_id": message_id}

    def send_extension_message(
        self,
        extension_name: str,
        payload: bytes,
        peer_id: Optional[str] = None,
        local_fallback: bool = False,
    ) -> bytes:
        """Build a peer extension message payload with peer-aware routing IDs.

        This method is now peer-aware and prefers the peer-advertised extension ID
        for the provided peer. If ``peer_id`` is omitted, it falls back to the
        local extension ID to preserve compatibility for code paths that are not
        peer-specific.

        If ``peer_id`` is provided and ``local_fallback`` is False, this method
        requires a peer-advertised ID and raises when the peer has not advertised
        the extension. Set ``local_fallback`` to True only when you explicitly want
        that behavior.

        Args:
            extension_name: Extension name to send.
            payload: Payload bytes to send.
            peer_id: Peer identifier (for peer-specific extension ID lookup).
            local_fallback: If True, use local extension ID when peer mapping is absent.

        Returns:
            Encoded extension message bytes.

        """
        if extension_name not in self.extensions:
            msg = f"Extension '{extension_name}' not registered"
            raise ValueError(msg)

        extension_info = self.extensions[extension_name]
        if peer_id is None:
            warnings.warn(
                "send_extension_message is deprecated for direct local-only usage. "
                "Pass peer_id to safely use the peer-advertised extension ID.",
                DeprecationWarning,
                stacklevel=2,
            )
        outgoing_message_id: Optional[int]
        if peer_id is None:
            outgoing_message_id = extension_info.message_id
        else:
            outgoing_message_id = self.get_peer_message_id(peer_id, extension_name)
            if outgoing_message_id is None and local_fallback:
                outgoing_message_id = extension_info.message_id
        if outgoing_message_id is None:
            msg = f"Extension '{extension_name}' has no id for peer '{peer_id}'"
            raise ValueError(msg)
        return self.encode_extension_message(outgoing_message_id, payload)

    def send_extension_message_for_peer(
        self,
        peer_id: str,
        extension_name: str,
        payload: bytes,
    ) -> bytes:
        """Build a peer extension message payload using the peer-advertised ID."""
        return self.send_extension_message(
            extension_name, payload, peer_id=peer_id, local_fallback=False
        )

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
