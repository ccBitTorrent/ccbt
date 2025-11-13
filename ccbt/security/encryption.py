"""Encryption Manager for ccBitTorrent.

from __future__ import annotations

Provides encryption support including:
- MSE/PE encryption (BEP 3)
- Protocol encryption
- Key exchange
- Encrypted handshake
- Cipher suites: RC4, AES, ChaCha20
"""

from __future__ import annotations

import secrets
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ccbt.utils.events import Event, EventType, emit_event


class EncryptionType(Enum):
    """Types of encryption."""

    NONE = "none"
    RC4 = "rc4"
    AES = "aes"
    CHACHA20 = "chacha20"


class EncryptionMode(Enum):
    """Encryption modes."""

    DISABLED = "disabled"
    PREFERRED = "preferred"
    REQUIRED = "required"


@dataclass
class EncryptionConfig:
    """Encryption configuration.

    This is a legacy configuration class. For new code, use SecurityConfig from
    ccbt.models.SecurityConfig instead.
    """

    mode: EncryptionMode = EncryptionMode.PREFERRED
    allowed_ciphers: list[EncryptionType] = field(default_factory=list)
    key_size: int = 16  # 128-bit keys
    handshake_timeout: float = 10.0

    def __post_init__(self):
        """Initialize allowed ciphers after object creation."""
        if not self.allowed_ciphers:
            self.allowed_ciphers = [EncryptionType.RC4, EncryptionType.AES]

    @classmethod
    def from_security_config(cls, security_config: Any) -> EncryptionConfig:
        """Create EncryptionConfig from SecurityConfig.

        Args:
            security_config: SecurityConfig instance from ccbt.models

        Returns:
            EncryptionConfig instance

        """
        from ccbt.config.config import get_config

        # Try to get from security_config if provided, else get from global config
        if security_config is None:
            config = get_config()
            security_config = config.security

        # Map encryption_mode string to EncryptionMode enum
        encryption_mode_str = getattr(security_config, "encryption_mode", "preferred")
        mode_map = {
            "disabled": EncryptionMode.DISABLED,
            "preferred": EncryptionMode.PREFERRED,
            "required": EncryptionMode.REQUIRED,
        }
        mode = mode_map.get(encryption_mode_str.lower(), EncryptionMode.PREFERRED)

        # Map allowed_ciphers from string list to EncryptionType enum
        allowed_cipher_strings = getattr(
            security_config, "encryption_allowed_ciphers", ["rc4", "aes"]
        )
        allowed_ciphers = []
        cipher_map = {
            "rc4": EncryptionType.RC4,
            "aes": EncryptionType.AES,
            "chacha20": EncryptionType.CHACHA20,
        }
        for cipher_str in allowed_cipher_strings:
            cipher_type = cipher_map.get(cipher_str.lower())
            if cipher_type:
                allowed_ciphers.append(cipher_type)

        if not allowed_ciphers:
            allowed_ciphers = [EncryptionType.RC4, EncryptionType.AES]

        return cls(
            mode=mode,
            allowed_ciphers=allowed_ciphers,
            key_size=16,  # Default key size (SecurityConfig doesn't have this)
            handshake_timeout=10.0,  # Default timeout
        )


@dataclass
class EncryptionSession:
    """Encryption session information."""

    peer_id: str
    ip: str
    encryption_type: EncryptionType
    key: bytes
    handshake_complete: bool = False
    bytes_encrypted: int = 0
    bytes_decrypted: int = 0
    created_at: float = 0.0
    last_activity: float = 0.0
    # MSE handshake state (for integration with MSEHandshake)
    mse_handshake: Any = None  # Will store MSEHandshake instance if needed
    info_hash: bytes | None = None  # Torrent info hash for key derivation


