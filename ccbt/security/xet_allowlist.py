"""Encrypted allowlist for XET folder synchronization.

This module provides Ed25519-based peer authentication and AES-256-GCM
encrypted allowlist storage for XET folder sync.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

try:
    from ccbt.security.key_manager import Ed25519KeyManager

    ED25519_AVAILABLE = True
except ImportError:
    ED25519_AVAILABLE = False
    logger.warning("Ed25519 key manager not available")


class XetAllowlistError(Exception):
    """Exception raised for allowlist errors."""


class XetAllowlist:
    """Encrypted allowlist manager for XET folders."""

    def __init__(
        self,
        allowlist_path: str | Path,
        encryption_key: bytes | None = None,
        key_manager: Ed25519KeyManager | None = None,
    ) -> None:
        """Initialize allowlist manager.

        Args:
            allowlist_path: Path to allowlist file
            encryption_key: AES-256-GCM encryption key (32 bytes, auto-generated if None)
            key_manager: Ed25519KeyManager for peer authentication

        """
        self.allowlist_path = Path(allowlist_path)
        self.key_manager = key_manager
        self.logger = logging.getLogger(__name__)

        # Generate or use provided encryption key
        if encryption_key:
            if len(encryption_key) != 32:
                msg = "Encryption key must be 32 bytes for AES-256"
                raise ValueError(msg)
            self.encryption_key = encryption_key
        else:
            # Generate key from allowlist path hash (deterministic)
            key_hash = hashlib.sha256(str(self.allowlist_path).encode()).digest()
            self.encryption_key = key_hash

        # Initialize AES-GCM
        self.aes_gcm = AESGCM(self.encryption_key)

        # In-memory allowlist cache
        self._allowlist: dict[str, dict[str, Any]] = {}
        self._loaded = False

    async def load(self) -> None:
        """Load allowlist from encrypted file."""
        if self._loaded:
            return

        if not self.allowlist_path.exists():
            self._allowlist = {}
            self._loaded = True
            return

        try:
            # Read encrypted file
            encrypted_data = self.allowlist_path.read_bytes()

            if len(encrypted_data) < 12:  # Nonce (12 bytes) + at least some data
                self.logger.warning("Invalid allowlist file, starting with empty list")
                self._allowlist = {}
                self._loaded = True
                return

            # Extract nonce and ciphertext
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]

            # Decrypt
            try:
                plaintext = self.aes_gcm.decrypt(nonce, ciphertext, None)
                data = json.loads(plaintext.decode("utf-8"))
                self._allowlist = data.get("peers", {})
            except Exception as e:
                self.logger.warning("Failed to decrypt allowlist: %s", e)
                self._allowlist = {}

            self._loaded = True
            self.logger.info("Loaded allowlist with %d peers", len(self._allowlist))

        except Exception as e:
            self.logger.exception("Error loading allowlist: %s", e)
            self._allowlist = {}
            self._loaded = True

    async def save(self) -> None:
        """Save allowlist to encrypted file."""
        try:
            # Ensure loaded
            if not self._loaded:
                await self.load()

            # Prepare data
            data = {
                "peers": self._allowlist,
                "version": 1,
            }

            # Encrypt
            plaintext = json.dumps(data).encode("utf-8")
            nonce = self._generate_nonce()
            ciphertext = self.aes_gcm.encrypt(nonce, plaintext, None)

            # Write to file
            self.allowlist_path.parent.mkdir(parents=True, exist_ok=True)
            self.allowlist_path.write_bytes(nonce + ciphertext)

            self.logger.info("Saved allowlist with %d peers", len(self._allowlist))

        except Exception as e:
            msg = f"Failed to save allowlist: {e}"
            raise XetAllowlistError(msg) from e

    def add_peer(
        self,
        peer_id: str,
        public_key: bytes | None = None,
        metadata: dict[str, Any] | None = None,
        alias: str | None = None,
    ) -> None:
        """Add peer to allowlist.

        Args:
            peer_id: Peer identifier
            public_key: Ed25519 public key (32 bytes) for authentication
            metadata: Optional metadata (name, description, etc.)
            alias: Optional human-readable alias for the peer

        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load())

        # Get existing entry or create new one
        if peer_id in self._allowlist:
            peer_entry = self._allowlist[peer_id]
        else:
            peer_entry = {
                "added_at": self._get_timestamp(),
            }

        if public_key:
            if len(public_key) != 32:
                msg = "Public key must be 32 bytes"
                raise ValueError(msg)
            peer_entry["public_key"] = public_key.hex()

        if metadata:
            peer_entry["metadata"] = metadata

        if alias:
            if "metadata" not in peer_entry:
                peer_entry["metadata"] = {}
            peer_entry["metadata"]["alias"] = alias

        self._allowlist[peer_id] = peer_entry
        self.logger.info("Added peer %s to allowlist", peer_id)

    def set_alias(self, peer_id: str, alias: str) -> bool:
        """Set alias for a peer.

        Args:
            peer_id: Peer identifier
            alias: Human-readable alias

        Returns:
            True if alias was set, False if peer not found

        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load())

        if peer_id not in self._allowlist:
            return False

        peer_entry = self._allowlist[peer_id]
        if "metadata" not in peer_entry:
            peer_entry["metadata"] = {}
        peer_entry["metadata"]["alias"] = alias

        self.logger.info("Set alias '%s' for peer %s", alias, peer_id)
        return True

    def get_alias(self, peer_id: str) -> str | None:
        """Get alias for a peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Alias string or None if not found or not set

        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load())

        peer_entry = self._allowlist.get(peer_id)
        if not peer_entry:
            return None

        metadata = peer_entry.get("metadata", {})
        return metadata.get("alias") if isinstance(metadata, dict) else None

    def remove_alias(self, peer_id: str) -> bool:
        """Remove alias for a peer.

        Args:
            peer_id: Peer identifier

        Returns:
            True if alias was removed, False if peer not found or no alias set

        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load())

        if peer_id not in self._allowlist:
            return False

        peer_entry = self._allowlist[peer_id]
        metadata = peer_entry.get("metadata", {})
        if not isinstance(metadata, dict) or "alias" not in metadata:
            return False

        del metadata["alias"]
        if not metadata:
            # Remove metadata dict if empty
            peer_entry.pop("metadata", None)

        self.logger.info("Removed alias for peer %s", peer_id)
        return True

    def remove_peer(self, peer_id: str) -> bool:
        """Remove peer from allowlist.

        Args:
            peer_id: Peer identifier

        Returns:
            True if peer was removed, False if not found

        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load())

        if peer_id in self._allowlist:
            del self._allowlist[peer_id]
            self.logger.info("Removed peer %s from allowlist", peer_id)
            return True

        return False

    def is_allowed(self, peer_id: str) -> bool:
        """Check if peer is in allowlist.

        Args:
            peer_id: Peer identifier

        Returns:
            True if peer is allowed

        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load())

        return peer_id in self._allowlist

    def verify_peer(
        self, peer_id: str, public_key: bytes, signature: bytes, message: bytes
    ) -> bool:
        """Verify peer identity using Ed25519 signature.

        Args:
            peer_id: Peer identifier
            public_key: Peer's Ed25519 public key (32 bytes)
            signature: Ed25519 signature (64 bytes)
            message: Message that was signed

        Returns:
            True if peer is allowed and signature is valid

        """
        if not self.is_allowed(peer_id):
            return False

        if not ED25519_AVAILABLE or not self.key_manager:
            # If Ed25519 not available, just check allowlist membership
            return True

        # Get expected public key from allowlist
        peer_entry = self._allowlist.get(peer_id)
        if not peer_entry:
            return False

        expected_key_hex = peer_entry.get("public_key")
        if expected_key_hex:
            expected_key = bytes.fromhex(expected_key_hex)
            if expected_key != public_key:
                self.logger.warning(
                    "Public key mismatch for peer %s", peer_id
                )
                return False

        # Verify signature
        try:
            is_valid = self.key_manager.verify_signature(message, signature, public_key)
            if not is_valid:
                self.logger.warning(
                    "Invalid signature for peer %s", peer_id
                )
            return is_valid
        except Exception as e:
            self.logger.exception("Error verifying peer signature: %s", e)
            return False

    def get_peers(self) -> list[str]:
        """Get list of all allowed peer IDs.

        Returns:
            List of peer IDs

        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load())

        return list(self._allowlist.keys())

    def get_peer_info(self, peer_id: str) -> dict[str, Any] | None:
        """Get information about a peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Peer information dictionary or None if not found

        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load())

        return self._allowlist.get(peer_id)

    def get_allowlist_hash(self) -> bytes:
        """Calculate hash of allowlist for verification.

        Returns:
            32-byte SHA-256 hash of allowlist

        """
        if not self._loaded:
            import asyncio

            asyncio.run(self.load())

        # Create deterministic representation
        peers_sorted = sorted(self._allowlist.items())
        data = json.dumps(peers_sorted, sort_keys=True).encode("utf-8")
        return hashlib.sha256(data).digest()

    def _generate_nonce(self) -> bytes:
        """Generate 12-byte nonce for AES-GCM.

        Returns:
            12-byte nonce

        """
        import secrets

        return secrets.token_bytes(12)

    def _get_timestamp(self) -> float:
        """Get current timestamp.

        Returns:
            Current timestamp

        """
        import time

        return time.time()




