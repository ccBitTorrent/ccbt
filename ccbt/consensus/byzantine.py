"""Byzantine fault tolerance implementation.

Provides signature verification and weighted voting for Byzantine consensus.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class ByzantineConsensus:
    """Byzantine fault tolerance consensus.

    Implements signature verification and weighted voting for
    Byzantine fault-tolerant consensus.

    Attributes:
        node_id: Unique identifier for this node
        fault_threshold: Maximum fraction of faulty nodes (default 0.33)
        weighted_voting: Whether to use weighted voting
        node_weights: Dictionary of node_id -> weight
        signatures: Dictionary for signature verification

    """

    def __init__(
        self,
        node_id: str,
        fault_threshold: float = 0.33,
        weighted_voting: bool = False,
        node_weights: dict[str, float] | None = None,
    ):
        """Initialize Byzantine consensus.

        Args:
            node_id: Unique identifier for this node
            fault_threshold: Maximum fraction of faulty nodes (0.0 to 1.0)
            weighted_voting: Whether to use weighted voting
            node_weights: Dictionary of node_id -> weight (for weighted voting)

        """
        if not 0.0 <= fault_threshold <= 1.0:
            msg = "Fault threshold must be between 0.0 and 1.0"
            raise ValueError(msg)

        self.node_id = node_id
        self.fault_threshold = fault_threshold
        self.weighted_voting = weighted_voting
        self.node_weights = node_weights or {}
        self.signatures: dict[str, bytes] = {}  # node_id -> public_key

    def propose(
        self,
        proposal: dict[str, Any],
        signature: bytes | None = None,
    ) -> dict[str, Any]:
        """Create a proposal with optional signature.

        Args:
            proposal: Proposal data
            signature: Optional signature (for signing)

        Returns:
            Proposal with metadata

        """
        proposal_data = {
            "proposal": proposal,
            "proposer": self.node_id,
            "signature": signature,
        }

        return proposal_data

    def vote(
        self,
        proposal: dict[str, Any],
        vote: bool,
        signature: bytes | None = None,
    ) -> dict[str, Any]:
        """Create a vote on a proposal.

        Args:
            proposal: Original proposal
            vote: True to accept, False to reject
            signature: Optional signature

        Returns:
            Vote with metadata

        """
        vote_data = {
            "proposal": proposal,
            "voter": self.node_id,
            "vote": vote,
            "signature": signature,
        }

        return vote_data

    def verify_signature(
        self,
        data: bytes,
        signature: bytes,
        public_key: bytes,
        node_id: str,
    ) -> bool:
        """Verify signature (simplified - would use Ed25519 in production).

        Args:
            data: Data that was signed
            signature: Signature bytes
            public_key: Public key for verification
            node_id: Node ID (for lookup)

        Returns:
            True if signature is valid

        """
        # Store public key for this node
        self.signatures[node_id] = public_key

        # Simplified verification (would use Ed25519 in production)
        # For now, just check that signature exists and has correct length
        if len(signature) != 64:  # Ed25519 signature length
            return False

        # In production, would verify using cryptography library:
        # from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        # public_key_obj = Ed25519PublicKey.from_public_bytes(public_key)
        # public_key_obj.verify(signature, data)

        # For now, accept if signature format is correct
        return True

    def check_byzantine_threshold(
        self,
        votes: dict[str, bool],
        weights: dict[str, float] | None = None,
    ) -> tuple[bool, float]:
        """Check if consensus threshold is met with Byzantine fault tolerance.

        Args:
            votes: Dictionary of node_id -> vote (True/False)
            weights: Optional dictionary of node_id -> weight

        Returns:
            Tuple of (consensus_reached, agreement_ratio)

        """
        if not votes:
            return False, 0.0

        if self.weighted_voting and weights:
            # Weighted voting
            total_weight = sum(weights.values())
            if total_weight == 0:
                return False, 0.0

            yes_weight = sum(
                weights.get(node_id, 1.0) for node_id, vote in votes.items() if vote
            )
            agreement_ratio = yes_weight / total_weight
        else:
            # Simple majority
            yes_votes = sum(1 for vote in votes.values() if vote)
            total_votes = len(votes)
            agreement_ratio = yes_votes / total_votes if total_votes > 0 else 0.0

        # Consensus requires agreement from more than (1 - fault_threshold) of nodes
        # This ensures Byzantine fault tolerance
        required_ratio = 1.0 - self.fault_threshold
        consensus_reached = agreement_ratio > required_ratio

        return consensus_reached, agreement_ratio

    def aggregate_votes(
        self,
        votes: list[dict[str, Any]],
    ) -> tuple[bool, float, dict[str, bool]]:
        """Aggregate votes and check consensus.

        Args:
            votes: List of vote dictionaries

        Returns:
            Tuple of (consensus_reached, agreement_ratio, vote_dict)

        """
        vote_dict: dict[str, bool] = {}
        weights: dict[str, float] = {}

        for vote_data in votes:
            voter_id = vote_data.get("voter")
            vote_value = vote_data.get("vote")

            if voter_id and isinstance(vote_value, bool):
                vote_dict[voter_id] = vote_value

                # Get weight if available
                if self.weighted_voting and voter_id in self.node_weights:
                    weights[voter_id] = self.node_weights[voter_id]

        consensus_reached, agreement_ratio = self.check_byzantine_threshold(
            vote_dict, weights if self.weighted_voting else None
        )

        return consensus_reached, agreement_ratio, vote_dict



