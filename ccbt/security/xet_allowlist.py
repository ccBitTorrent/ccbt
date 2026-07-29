"""Encrypted allowlist for XET folder synchronization.

This module provides Ed25519-based peer authentication and AES-256-GCM
encrypted allowlist storage for XET folder sync.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ccbt.utils.compat import to_thread_compat

logger = logging.getLogger(__name__)

try:
    from ccbt.security.key_manager import Ed25519KeyManager as _Ed25519KeyManager

    ED25519_AVAILABLE = True
except ImportError:
    ED25519_AVAILABLE = False
    _Ed25519KeyManager = None  # type: ignore[assignment, misc]
    logger.warning("Ed25519 key manager not available")

if TYPE_CHECKING:
    from ccbt.security.key_manager import Ed25519KeyManager


class XetAllowlistError(Exception):
    """Exception raised for allowlist errors."""


class XetAllowlist:
    """Encrypted allowlist manager for XET folders."""

    def __init__(
        self,
        allowlist_path: Union[str, Path],
        encryption_key: Optional[bytes] = None,
        key_manager: Optional[Ed25519KeyManager] = None,
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
        if encryption_key and len(encryption_key) != 32:
            msg = "Encryption key must be 32 bytes for AES-256"
            raise ValueError(msg)
        self.encryption_key = encryption_key
        self._legacy_encryption_key = hashlib.sha256(
            str(self.allowlist_path).encode()
        ).digest()
        self._loaded_secret: Optional[bytes] = None
        self._migrate_on_next_save = False

        # In-memory allowlist cache
        self._allowlist: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Raise if allowlist has not been loaded (e.g. load() not awaited in async context)."""
        if not self._loaded:
            msg = "Allowlist must be loaded before use; call await load() first"
            raise XetAllowlistError(msg)

    @property
    def _secret_path(self) -> Path:
        """Return the path for the local secret used by derived-key mode."""
        return self.allowlist_path.with_name(f"{self.allowlist_path.name}.key")

    def _load_or_create_local_secret(self, *, create: bool) -> bytes:
        """Return a stable local secret for allowlist key derivation."""
        if self._loaded_secret is not None:
            return self._loaded_secret
        if self._secret_path.exists():
            self._loaded_secret = self._secret_path.read_bytes()
            return self._loaded_secret
        if not create:
            msg = f"Allowlist secret file not found: {self._secret_path}"
            raise XetAllowlistError(msg)
        import secrets

        self._secret_path.parent.mkdir(parents=True, exist_ok=True)
        self._loaded_secret = secrets.token_bytes(32)
        self._secret_path.write_bytes(self._loaded_secret)
        return self._loaded_secret

    def _get_secret_material(self, *, create: bool) -> bytes:
        """Return the secret material used for KDF-based allowlist keys."""
        if self.encryption_key is not None:
            return self.encryption_key

        env_secret = os.environ.get("CCBT_XET_ALLOWLIST_SECRET")
        if env_secret:
            return env_secret.encode("utf-8")

        if self.key_manager is not None:
            try:
                return self.key_manager.get_private_key_bytes()
            except Exception:
                self.logger.debug(
                    "Falling back to local allowlist secret", exc_info=True
                )

        return self._load_or_create_local_secret(create=create)

    def _derive_encryption_key(self, salt: bytes, *, create: bool) -> bytes:
        """Derive the AES-GCM key for the current allowlist format."""
        if self.encryption_key is not None:
            return self.encryption_key
        secret_material = self._get_secret_material(create=create)
        return hashlib.scrypt(
            secret_material,
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )

    @staticmethod
    def _encode_bytes(value: bytes) -> str:
        """Encode bytes for the JSON allowlist envelope."""
        return base64.b64encode(value).decode("ascii")

    @staticmethod
    def _decode_bytes(value: str) -> bytes:
        """Decode bytes from the JSON allowlist envelope."""
        return base64.b64decode(value.encode("ascii"))

    async def load(self) -> None:
        """Load allowlist from encrypted file."""
        if self._loaded:
            return

        exists = await to_thread_compat(self.allowlist_path.exists)
        if not exists:
            self._allowlist = {}
            self._loaded = True
            return

        try:
            encrypted_data = await to_thread_compat(self.allowlist_path.read_bytes)
            if not encrypted_data:
                self._allowlist = {}
                self._loaded = True
                return
            try:
                envelope = json.loads(encrypted_data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                envelope = None

            try:
                if isinstance(envelope, dict) and envelope.get("version", 0) >= 2:
                    salt = self._decode_bytes(envelope["salt"])
                    nonce = self._decode_bytes(envelope["nonce"])
                    ciphertext = self._decode_bytes(envelope["ciphertext"])
                    await to_thread_compat(
                        lambda: self._load_or_create_local_secret(create=False)
                    )
                    aes_gcm = AESGCM(self._derive_encryption_key(salt, create=False))
                    plaintext = aes_gcm.decrypt(nonce, ciphertext, None)
                    data = json.loads(plaintext.decode("utf-8"))
                    self._allowlist = data.get("peers", {})
                else:
                    if len(encrypted_data) < 12:
                        msg = "Legacy allowlist is too short"
                        raise XetAllowlistError(msg)
                    nonce = encrypted_data[:12]
                    ciphertext = encrypted_data[12:]
                    plaintext = AESGCM(self._legacy_encryption_key).decrypt(
                        nonce, ciphertext, None
                    )
                    data = json.loads(plaintext.decode("utf-8"))
                    self._allowlist = data.get("peers", {})
                    self._migrate_on_next_save = True
            except Exception as e:
                self.logger.warning(
                    "Failed to decrypt allowlist file '%s': %s. Starting with empty allowlist.",
                    self.allowlist_path,
                    e,
                )
                self._allowlist = {}

            self._loaded = True
            self.logger.info("Loaded allowlist with %d peers", len(self._allowlist))

        except Exception:
            self.logger.exception("Error loading allowlist")
            self._allowlist = {}
            self._loaded = True

    async def save(self) -> None:
        """Save allowlist to encrypted file."""
        try:
            # Ensure loaded
            if not self._loaded:
                await self.load()

            await to_thread_compat(
                lambda: self._load_or_create_local_secret(create=True)
            )

            # Prepare data
            data = {
                "peers": self._allowlist,
                "version": 2,
            }

            plaintext = json.dumps(data, sort_keys=True).encode("utf-8")
            import secrets

            salt = secrets.token_bytes(16)
            nonce = self._generate_nonce()
            aes_gcm = AESGCM(self._derive_encryption_key(salt, create=True))
            ciphertext = aes_gcm.encrypt(nonce, plaintext, None)
            envelope = {
                "ciphertext": self._encode_bytes(ciphertext),
                "format": "xet_allowlist",
                "kdf": "scrypt" if self.encryption_key is None else "raw",
                "nonce": self._encode_bytes(nonce),
                "salt": self._encode_bytes(salt),
                "version": 2,
            }

            def _write_envelope() -> None:
                self.allowlist_path.parent.mkdir(parents=True, exist_ok=True)
                self.allowlist_path.write_text(
                    json.dumps(envelope, indent=2, sort_keys=True),
                    encoding="utf-8",
                )

            await to_thread_compat(_write_envelope)
            self._migrate_on_next_save = False

            self.logger.info("Saved allowlist with %d peers", len(self._allowlist))

        except Exception as e:
            msg = f"Failed to save allowlist: {e}"
            raise XetAllowlistError(msg) from e

    def add_peer(
        self,
        peer_id: str,
        public_key: Optional[bytes] = None,
        metadata: Optional[dict[str, Any]] = None,
        alias: Optional[str] = None,
    ) -> None:
        """Add peer to allowlist.

        Args:
            peer_id: Peer identifier
            public_key: Ed25519 public key (32 bytes) for authentication
            metadata: Optional metadata (name, description, etc.)
            alias: Optional human-readable alias for the peer

        """
        self._ensure_loaded()
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
            # Type checker needs help here - we know metadata is a dict at this point
            peer_entry["metadata"]["alias"] = alias  # type: ignore[index]

        if not isinstance(self._allowlist, dict):
            self._allowlist = {}  # type: ignore[assignment]
        self._allowlist[peer_id] = peer_entry  # type: ignore[index]
        self.logger.info("Added peer %s to allowlist", peer_id)

    def set_alias(self, peer_id: str, alias: str) -> bool:
        """Set alias for a peer.

        Args:
            peer_id: Peer identifier
            alias: Human-readable alias

        Returns:
            True if alias was set, False if peer not found

        """
        self._ensure_loaded()
        if peer_id not in self._allowlist:
            return False

        peer_entry = self._allowlist[peer_id]
        if "metadata" not in peer_entry:
            peer_entry["metadata"] = {}
        peer_entry["metadata"]["alias"] = alias

        self.logger.info("Set alias '%s' for peer %s", alias, peer_id)
        return True

    def get_alias(self, peer_id: str) -> Optional[str]:
        """Get alias for a peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Alias string or None if not found or not set

        """
        self._ensure_loaded()
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
        self._ensure_loaded()
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
        self._ensure_loaded()
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
        self._ensure_loaded()
        return peer_id in self._allowlist

    def get_peer_id_by_public_key(self, public_key: bytes) -> Optional[str]:
        """Return the allowlisted peer ID that owns a public key."""
        self._ensure_loaded()
        public_key_hex = public_key.hex()
        for peer_id, peer_entry in self._allowlist.items():
            expected_key_hex = peer_entry.get("public_key")
            if expected_key_hex == public_key_hex:
                return peer_id
        return None

    def get_peer_record_by_public_key(
        self, public_key: bytes
    ) -> Optional[dict[str, Any]]:
        """Return the full allowlist record for a public key."""
        peer_id = self.get_peer_id_by_public_key(public_key)
        if peer_id is None:
            return None
        return self._allowlist.get(peer_id)

    def is_public_key_allowed(self, public_key: bytes) -> bool:
        """Check whether a public key belongs to an allowlisted peer."""
        return self.get_peer_id_by_public_key(public_key) is not None

    def get_member_index(self, public_key: bytes) -> Optional[int]:
        """Return the 0-based index of the member for this public key (stable order by peer_id).

        Useful for logging and audit. Returns None if the key is not in the allowlist.
        """
        peer_id = self.get_peer_id_by_public_key(public_key)
        if peer_id is None:
            return None
        ordered = sorted(self._allowlist.keys())
        try:
            return ordered.index(peer_id)
        except ValueError:
            return None

    def verify_member_signature(
        self, public_key: bytes, signature: bytes, message: bytes
    ) -> bool:
        """Verify a signature for an allowlisted public key."""
        peer_id = self.get_peer_id_by_public_key(public_key)
        if peer_id is None:
            return False
        if not ED25519_AVAILABLE or not self.key_manager:
            return True
        try:
            return self.key_manager.verify_signature(message, signature, public_key)
        except Exception:
            self.logger.exception("Error verifying allowlist member signature")
            return False

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
        matched_peer_id = self.get_peer_id_by_public_key(public_key)
        if not self.is_allowed(peer_id):
            return False
        if matched_peer_id is not None and matched_peer_id != peer_id:
            self.logger.warning(
                "Peer %s presented public key for allowlisted peer %s",
                peer_id,
                matched_peer_id,
            )
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
                self.logger.warning("Public key mismatch for peer %s", peer_id)
                return False

        # Verify signature
        try:
            is_valid = self.key_manager.verify_signature(message, signature, public_key)
            if not is_valid:
                self.logger.warning("Invalid signature for peer %s", peer_id)
            return is_valid
        except Exception:
            self.logger.exception("Error verifying peer signature")
            return False

    def get_peers(self) -> list[str]:
        """Get list of all allowed peer IDs.

        Returns:
            List of peer IDs

        """
        self._ensure_loaded()
        return list(self._allowlist.keys())

    def get_peer_info(self, peer_id: str) -> Optional[dict[str, Any]]:
        """Get information about a peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Peer information dictionary or None if not found

        """
        self._ensure_loaded()
        return self._allowlist.get(peer_id)

    def get_allowlist_hash(self) -> bytes:
        """Calculate hash of allowlist for verification.

        Returns:
            32-byte SHA-256 hash of allowlist

        """
        self._ensure_loaded()
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
