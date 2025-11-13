"""Secure Messaging Protocol for Peer-to-Peer Communication.

from __future__ import annotations

Provides end-to-end encrypted messaging using Ed25519 for signing
and X25519 (derived from Ed25519) for encryption.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ccbt.utils.logging_config import get_logger

if TYPE_CHECKING:
    from ccbt.security.key_manager import Ed25519KeyManager

try:
    from cryptography.hazmat.primitives import hashes as crypto_hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    AESGCM = None  # type: ignore[assignment, misc]
    HKDF = None  # type: ignore[assignment, misc]
    crypto_hashes = None  # type: ignore[assignment, misc]
    Encoding = None  # type: ignore[assignment, misc]
    NoEncryption = None  # type: ignore[assignment, misc]
    PrivateFormat = None  # type: ignore[assignment, misc]

logger = get_logger(__name__)


class SecureMessageError(Exception):
    """Base exception for secure messaging errors."""


@dataclass
class SecureMessage:
    """Secure message with encryption and signature.

    Attributes:
        sender_public_key: Sender's Ed25519 public key (32 bytes)
        recipient_public_key: Recipient's Ed25519 public key (32 bytes)
        encrypted_payload: Encrypted message payload
        signature: Ed25519 signature of encrypted payload (64 bytes)
        timestamp: Message timestamp
        nonce: AES-GCM nonce (12 bytes)

    """

    sender_public_key: bytes
    recipient_public_key: bytes
    encrypted_payload: bytes
    signature: bytes
    timestamp: float
    nonce: bytes

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary for serialization.

        Returns:
            Dictionary representation

        """
        return {
            "sender_public_key": self.sender_public_key.hex(),
            "recipient_public_key": self.recipient_public_key.hex(),
            "encrypted_payload": self.encrypted_payload.hex(),
            "signature": self.signature.hex(),
            "timestamp": self.timestamp,
            "nonce": self.nonce.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecureMessage:
        """Create message from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            SecureMessage instance

        """
        return cls(
            sender_public_key=bytes.fromhex(data["sender_public_key"]),
            recipient_public_key=bytes.fromhex(data["recipient_public_key"]),
            encrypted_payload=bytes.fromhex(data["encrypted_payload"]),
            signature=bytes.fromhex(data["signature"]),
            timestamp=float(data["timestamp"]),
            nonce=bytes.fromhex(data["nonce"]),
        )


class SecureMessaging:
    """Secure messaging protocol using Ed25519 and X25519."""

    def __init__(self, key_manager: Ed25519KeyManager):
        """Initialize secure messaging.

        Args:
            key_manager: Ed25519KeyManager instance

        """
        if not CRYPTOGRAPHY_AVAILABLE:
            msg = "Cryptography library required for secure messaging"
            raise SecureMessageError(msg)

        self.key_manager = key_manager

    def _ed25519_to_x25519_private(self, ed25519_private: bytes) -> bytes:
        """Convert Ed25519 private key to X25519 private key.

        Args:
            ed25519_private: Ed25519 private key bytes (32 bytes)

        Returns:
            X25519 private key bytes (32 bytes)

        """
        # Use first 32 bytes of SHA-512 hash of Ed25519 private key
        # This is a simplified conversion - in production, use proper curve conversion
        hash_digest = hashlib.sha512(ed25519_private).digest()
        return hash_digest[:32]

    def _derive_shared_secret(
        self, our_private_key: bytes, peer_public_key: bytes
    ) -> bytes:
        """Derive shared secret using X25519-style key exchange.

        Args:
            our_private_key: Our X25519 private key (32 bytes)
            peer_public_key: Peer's X25519 public key (32 bytes)

        Returns:
            Shared secret (32 bytes)

        """
        # Simplified key derivation using HKDF
        # In production, use proper X25519 key exchange
        combined = our_private_key + peer_public_key
        hkdf = HKDF(
            algorithm=crypto_hashes.SHA256(),
            length=32,
            salt=None,
            info=b"ccbt-secure-messaging",
        )
        return hkdf.derive(combined)

    def encrypt_message(
        self, message: bytes, recipient_public_key: bytes
    ) -> SecureMessage:
        """Encrypt and sign a message.

        Args:
            message: Plaintext message bytes
            recipient_public_key: Recipient's Ed25519 public key (32 bytes)

        Returns:
            Encrypted and signed SecureMessage

        Raises:
            SecureMessageError: If encryption fails

        """
        try:
            # Get our private key using get_private_key_bytes() method
            # This method encapsulates key extraction logic
            our_private_key_bytes = self.key_manager.get_private_key_bytes()
            # For encryption, we need to derive X25519 keys
            # Simplified: use Ed25519 keys directly with HKDF
            our_x25519_private = self._ed25519_to_x25519_private(our_private_key_bytes)

            # Derive shared secret
            shared_secret = self._derive_shared_secret(
                our_x25519_private, recipient_public_key
            )

            # Generate nonce
            nonce = secrets.token_bytes(12)

            # Encrypt with AES-256-GCM
            aesgcm = AESGCM(shared_secret)
            encrypted_payload = aesgcm.encrypt(nonce, message, None)

            # Sign encrypted payload with Ed25519
            signature = self.key_manager.sign_message(encrypted_payload)

            # Get our public key
            our_public_key = self.key_manager.get_public_key_bytes()

            return SecureMessage(
                sender_public_key=our_public_key,
                recipient_public_key=recipient_public_key,
                encrypted_payload=encrypted_payload,
                signature=signature,
                timestamp=time.time(),
                nonce=nonce,
            )
        except Exception as e:
            msg = f"Failed to encrypt message: {e}"
            logger.exception(msg)
            raise SecureMessageError(msg) from e

    def decrypt_message(
        self, secure_message: SecureMessage, sender_public_key: bytes | None = None
    ) -> bytes:
        """Decrypt and verify a message.

        Args:
            secure_message: Encrypted SecureMessage
            sender_public_key: Optional sender public key for verification
                (uses message's sender_public_key if None)

        Returns:
            Decrypted plaintext message

        Raises:
            SecureMessageError: If decryption or verification fails

        """
        try:
            # Verify signature
            sender_key = (
                sender_public_key
                if sender_public_key is not None
                else secure_message.sender_public_key
            )

            if not self.key_manager.verify_signature(
                secure_message.encrypted_payload,
                secure_message.signature,
                sender_key,
            ):
                msg = "Invalid message signature"
                raise SecureMessageError(msg)

            # Get our private key
            private_key, _ = self.key_manager.get_or_create_keypair()
            our_private_key_bytes = private_key.private_bytes(
                encoding=Encoding.Raw,
                format=PrivateFormat.Raw,
                encryption_algorithm=NoEncryption(),
            )
            our_x25519_private = self._ed25519_to_x25519_private(our_private_key_bytes)

            # Derive shared secret
            shared_secret = self._derive_shared_secret(
                our_x25519_private, secure_message.sender_public_key
            )

            # Decrypt with AES-256-GCM
            aesgcm = AESGCM(shared_secret)
            plaintext = aesgcm.decrypt(
                secure_message.nonce,
                secure_message.encrypted_payload,
                None,
            )

            return plaintext
        except Exception as e:
            msg = f"Failed to decrypt message: {e}"
            logger.exception(msg)
            raise SecureMessageError(msg) from e
