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
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    x25519 = None  # type: ignore[assignment, misc]
    AESGCM = None  # type: ignore[assignment, misc]
    HKDF = None  # type: ignore[assignment, misc]
    crypto_hashes = None  # type: ignore[assignment, misc]
    Encoding = None  # type: ignore[assignment, misc]
    NoEncryption = None  # type: ignore[assignment, misc]
    PrivateFormat = None  # type: ignore[assignment, misc]
    PublicFormat = None  # type: ignore[assignment, misc]

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
        # This follows RFC 8032 section 5.1.5 for Ed25519 to X25519 conversion
        hash_digest = hashlib.sha512(ed25519_private).digest()
        return hash_digest[:32]

    def _ed25519_to_x25519_public(self, ed25519_public: bytes) -> bytes:
        """Convert Ed25519 public key to X25519 public key (RFC 8032 Section 5.1.5).

        Args:
            ed25519_public: Ed25519 public key bytes (32 bytes)

        Returns:
            X25519 public key bytes (32 bytes)

        Note:
            This implements the proper RFC 8032 conversion algorithm:
            - Ed25519 uses Edwards curve form of Curve25519
            - X25519 uses Montgomery curve form of Curve25519
            - Conversion: u = (1+y)/(1-y) mod p where (x,y) is Edwards point, u is Montgomery coordinate
            - Ed25519 public key encodes y-coordinate with sign bit in the most significant bit

        Raises:
            SecureMessageError: If conversion fails

        """
        if len(ed25519_public) != 32:
            msg = f"Ed25519 public key must be 32 bytes, got {len(ed25519_public)}"
            raise SecureMessageError(msg)

        # RFC 8032 Section 5.1.5: Ed25519 to X25519 public key conversion
        # Ed25519 public key is the y-coordinate (255 bits) with sign bit in MSB
        # Extract y-coordinate (clear sign bit)
        y = int.from_bytes(ed25519_public, byteorder="little")
        # Clear the sign bit (bit 255)
        y = y & ((1 << 255) - 1)

        # Curve25519 prime: p = 2^255 - 19
        p = (1 << 255) - 19

        # Convert Edwards to Montgomery: u = (1+y)/(1-y) mod p
        # Compute 1+y mod p
        one_plus_y = (1 + y) % p
        # Compute 1-y mod p (handle negative)
        one_minus_y = (1 - y) % p
        if one_minus_y == 0:
            # Edge case: y = 1, which maps to infinity in Montgomery form
            # In practice, this is extremely rare (probability ~2^-255)
            # Return a special value or raise error
            msg = "Ed25519 public key maps to infinity in X25519 (y=1)"
            raise SecureMessageError(msg)

        # Compute modular inverse of (1-y) using Fermat's little theorem
        # inv = (1-y)^(p-2) mod p
        inv_one_minus_y = pow(one_minus_y, p - 2, p)

        # Compute u = (1+y) * inv(1-y) mod p
        u = (one_plus_y * inv_one_minus_y) % p

        # Encode u as 32-byte little-endian (X25519 format)
        # X25519 uses little-endian encoding
        return u.to_bytes(32, byteorder="little")

    def _derive_x25519_public_from_private(self, x25519_private: bytes) -> bytes:
        """Derive X25519 public key from X25519 private key.

        Args:
            x25519_private: X25519 private key bytes (32 bytes)

        Returns:
            X25519 public key bytes (32 bytes)

        """
        if not CRYPTOGRAPHY_AVAILABLE or x25519 is None:
            # Fallback: can't derive without cryptography library
            return x25519_private

        try:
            x25519_private_key = x25519.X25519PrivateKey.from_private_bytes(
                x25519_private
            )
            x25519_public_key = x25519_private_key.public_key()
            return x25519_public_key.public_bytes_raw()
        except Exception:
            # Fallback if derivation fails
            return x25519_private

    def _derive_shared_secret(
        self, our_private_key: bytes, peer_public_key: bytes
    ) -> bytes:
        """Derive shared secret using proper X25519 key exchange (RFC 8032).

        Args:
            our_private_key: Our X25519 private key (32 bytes)
            peer_public_key: Peer's X25519 public key (32 bytes)

        Returns:
            Shared secret (32 bytes) derived via HKDF from X25519 key exchange

        Raises:
            SecureMessageError: If key exchange fails or cryptography library unavailable

        Note:
            This method uses proper X25519 key exchange as specified in RFC 8032.
            The shared secret is derived using HKDF for additional key material derivation.

        """
        if (
            not CRYPTOGRAPHY_AVAILABLE
            or x25519 is None
            or HKDF is None
            or crypto_hashes is None
        ):
            msg = "Cryptography library required for shared secret derivation"
            raise SecureMessageError(msg)

        try:
            # Create X25519 private key object
            x25519_private = x25519.X25519PrivateKey.from_private_bytes(our_private_key)
            # Create X25519 public key object
            x25519_public = x25519.X25519PublicKey.from_public_bytes(peer_public_key)
            # Perform key exchange (RFC 7748)
            shared_secret_raw = x25519_private.exchange(x25519_public)
            # Use HKDF to derive final key material (RFC 5869)
            hkdf = HKDF(
                algorithm=crypto_hashes.SHA256(),
                length=32,
                salt=None,
                info=b"ccbt-secure-messaging",
            )
            return hkdf.derive(shared_secret_raw)
        except Exception as e:
            msg = f"X25519 key exchange failed: {e}"
            logger.exception(msg)
            raise SecureMessageError(msg) from e

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
            # For encryption, we need to derive X25519 keys (RFC 8032 Section 5.1.5)
            our_x25519_private = self._ed25519_to_x25519_private(our_private_key_bytes)
            # Convert recipient's Ed25519 public key to X25519 public key
            # This uses proper curve point conversion (Edwards → Montgomery)
            recipient_x25519_public = self._ed25519_to_x25519_public(
                recipient_public_key
            )

            # Derive shared secret using proper X25519 key exchange
            shared_secret = self._derive_shared_secret(
                our_x25519_private, recipient_x25519_public
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
            # Convert sender's Ed25519 public key to X25519 public key (RFC 8032 Section 5.1.5)
            # This uses proper curve point conversion (Edwards → Montgomery)
            sender_x25519_public = self._ed25519_to_x25519_public(
                secure_message.sender_public_key
            )

            # Derive shared secret using proper X25519 key exchange
            shared_secret = self._derive_shared_secret(
                our_x25519_private, sender_x25519_public
            )

            # Decrypt with AES-256-GCM
            aesgcm = AESGCM(shared_secret)
            return aesgcm.decrypt(
                secure_message.nonce,
                secure_message.encrypted_payload,
                None,
            )

        except Exception as e:
            msg = f"Failed to decrypt message: {e}"
            logger.exception(msg)
            raise SecureMessageError(msg) from e
