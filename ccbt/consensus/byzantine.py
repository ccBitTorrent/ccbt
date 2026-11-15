"""Byzantine fault tolerance implementation.

Provides Ed25519 signature verification and weighted voting for Byzantine consensus.
Quorum requires ``2f+1`` with ``n >= 3f+1``; enabling with too few peers fails loudly.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    _ED25519_AVAILABLE = True
except ImportError:  # pragma: no cover
    Ed25519PrivateKey = None  # type: ignore[misc, assignment]
    Ed25519PublicKey = None  # type: ignore[misc, assignment]
    _ED25519_AVAILABLE = False


class ByzantineConsensus:
    """Byzantine fault tolerance consensus with real Ed25519 verification."""

    def __init__(
        self,
        node_id: str,
        fault_threshold: float = 0.33,
        weighted_voting: bool = False,
        node_weights: Optional[dict[str, float]] = None,
        *,
        cluster_size: Optional[int] = None,
        max_faulty: Optional[int] = None,
    ):
        """Initialize Byzantine consensus.

        Args:
            node_id: Unique identifier for this node
            fault_threshold: Maximum fraction of faulty nodes (0.0 to 1.0)
            weighted_voting: Whether to use weighted voting
            node_weights: Dictionary of node_id -> weight (for weighted voting)
            cluster_size: Expected ``n``; when set, enforces ``n >= 3f+1``
            max_faulty: Expected ``f``; defaults from fault_threshold * n

        """
        if not 0.0 <= fault_threshold <= 1.0:
            msg = "Fault threshold must be between 0.0 and 1.0"
            raise ValueError(msg)

        self.node_id = node_id
        self.fault_threshold = fault_threshold
        self.weighted_voting = weighted_voting
        self.node_weights = node_weights or {}
        self.signatures: dict[str, bytes] = {}  # node_id -> public_key bytes

        if cluster_size is not None:
            f = (
                max_faulty
                if max_faulty is not None
                else int(cluster_size * fault_threshold)
            )
            if cluster_size < 3 * f + 1:
                msg = (
                    f"Byzantine mode requires n >= 3f+1 "
                    f"(got n={cluster_size}, f={f}); refusing to degrade"
                )
                raise ValueError(msg)
            self._quorum = 2 * f + 1
            self._max_faulty = f
        else:
            self._quorum = None
            self._max_faulty = None

    def register_public_key(self, node_id: str, public_key: bytes) -> None:
        """Register allowlist Ed25519 public key for a node."""
        if len(public_key) != 32:
            msg = "Ed25519 public key must be 32 bytes"
            raise ValueError(msg)
        self.signatures[node_id] = public_key

    def propose(
        self,
        proposal: dict[str, Any],
        signature: Optional[bytes] = None,
    ) -> dict[str, Any]:
        """Create a proposal with optional signature."""
        return {
            "proposal": proposal,
            "proposer": self.node_id,
            "signature": signature,
        }

    def vote(
        self,
        proposal: dict[str, Any],
        vote: bool,
        signature: Optional[bytes] = None,
    ) -> dict[str, Any]:
        """Create a vote on a proposal."""
        return {
            "proposal": proposal,
            "voter": self.node_id,
            "vote": vote,
            "signature": signature,
        }

    @staticmethod
    def sign(data: bytes, private_key: bytes) -> bytes:
        """Sign ``data`` with a raw 32-byte Ed25519 private key."""
        if not _ED25519_AVAILABLE or Ed25519PrivateKey is None:
            msg = "cryptography Ed25519 not available"
            raise RuntimeError(msg)
        if len(private_key) != 32:
            msg = "Ed25519 private key must be 32 bytes"
            raise ValueError(msg)
        key = Ed25519PrivateKey.from_private_bytes(private_key)
        return key.sign(data)

    def verify_signature(
        self,
        data: bytes,
        signature: bytes,
        public_key: bytes,
        node_id: str,
    ) -> bool:
        """Verify Ed25519 signature; reject anything that is not a valid verify."""
        if not _ED25519_AVAILABLE or Ed25519PublicKey is None:
            logger.error("Ed25519 unavailable; rejecting signature")
            return False
        if len(signature) != 64 or len(public_key) != 32:
            return False
        # Prefer allowlist key when registered for this node.
        expected = self.signatures.get(node_id, public_key)
        if expected != public_key and node_id in self.signatures:
            public_key = expected
        self.signatures[node_id] = public_key
        try:
            key = Ed25519PublicKey.from_public_bytes(public_key)
            key.verify(signature, data)
            return True
        except Exception:
            logger.debug("Ed25519 signature verification failed for %s", node_id)
            return False

    def aggregate_votes(
        self,
        votes: list[dict[str, Any]],
    ) -> tuple[bool, float, dict[str, bool]]:
        """Aggregate vote dicts and check consensus.

        Args:
            votes: List of vote dictionaries with ``voter`` / ``vote``
                (optional ``weight`` when weighted voting is enabled)

        Returns:
            Tuple of (consensus_reached, agreement_ratio, vote_dict)

        """
        vote_dict: dict[str, bool] = {}
        weights: dict[str, float] = {}

        for vote_data in votes:
            voter_id = vote_data.get("voter")
            vote_value = vote_data.get("vote")

            if voter_id and isinstance(vote_value, bool):
                vote_dict[str(voter_id)] = vote_value

                if self.weighted_voting:
                    if "weight" in vote_data:
                        weights[str(voter_id)] = float(vote_data["weight"])
                    elif voter_id in self.node_weights:
                        weights[str(voter_id)] = self.node_weights[voter_id]

        consensus_reached, agreement_ratio = self.check_byzantine_threshold(
            vote_dict, weights if self.weighted_voting else None
        )

        return consensus_reached, agreement_ratio, vote_dict

    def check_byzantine_threshold(
        self,
        votes: dict[str, bool],
        weights: Optional[dict[str, float]] = None,
    ) -> tuple[bool, float]:
        """Check if consensus threshold is met with Byzantine fault tolerance.

        Empty vote sets never reach consensus (no zero-peers-applies-immediately).
        When cluster_size was set at init, requires at least ``2f+1`` yes votes.
        """
        if not votes:
            return False, 0.0

        if self._quorum is not None:
            yes_votes = sum(1 for v in votes.values() if v)
            agreement_ratio = yes_votes / max(len(votes), 1)
            return yes_votes >= self._quorum, agreement_ratio

        if self.weighted_voting and weights:
            total_weight = sum(weights.values())
            if total_weight == 0:
                return False, 0.0
            yes_weight = sum(
                weights.get(node_id, 1.0) for node_id, vote in votes.items() if vote
            )
            agreement_ratio = yes_weight / total_weight
        else:
            yes_votes = sum(1 for vote in votes.values() if vote)
            total_votes = len(votes)
            agreement_ratio = yes_votes / total_votes if total_votes else 0.0

        required_ratio = 1.0 - self.fault_threshold
        consensus_reached = agreement_ratio > required_ratio
        return consensus_reached, agreement_ratio

    def get_required_quorum(self) -> Optional[int]:
        """Return configured ``2f+1`` quorum size, or None if unset."""
        return self._quorum
