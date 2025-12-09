"""Extended XET handshake for folder synchronization.

This module extends the XET extension protocol to support:
- Allowlist hash exchange during BEP 10 extension handshake
- Peer identity verification via Ed25519 signatures
- Sync mode negotiation
- Git ref exchange for version checking
- Rejection of non-allowlisted peers
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class XetHandshakeExtension:
    """Extended XET handshake for folder sync."""

    def __init__(
        self,
        allowlist_hash: bytes | None = None,
        sync_mode: str = "best_effort",
        git_ref: str | None = None,
        key_manager: Any | None = None,  # Ed25519KeyManager
    ) -> None:
        """Initialize XET handshake extension.

        Args:
            allowlist_hash: 32-byte hash of encrypted allowlist
            sync_mode: Synchronization mode
            git_ref: Current git commit hash/ref
            key_manager: Ed25519KeyManager for peer verification

        """
        self.allowlist_hash = allowlist_hash
        self.sync_mode = sync_mode
        self.git_ref = git_ref
        self.key_manager = key_manager
        self.logger = logging.getLogger(__name__)

        # Track peer handshake data
        self.peer_handshakes: dict[str, dict[str, Any]] = {}

    def encode_handshake(self) -> dict[str, Any]:
        """Encode XET folder sync handshake data.

        Returns:
            Dictionary containing handshake data for BEP 10 extension

        """
        handshake_data: dict[str, Any] = {
            "xet_folder_sync": {
                "version": "1.0",
                "supports_folder_sync": True,
            },
        }

        # Add allowlist hash if available
        if self.allowlist_hash:
            if len(self.allowlist_hash) != 32:
                msg = "Allowlist hash must be 32 bytes"
                raise ValueError(msg)
            handshake_data["xet_folder_sync"]["allowlist_hash"] = (
                self.allowlist_hash.hex()
            )

        # Add sync mode
        handshake_data["xet_folder_sync"]["sync_mode"] = self.sync_mode

        # Add git ref if available
        if self.git_ref:
            handshake_data["xet_folder_sync"]["git_ref"] = self.git_ref

        # Add Ed25519 public key if key manager available
        if self.key_manager:
            try:
                public_key = self.key_manager.get_public_key_bytes()
                if public_key:
                    handshake_data["xet_folder_sync"]["ed25519_public_key"] = (
                        public_key.hex()
                    )
            except Exception as e:
                self.logger.debug("Error getting public key for handshake: %s", e)

        return handshake_data

    def decode_handshake(
        self, peer_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Decode XET folder sync handshake from peer.

        Args:
            peer_id: Peer identifier
            data: Extension handshake data dictionary

        Returns:
            Decoded handshake data or None if invalid

        """
        xet_data = data.get("xet_folder_sync", {})
        if not isinstance(xet_data, dict):
            return None

        if not xet_data.get("supports_folder_sync", False):
            return None

        handshake_info: dict[str, Any] = {
            "version": xet_data.get("version", "1.0"),
            "supports_folder_sync": True,
        }

        # Extract allowlist hash
        allowlist_hash_hex = xet_data.get("allowlist_hash")
        if allowlist_hash_hex:
            try:
                handshake_info["allowlist_hash"] = bytes.fromhex(allowlist_hash_hex)
            except ValueError:
                self.logger.warning("Invalid allowlist hash from peer %s", peer_id)

        # Extract sync mode
        handshake_info["sync_mode"] = xet_data.get("sync_mode", "best_effort")

        # Extract git ref
        handshake_info["git_ref"] = xet_data.get("git_ref")

        # Extract Ed25519 public key
        public_key_hex = xet_data.get("ed25519_public_key")
        if public_key_hex:
            try:
                handshake_info["ed25519_public_key"] = bytes.fromhex(public_key_hex)
            except ValueError:
                self.logger.warning("Invalid public key from peer %s", peer_id)

        # Store peer handshake data
        self.peer_handshakes[peer_id] = handshake_info

        return handshake_info

    def verify_peer_allowlist(
        self, peer_id: str, peer_allowlist_hash: bytes | None
    ) -> bool:
        """Verify peer's allowlist hash matches expected.

        Args:
            peer_id: Peer identifier
            peer_allowlist_hash: Peer's allowlist hash

        Returns:
            True if allowlist hash matches or no allowlist required

        """
        # If we don't have an allowlist, accept all peers
        if not self.allowlist_hash:
            return True

        # If peer doesn't provide allowlist hash, reject
        if not peer_allowlist_hash:
            self.logger.warning(
                "Peer %s did not provide allowlist hash, rejecting", peer_id
            )
            return False

        # Compare hashes
        if peer_allowlist_hash != self.allowlist_hash:
            self.logger.warning(
                "Allowlist hash mismatch for peer %s (expected %s, got %s)",
                peer_id,
                self.allowlist_hash.hex()[:16],
                peer_allowlist_hash.hex()[:16],
            )
            return False

        return True

    def verify_peer_identity(
        self,
        peer_id: str,
        public_key: bytes,
        signature: bytes,
        message: bytes,
    ) -> bool:
        """Verify peer identity using Ed25519 signature.

        Args:
            peer_id: Peer identifier
            public_key: Peer's Ed25519 public key (32 bytes)
            signature: Ed25519 signature (64 bytes)
            message: Message that was signed

        Returns:
            True if signature is valid

        """
        if not self.key_manager:
            # No key manager, skip verification
            return True

        if len(public_key) != 32:
            self.logger.warning("Invalid public key length from peer %s", peer_id)
            return False

        if len(signature) != 64:
            self.logger.warning("Invalid signature length from peer %s", peer_id)
            return False

        try:
            is_valid = self.key_manager.verify_signature(message, signature, public_key)
            if not is_valid:
                self.logger.warning("Invalid signature from peer %s", peer_id)
            return is_valid
        except Exception as e:
            self.logger.exception("Error verifying peer identity: %s", e)
            return False

    def negotiate_sync_mode(
        self, peer_id: str, peer_sync_mode: str
    ) -> str | None:
        """Negotiate sync mode with peer.

        Args:
            peer_id: Peer identifier
            peer_sync_mode: Peer's requested sync mode

        Returns:
            Agreed sync mode or None if incompatible

        """
        valid_modes = {"designated", "best_effort", "broadcast", "consensus"}

        if peer_sync_mode not in valid_modes:
            self.logger.warning("Invalid sync mode from peer %s: %s", peer_id, peer_sync_mode)
            return None

        # For now, use the more restrictive mode
        # In practice, both peers should agree on mode from .tonic file
        if self.sync_mode == "designated" or peer_sync_mode == "designated":
            # Designated mode requires explicit agreement
            if self.sync_mode != peer_sync_mode:
                self.logger.warning(
                    "Sync mode mismatch: local=%s, peer=%s",
                    self.sync_mode,
                    peer_sync_mode,
                )
                return None
            return "designated"

        # For other modes, prefer consensus > broadcast > best_effort
        mode_priority = {
            "consensus": 3,
            "broadcast": 2,
            "best_effort": 1,
        }

        local_priority = mode_priority.get(self.sync_mode, 0)
        peer_priority = mode_priority.get(peer_sync_mode, 0)

        # Use higher priority mode
        if local_priority >= peer_priority:
            return self.sync_mode
        return peer_sync_mode

    def get_peer_git_ref(self, peer_id: str) -> str | None:
        """Get git ref from peer handshake.

        Args:
            peer_id: Peer identifier

        Returns:
            Git commit hash/ref or None

        """
        handshake = self.peer_handshakes.get(peer_id)
        if handshake:
            return handshake.get("git_ref")
        return None

    def compare_git_refs(self, local_ref: str | None, peer_ref: str | None) -> bool:
        """Compare git refs to check if versions match.

        Args:
            local_ref: Local git commit hash/ref
            peer_ref: Peer's git commit hash/ref

        Returns:
            True if refs match or both are None

        """
        if local_ref is None and peer_ref is None:
            return True

        if local_ref is None or peer_ref is None:
            return False

        return local_ref == peer_ref

    def get_peer_handshake_info(self, peer_id: str) -> dict[str, Any] | None:
        """Get stored handshake information for a peer.

        Args:
            peer_id: Peer identifier

        Returns:
            Handshake information dictionary or None

        """
        return self.peer_handshakes.get(peer_id)

    def remove_peer_handshake(self, peer_id: str) -> None:
        """Remove stored handshake information for a peer.

        Args:
            peer_id: Peer identifier

        """
        if peer_id in self.peer_handshakes:
            del self.peer_handshakes[peer_id]