class EncryptionManager:
    """Encryption management system."""

    def __init__(
        self,
        config: EncryptionConfig | None = None,
        security_config: Any = None,
    ):
        """Initialize encryption manager.

        Args:
            config: Legacy EncryptionConfig (deprecated, use security_config)
            security_config: SecurityConfig from ccbt.models (preferred)

        """
        # Support both legacy EncryptionConfig and new SecurityConfig
        if security_config is not None:
            # Convert SecurityConfig to EncryptionConfig
            self.config = EncryptionConfig.from_security_config(security_config)
        elif config is not None:
            self.config = config
        else:
            # Try to get from global config
            try:
                from ccbt.config.config import get_config

                global_config = get_config()
                self.config = EncryptionConfig.from_security_config(
                    global_config.security
                )
            except Exception:
                # Fallback to defaults
                self.config = EncryptionConfig()

        self.encryption_sessions: dict[str, EncryptionSession] = {}
        self.cipher_suites: dict[EncryptionType, Any] = {}

        # Initialize cipher suites
        self._initialize_cipher_suites()

        # Statistics
        self.stats = {
            "sessions_created": 0,
            "sessions_failed": 0,
            "bytes_encrypted": 0,
            "bytes_decrypted": 0,
            "handshake_failures": 0,
        }

    async def initiate_encryption(self, peer_id: str, ip: str) -> tuple[bool, bytes]:
        """Initiate encryption with a peer.

        Args:
            peer_id: Peer identifier
            ip: Peer IP address

        Returns:
            Tuple of (success, handshake_data)

        """
        try:
            # Create encryption session
            session = await self._create_encryption_session(peer_id, ip)

            # Generate handshake data
            handshake_data = await self._generate_handshake(session)

            # Store session
            self.encryption_sessions[peer_id] = session

            self.stats["sessions_created"] += 1

            # Emit encryption initiated event
            await emit_event(
                Event(
                    event_type=EventType.ENCRYPTION_INITIATED.value,
                    data={
                        "peer_id": peer_id,
                        "ip": ip,
                        "encryption_type": session.encryption_type.value,
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception as e:
            self.stats["sessions_failed"] += 1

            # Emit encryption error event
            await emit_event(
                Event(
                    event_type=EventType.ENCRYPTION_ERROR.value,
                    data={
                        "peer_id": peer_id,
                        "ip": ip,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return False, b""
        else:
            return True, handshake_data

    async def complete_handshake(self, peer_id: str, handshake_response: bytes) -> bool:
        """Complete encryption handshake.

        Args:
            peer_id: Peer identifier
            handshake_response: Handshake response from peer

        Returns:
            True if handshake successful

        """
        if peer_id not in self.encryption_sessions:
            return False

        try:
            session = self.encryption_sessions[peer_id]

            # Verify handshake response
            if await self._verify_handshake_response(session, handshake_response):
                session.handshake_complete = True
                session.last_activity = time.time()

                # Emit handshake completed event
                await emit_event(
                    Event(
                        event_type=EventType.ENCRYPTION_HANDSHAKE_COMPLETED.value,
                        data={
                            "peer_id": peer_id,
                            "encryption_type": session.encryption_type.value,
                            "timestamp": time.time(),
                        },
                    ),
                )
                return True
            # Verification failed
            return False

        except Exception as e:
            self.stats["handshake_failures"] += 1

            # Emit handshake error event
            await emit_event(
                Event(
                    event_type=EventType.ENCRYPTION_HANDSHAKE_FAILED.value,
                    data={
                        "peer_id": peer_id,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return False

    async def encrypt_data(self, peer_id: str, data: bytes) -> tuple[bool, bytes]:
        """Encrypt data for a peer.

        Args:
            peer_id: Peer identifier
            data: Data to encrypt

        Returns:
            Tuple of (success, encrypted_data)

        """
        if peer_id not in self.encryption_sessions:
            return False, data

        session = self.encryption_sessions[peer_id]

        if not session.handshake_complete:
            return False, data

        try:
            # Get cipher for this session
            cipher = self.cipher_suites.get(session.encryption_type)
            if not cipher:
                return False, data

            # Encrypt data
            encrypted_data = await self._encrypt_with_cipher(cipher, session.key, data)

            # Update statistics
            session.bytes_encrypted += len(encrypted_data)
            session.last_activity = time.time()
            self.stats["bytes_encrypted"] += len(encrypted_data)

        except Exception as e:
            # Emit encryption error event
            await emit_event(
                Event(
                    event_type=EventType.ENCRYPTION_ERROR.value,
                    data={
                        "peer_id": peer_id,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return False, data
        else:
            return True, encrypted_data

    async def decrypt_data(
        self,
        peer_id: str,
        encrypted_data: bytes,
    ) -> tuple[bool, bytes]:
        """Decrypt data from a peer.

        Args:
            peer_id: Peer identifier
            encrypted_data: Encrypted data to decrypt

        Returns:
            Tuple of (success, decrypted_data)

        """
        if peer_id not in self.encryption_sessions:
            return False, encrypted_data

        session = self.encryption_sessions[peer_id]

        if not session.handshake_complete:
            return False, encrypted_data

        try:
            # Get cipher for this session
            cipher = self.cipher_suites.get(session.encryption_type)
            if not cipher:
                return False, encrypted_data

            # Decrypt data
            decrypted_data = await self._decrypt_with_cipher(
                cipher,
                session.key,
                encrypted_data,
            )

            # Update statistics
            session.bytes_decrypted += len(decrypted_data)
            session.last_activity = time.time()
            self.stats["bytes_decrypted"] += len(decrypted_data)

        except Exception as e:
            # Emit decryption error event
            await emit_event(
                Event(
                    event_type=EventType.ENCRYPTION_ERROR.value,
                    data={
                        "peer_id": peer_id,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return False, encrypted_data
        else:
            return True, decrypted_data

    def is_peer_encrypted(self, peer_id: str) -> bool:
        """Check if peer has active encryption."""
        if peer_id not in self.encryption_sessions:
            return False

        session = self.encryption_sessions[peer_id]
        return session.handshake_complete

    def get_encryption_type(self, peer_id: str) -> EncryptionType | None:
        """Get encryption type for a peer."""
        if peer_id not in self.encryption_sessions:
            return None

        return self.encryption_sessions[peer_id].encryption_type

    def get_encryption_statistics(self) -> dict[str, Any]:
        """Get encryption statistics."""
        return {
            "sessions_created": self.stats["sessions_created"],
            "sessions_failed": self.stats["sessions_failed"],
            "bytes_encrypted": self.stats["bytes_encrypted"],
            "bytes_decrypted": self.stats["bytes_decrypted"],
            "handshake_failures": self.stats["handshake_failures"],
            "active_sessions": len(self.encryption_sessions),
            "encryption_rate": self.stats["bytes_encrypted"]
            / max(1, self.stats["bytes_encrypted"] + self.stats["bytes_decrypted"]),
        }

    def get_peer_encryption_info(self, peer_id: str) -> dict[str, Any] | None:
        """Get encryption information for a peer."""
        if peer_id not in self.encryption_sessions:
            return None

        session = self.encryption_sessions[peer_id]

        return {
            "encryption_type": session.encryption_type.value,
            "handshake_complete": session.handshake_complete,
            "bytes_encrypted": session.bytes_encrypted,
            "bytes_decrypted": session.bytes_decrypted,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
        }

    def cleanup_old_sessions(self, max_age_seconds: int = 3600) -> None:
        """Clean up old encryption sessions."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        to_remove = []
        for peer_id, session in self.encryption_sessions.items():
            if session.last_activity < cutoff_time:
                to_remove.append(peer_id)

        for peer_id in to_remove:
            del self.encryption_sessions[peer_id]

    def _initialize_cipher_suites(self) -> None:
        """Initialize cipher suites."""
        from ccbt.security.ciphers.aes import AESCipher
        from ccbt.security.ciphers.chacha20 import ChaCha20Cipher
        from ccbt.security.ciphers.rc4 import RC4Cipher

        # Register cipher classes (not instances)
        self.cipher_suites[EncryptionType.RC4] = RC4Cipher
        self.cipher_suites[EncryptionType.AES] = AESCipher
        self.cipher_suites[EncryptionType.CHACHA20] = ChaCha20Cipher

    async def _create_encryption_session(
        self,
        peer_id: str,
        ip: str,
    ) -> EncryptionSession:
        """Create a new encryption session."""
        # Select encryption type
        encryption_type = self._select_encryption_type()

        # Generate encryption key
        key = self._generate_encryption_key()

        return EncryptionSession(
            peer_id=peer_id,
            ip=ip,
            encryption_type=encryption_type,
            key=key,
            created_at=time.time(),
            last_activity=time.time(),
        )

    def _select_encryption_type(
        self, peer_capabilities: list[EncryptionType] | None = None
    ) -> EncryptionType:
        """Select encryption type based on configuration and peer capabilities.

        Args:
            peer_capabilities: List of encryption types supported by peer (None = unknown)

        Returns:
            Selected encryption type

        """
        # Priority order: Most secure first (ChaCha20, AES), then RC4 (for compatibility)
        preferred_order = [
            EncryptionType.CHACHA20,
            EncryptionType.AES,
            EncryptionType.RC4,
        ]

        # Filter by allowed ciphers from config
        if not self.config.allowed_ciphers:
            # Default to RC4 if no configuration
            return EncryptionType.RC4

        # Get intersection of allowed ciphers and preferred order
        available_ciphers = [
            cipher
            for cipher in preferred_order
            if cipher in self.config.allowed_ciphers
        ]

        if not available_ciphers:
            # Fallback to first allowed cipher if none in preferred order
            return self.config.allowed_ciphers[0]

        # If peer capabilities are known, prefer matching ciphers
        if peer_capabilities:
            matching_ciphers = [
                cipher for cipher in available_ciphers if cipher in peer_capabilities
            ]
            if matching_ciphers:
                # Return first matching cipher from preferred order
                return matching_ciphers[0]

        # Return first available cipher from preferred order
        return available_ciphers[0]

    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key."""
        return secrets.token_bytes(self.config.key_size)

    async def _generate_handshake(self, session: EncryptionSession) -> bytes:
        """Generate encryption handshake data.

        Note: This is a simplified placeholder method. The actual MSE handshake
        will be performed at the peer connection level using MSEHandshake directly
        with StreamReader/StreamWriter. This method is kept for backward compatibility
        with the EncryptionManager interface.

        Args:
            session: Encryption session

        Returns:
            Simplified handshake data (for compatibility only)

        """
        # Map EncryptionType to MSE CipherType
        from ccbt.security.mse_handshake import CipherType

        # Convert EncryptionType to CipherType for MSE protocol
        cipher_type_map = {
            EncryptionType.RC4: CipherType.RC4,
            EncryptionType.AES: CipherType.AES,
            EncryptionType.CHACHA20: CipherType.CHACHA20,
        }

        mse_cipher_type = cipher_type_map.get(session.encryption_type, CipherType.RC4)

        # Generate simplified handshake structure aligned with MSE protocol format
        # Format: [4 bytes length][1 byte message type][payload]
        # This is a placeholder - actual handshake uses MSEHandshake with streams

        # Protocol identifier for simplified handshake
        protocol_version = 1
        handshake_data = struct.pack(
            "!BB",  # Protocol version and encryption type
            protocol_version,
            int(mse_cipher_type),
        )

        # Add minimal key material placeholder
        # Note: In real MSE handshake, key is derived from DH exchange via MSEHandshake
        handshake_data += session.key[:16]  # Use first 16 bytes

        return handshake_data

    async def _verify_handshake_response(
        self,
        session: EncryptionSession,
        response: bytes,
    ) -> bool:
        """Verify handshake response from peer.

        Note: This is a simplified placeholder method. The actual MSE handshake
        verification will be performed at the peer connection level using MSEHandshake
        directly with StreamReader/StreamWriter. This method is kept for backward
        compatibility with the EncryptionManager interface.

        Args:
            session: Encryption session
            response: Handshake response bytes from peer

        Returns:
            True if handshake response is valid

        """
        from ccbt.security.mse_handshake import CipherType

        if len(response) < 2:
            return False

        try:
            # Check protocol version and encryption type
            version, cipher_type_value = struct.unpack("!BB", response[:2])

            if version != 1:
                return False

            # Map MSE CipherType to EncryptionType
            cipher_type_map = {
                CipherType.RC4: EncryptionType.RC4,
                CipherType.AES: EncryptionType.AES,
                CipherType.CHACHA20: EncryptionType.CHACHA20,
            }

            try:
                mse_cipher_type = CipherType(cipher_type_value)
                expected_encryption_type = cipher_type_map.get(
                    mse_cipher_type, EncryptionType.RC4
                )
                return expected_encryption_type == session.encryption_type
            except ValueError:
                # Invalid cipher type value
                return False

        except struct.error:  # pragma: no cover
            # Tested via test_verify_handshake_response_struct_error, but coverage
            # tool may not always track exception handler execution correctly
            return False
        except ValueError:  # pragma: no cover - defensive code for outer try block
            # Defensive: catch any other ValueError in outer try block
            # (inner ValueError from CipherType is already handled above)
            # This is unlikely to be reached in practice but protects against
            # unexpected ValueError from struct operations
            return False

    async def _encrypt_with_cipher(
        self, cipher_class: type, key: bytes, data: bytes
    ) -> bytes:
        """Encrypt data with specified cipher.

        Args:
            cipher_class: Cipher class to instantiate
            key: Encryption key
            data: Data to encrypt

        Returns:
            Encrypted data

        """
        try:
            # Instantiate cipher with key
            cipher = cipher_class(key)
            # Encrypt data
            return cipher.encrypt(data)
        except Exception as e:
            # Log error and return original data
            # In production, should emit error event
            error_msg = f"Encryption failed: {e}"
            raise RuntimeError(error_msg) from e

    async def _decrypt_with_cipher(
        self,
        cipher_class: type,
        key: bytes,
        encrypted_data: bytes,
    ) -> bytes:
        """Decrypt data with specified cipher.

        Args:
            cipher_class: Cipher class to instantiate
            key: Decryption key
            encrypted_data: Encrypted data to decrypt

        Returns:
            Decrypted plaintext data

        """
        try:
            # Instantiate cipher with key
            cipher = cipher_class(key)
            # Decrypt data
            return cipher.decrypt(encrypted_data)
        except Exception as e:
            # Log error and return encrypted data
            # In production, should emit error event
            error_msg = f"Decryption failed: {e}"
            raise RuntimeError(error_msg) from e
