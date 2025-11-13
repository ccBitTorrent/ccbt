"""Ed25519 Handshake Extension for BitTorrent.

from __future__ import annotations

Provides Ed25519-based cryptographic authentication for BitTorrent peer handshakes.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from ccbt.utils.logging_config import get_logger

if TYPE_CHECKING:
    from ccbt.security.key_manager import Ed25519KeyManager

logger = get_logger(__name__)


class Ed25519HandshakeError(Exception):
    """Base exception for Ed25519 handshake errors."""


class Ed25519Handshake:
    """Ed25519 handshake for peer-to-peer authentication.

    Provides cryptographic authentication using Ed25519 signatures
    during BitTorrent handshake exchange.
    """

    def __init__(self, key_manager: Ed25519KeyManager):
        """Initialize Ed25519 handshake.

        Args:
            key_manager: Ed25519KeyManager instance for signing/verification

        """
        self.key_manager = key_manager

    def initiate_handshake(
        self, info_hash: bytes, peer_id: bytes
    ) -> tuple[bytes, bytes]:
        """Initiate handshake with Ed25519 signature.

        Args:
            info_hash: Torrent info hash (20 bytes)
            peer_id: Our peer ID (20 bytes)

        Returns:
            Tuple of (public_key_bytes, signature_bytes)

        """
        try:
            # Get our public key
            public_key_bytes = self.key_manager.get_public_key_bytes()

            # Create handshake message to sign
            # Format: info_hash + peer_id + timestamp
            timestamp = int(time.time())
            message = info_hash + peer_id + timestamp.to_bytes(8, "big")

            # Sign the message
            signature = self.key_manager.sign_message(message)

            logger.debug(
                "Initiated Ed25519 handshake: public_key=%s, signature_len=%d",
                public_key_bytes.hex()[:16],
                len(signature),
            )

            return public_key_bytes, signature
        except Exception as e:
            msg = f"Failed to initiate Ed25519 handshake: {e}"
            logger.exception(msg)
            raise Ed25519HandshakeError(msg) from e

    def verify_peer_handshake(
        self,
        info_hash: bytes,
        peer_id: bytes,
        peer_public_key: bytes,
        peer_signature: bytes,
        timestamp: int | None = None,
    ) -> bool:
        """Verify peer's handshake signature.

        Args:
            info_hash: Torrent info hash (20 bytes)
            peer_id: Peer's peer ID (20 bytes)
            peer_public_key: Peer's Ed25519 public key (32 bytes)
            peer_signature: Peer's signature (64 bytes)
            timestamp: Optional timestamp from handshake (for replay protection)

        Returns:
            True if signature is valid, False otherwise

        """
        try:
            # Reconstruct the message that was signed
            if timestamp is None:
                # Use current timestamp if not provided (for backward compatibility)
                timestamp = int(time.time())

            message = info_hash + peer_id + timestamp.to_bytes(8, "big")

            # Verify signature
            is_valid = self.key_manager.verify_signature(
                message, peer_signature, peer_public_key
            )

            if is_valid:
                logger.debug(
                    "Verified Ed25519 handshake from peer: %s",
                    peer_public_key.hex()[:16],
                )
            else:
                logger.warning(
                    "Invalid Ed25519 handshake signature from peer: %s",
                    peer_public_key.hex()[:16],
                )

            return is_valid
        except Exception as e:
            logger.debug("Ed25519 handshake verification error: %s", e)
            return False

    def create_handshake_extension(
        self, info_hash: bytes, peer_id: bytes
    ) -> dict[str, Any]:
        """Create handshake extension data with Ed25519 signature.

        Args:
            info_hash: Torrent info hash (20 bytes)
            peer_id: Our peer ID (20 bytes)

        Returns:
            Dictionary with public_key, signature, and timestamp

        """
        public_key_bytes, signature = self.initiate_handshake(info_hash, peer_id)
        timestamp = int(time.time())

        return {
            "ed25519_public_key": public_key_bytes,
            "ed25519_signature": signature,
            "ed25519_timestamp": timestamp,
        }

    def parse_handshake_extension(
        self, extension_data: dict[str, Any]
    ) -> tuple[bytes, bytes, int] | None:
        """Parse handshake extension data.

        Args:
            extension_data: Dictionary from handshake extension

        Returns:
            Tuple of (public_key, signature, timestamp) or None if invalid

        """
        try:
            public_key = extension_data.get("ed25519_public_key")
            signature = extension_data.get("ed25519_signature")
            timestamp = extension_data.get("ed25519_timestamp", int(time.time()))

            if not public_key or not signature:
                return None

            # Ensure proper types
            if isinstance(public_key, str):
                public_key = bytes.fromhex(public_key)
            if isinstance(signature, str):
                signature = bytes.fromhex(signature)
            if isinstance(timestamp, str):
                timestamp = int(timestamp)

            if len(public_key) != 32 or len(signature) != 64:
                return None

            return public_key, signature, timestamp
        except Exception as e:
            logger.debug("Failed to parse Ed25519 handshake extension: %s", e)
            return None
