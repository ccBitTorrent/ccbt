"""Extended XET handshake for folder synchronization.

This module extends the XET extension protocol to support:
- Allowlist hash exchange during BEP 10 extension handshake
- Peer identity verification via Ed25519 signatures
- Sync mode negotiation
- Git ref exchange for version checking
- Rejection of non-allowlisted peers
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import TYPE_CHECKING, Any, Optional

from ccbt.storage.xet_hashing import XetHasher

if TYPE_CHECKING:
    from ccbt.security.xet_allowlist import XetAllowlist

logger = logging.getLogger(__name__)


class XetHandshakeExtension:
    """Extended XET handshake for folder sync."""

    def __init__(
        self,
        allowlist_hash: Optional[bytes] = None,
        sync_mode: str = "best_effort",
        git_ref: Optional[str] = None,
        key_manager: Optional[Any] = None,  # Ed25519KeyManager
        workspace_id: Optional[bytes] = None,
        hash_algorithm: str = "auto",
        capabilities: Optional[dict[str, Any]] = None,
        allowlist: Optional[XetAllowlist] = None,
        auth_scope: str = "strict_workspace_auth",
        require_signed_metadata: bool = True,
        metadata_version: Optional[str] = None,
        metadata_root: Optional[str] = None,
    ) -> None:
        """Initialize XET handshake extension.

        Args:
            allowlist_hash: 32-byte hash of encrypted allowlist
            sync_mode: Synchronization mode
            git_ref: Current git commit hash/ref
            key_manager: Ed25519KeyManager for peer verification
            workspace_id: Optional workspace identifier bound to this handshake
            hash_algorithm: Negotiated hash algorithm name
            capabilities: Optional capability flags announced to peers
            allowlist: Optional resolved allowlist used for public-key checks
            auth_scope: Authorization policy scope for remote peers
            require_signed_metadata: Whether metadata messages must be signed
            metadata_version: Optional metadata version for identity payload
            metadata_root: Optional metadata root (e.g. tree hash) for identity payload

        """
        self.allowlist_hash = allowlist_hash
        self.sync_mode = sync_mode
        self.git_ref = git_ref
        self.key_manager = key_manager
        self.workspace_id = workspace_id
        self.hash_algorithm = hash_algorithm
        self.capabilities = capabilities or {}
        self.allowlist = allowlist
        self.auth_scope = auth_scope
        self.require_signed_metadata = require_signed_metadata
        self.metadata_version = metadata_version
        self.metadata_root = metadata_root
        self.logger = logging.getLogger(__name__)

        # Track peer handshake data
        self.peer_handshakes: dict[str, dict[str, Any]] = {}
        self._seen_nonces: set[tuple[str, bytes]] = set()

    @staticmethod
    def build_identity_message(
        public_key: bytes,
        nonce: bytes,
        *,
        allowlist_hash: Optional[bytes],
        sync_mode: str,
        git_ref: Optional[str],
        workspace_id: Optional[bytes] = None,
        hash_algorithm: str = "auto",
        capabilities: Optional[dict[str, Any]] = None,
        auth_scope: str = "strict_workspace_auth",
        metadata_version: Optional[str] = None,
        metadata_root: Optional[str] = None,
        freshness_token: Optional[str] = None,
    ) -> bytes:
        """Build the signed handshake payload for identity verification.

        The signed payload is the single source of truth for identity; verification
        must validate freshness (e.g. nonce not reused, token not expired).
        """
        payload = {
            "allowlist_hash": allowlist_hash.hex() if allowlist_hash else None,
            "auth_scope": auth_scope,
            "capabilities": capabilities or {},
            "freshness_token": freshness_token or nonce.hex(),
            "git_ref": git_ref,
            "hash_algorithm": XetHasher.get_hash_identity(hash_algorithm),
            "metadata_root": metadata_root,
            "metadata_version": metadata_version,
            "nonce": nonce.hex(),
            "public_key": public_key.hex(),
            "sync_mode": sync_mode,
            "version": "1.0",
            "workspace_id": workspace_id.hex() if workspace_id else None,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )

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
        handshake_data["xet_folder_sync"]["hash_algorithm"] = (
            XetHasher.get_hash_identity(self.hash_algorithm)
        )
        handshake_data["xet_folder_sync"]["capabilities"] = dict(self.capabilities)
        handshake_data["xet_folder_sync"]["auth_scope"] = self.auth_scope
        handshake_data["xet_folder_sync"]["require_signed_metadata"] = (
            self.require_signed_metadata
        )

        if self.workspace_id is not None:
            handshake_data["xet_folder_sync"]["workspace_id"] = self.workspace_id.hex()

        if self.metadata_version is not None:
            handshake_data["xet_folder_sync"]["metadata_version"] = (
                self.metadata_version
            )
        if self.metadata_root is not None:
            handshake_data["xet_folder_sync"]["metadata_root"] = self.metadata_root

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
                    nonce = secrets.token_bytes(16)
                    signature = self.key_manager.sign_message(
                        self.build_identity_message(
                            public_key,
                            nonce,
                            allowlist_hash=self.allowlist_hash,
                            sync_mode=self.sync_mode,
                            git_ref=self.git_ref,
                            workspace_id=self.workspace_id,
                            hash_algorithm=self.hash_algorithm,
                            capabilities=self.capabilities,
                            auth_scope=self.auth_scope,
                            metadata_version=self.metadata_version,
                            metadata_root=self.metadata_root,
                            freshness_token=nonce.hex(),
                        )
                    )
                    handshake_data["xet_folder_sync"]["ed25519_nonce"] = nonce.hex()
                    handshake_data["xet_folder_sync"]["ed25519_signature"] = (
                        signature.hex()
                    )
            except Exception as e:
                self.logger.debug("Error getting public key for handshake: %s", e)

        return handshake_data

    def decode_handshake(
        self, peer_id: str, data: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
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
        handshake_info["hash_algorithm"] = xet_data.get("hash_algorithm", "auto")
        handshake_info["auth_scope"] = xet_data.get(
            "auth_scope", "strict_workspace_auth"
        )
        handshake_info["require_signed_metadata"] = bool(
            xet_data.get("require_signed_metadata", True)
        )
        capabilities = xet_data.get("capabilities")
        if isinstance(capabilities, dict):
            handshake_info["capabilities"] = dict(capabilities)

        # Extract git ref
        handshake_info["git_ref"] = xet_data.get("git_ref")

        handshake_info["metadata_version"] = xet_data.get("metadata_version")
        handshake_info["metadata_root"] = xet_data.get("metadata_root")

        workspace_id_hex = xet_data.get("workspace_id")
        if isinstance(workspace_id_hex, str):
            try:
                handshake_info["workspace_id"] = bytes.fromhex(workspace_id_hex)
            except ValueError:
                self.logger.warning("Invalid workspace id from peer %s", peer_id)

        # Extract Ed25519 public key
        public_key_hex = xet_data.get("ed25519_public_key")
        if public_key_hex:
            try:
                handshake_info["ed25519_public_key"] = bytes.fromhex(public_key_hex)
            except ValueError:
                self.logger.warning("Invalid public key from peer %s", peer_id)

        nonce_hex = xet_data.get("ed25519_nonce")
        if nonce_hex:
            try:
                handshake_info["ed25519_nonce"] = bytes.fromhex(nonce_hex)
            except ValueError:
                self.logger.warning("Invalid identity nonce from peer %s", peer_id)

        signature_hex = xet_data.get("ed25519_signature")
        if signature_hex:
            try:
                handshake_info["ed25519_signature"] = bytes.fromhex(signature_hex)
            except ValueError:
                self.logger.warning("Invalid identity signature from peer %s", peer_id)

        # Store peer handshake data
        self.peer_handshakes[peer_id] = handshake_info

        return handshake_info

    def verify_peer_allowlist(
        self,
        peer_id: str,
        peer_allowlist_hash: Optional[bytes],
        peer_public_key: Optional[bytes] = None,
        peer_workspace_id: Optional[bytes] = None,
        peer_nonce: Optional[bytes] = None,
    ) -> bool:
        """Verify peer's allowlist hash matches expected.

        When require_signed_metadata is True, freshness is enforced: if peer_nonce
        is provided and (peer_id, peer_nonce) was already seen, returns False (replay).
        On success, (peer_id, peer_nonce) is added to _seen_nonces.

        Args:
            peer_id: Peer identifier
            peer_allowlist_hash: Peer's allowlist hash
            peer_public_key: Optional Ed25519 public key advertised by the peer
            peer_workspace_id: Optional peer workspace id from handshake
            peer_nonce: Optional nonce from peer's signed identity (for replay check)

        Returns:
            True if allowlist hash matches or no allowlist required

        """
        if peer_nonce is not None:
            key = (peer_id, peer_nonce)
            if key in self._seen_nonces:
                self.logger.warning(
                    "Replay detected for peer %s (nonce already seen)", peer_id
                )
                return False
        if self.workspace_id is not None and peer_workspace_id != self.workspace_id:
            self.logger.warning(
                "Workspace mismatch for peer %s (expected %s, got %s)",
                peer_id,
                self.workspace_id.hex()[:16],
                peer_workspace_id.hex()[:16]
                if isinstance(peer_workspace_id, bytes)
                else None,
            )
            return False

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

        if self.allowlist is not None:
            if peer_public_key is None:
                if self.auth_scope == "strict_workspace_auth":
                    self.logger.warning(
                        "Peer %s did not provide a public key for strict allowlist auth",
                        peer_id,
                    )
                    return False
                return True
            if not self.allowlist.is_public_key_allowed(peer_public_key):
                self.logger.warning(
                    "Peer %s presented a public key that is not in the allowlist",
                    peer_id,
                )
                return False
        if peer_nonce is not None:
            self._seen_nonces.add((peer_id, peer_nonce))
            _max_seen = 10000
            if len(self._seen_nonces) > _max_seen:
                self._seen_nonces.clear()

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
        except Exception:
            self.logger.exception("Error verifying peer identity")
            return False

    def verify_handshake_identity(
        self, peer_id: str, handshake_info: dict[str, Any]
    ) -> bool:
        """Verify signed handshake identity information when available."""
        public_key = handshake_info.get("ed25519_public_key")
        nonce = handshake_info.get("ed25519_nonce")
        signature = handshake_info.get("ed25519_signature")

        if public_key is None and signature is None and nonce is None:
            return not self.require_signed_metadata
        if not isinstance(public_key, bytes):
            self.logger.warning(
                "Missing public key for peer %s handshake identity", peer_id
            )
            return False
        if not isinstance(nonce, bytes):
            self.logger.warning("Missing nonce for peer %s handshake identity", peer_id)
            return False
        if not isinstance(signature, bytes):
            self.logger.warning(
                "Missing signature for peer %s handshake identity", peer_id
            )
            return False
        nonce_key = (peer_id, nonce)
        if nonce_key in self._seen_nonces:
            self.logger.warning("Replay nonce detected for peer %s", peer_id)
            return False
        self._seen_nonces.add(nonce_key)

        message = self.build_identity_message(
            public_key,
            nonce,
            allowlist_hash=handshake_info.get("allowlist_hash"),
            sync_mode=str(handshake_info.get("sync_mode", "best_effort")),
            git_ref=handshake_info.get("git_ref"),
            workspace_id=handshake_info.get("workspace_id"),
            hash_algorithm=str(handshake_info.get("hash_algorithm", "auto")),
            capabilities=handshake_info.get("capabilities"),
            auth_scope=str(handshake_info.get("auth_scope", self.auth_scope)),
        )
        if self.allowlist is not None and not self.allowlist.verify_member_signature(
            public_key, signature, message
        ):
            self.logger.warning(
                "Peer %s failed allowlist member signature verification", peer_id
            )
            return False
        return self.verify_peer_identity(peer_id, public_key, signature, message)

    def negotiate_sync_mode(self, peer_id: str, peer_sync_mode: str) -> Optional[str]:
        """Negotiate sync mode with peer.

        Args:
            peer_id: Peer identifier
            peer_sync_mode: Peer's requested sync mode

        Returns:
            Agreed sync mode or None if incompatible

        """
        valid_modes = {"designated", "best_effort", "broadcast", "consensus"}

        if peer_sync_mode not in valid_modes:
            self.logger.warning(
                "Invalid sync mode from peer %s: %s", peer_id, peer_sync_mode
            )
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

    def get_peer_git_ref(self, peer_id: str) -> Optional[str]:
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

    def compare_git_refs(
        self, local_ref: Optional[str], peer_ref: Optional[str]
    ) -> bool:
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

    def get_peer_handshake_info(self, peer_id: str) -> Optional[dict[str, Any]]:
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
