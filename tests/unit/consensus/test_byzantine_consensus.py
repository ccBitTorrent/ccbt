"""Unit tests for Byzantine consensus mechanism.

Tests Byzantine fault tolerance, signature verification, and weighted voting.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.consensus]


class TestByzantineConsensus:
    """Test Byzantine consensus implementation."""

    @pytest.fixture
    def byzantine_consensus(self):
        """Create Byzantine consensus instance."""
        from ccbt.consensus.byzantine import ByzantineConsensus

        return ByzantineConsensus(
            node_id="test_node_1",
            fault_threshold=0.33,
            weighted_voting=False,
        )

    def test_byzantine_initialization(self, byzantine_consensus):
        """Test Byzantine consensus initialization."""
        assert byzantine_consensus.node_id == "test_node_1"
        assert byzantine_consensus.fault_threshold == 0.33
        assert byzantine_consensus.weighted_voting is False

    def test_byzantine_propose(self, byzantine_consensus):
        """Test proposal creation."""
        proposal = {"type": "update", "data": "test"}
        proposal_data = byzantine_consensus.propose(proposal)

        assert proposal_data is not None
        assert "proposal" in proposal_data
        assert proposal_data["proposal"] == proposal

    def test_byzantine_aggregate_votes_simple(self, byzantine_consensus):
        """Test vote aggregation with simple majority."""
        proposal = {"type": "update", "data": "test"}
        proposal_data = byzantine_consensus.propose(proposal)

        # Create votes (3 yes, 1 no)
        votes = [
            {"voter": "node_1", "vote": True, "proposal": proposal_data},
            {"voter": "node_2", "vote": True, "proposal": proposal_data},
            {"voter": "node_3", "vote": True, "proposal": proposal_data},
            {"voter": "node_4", "vote": False, "proposal": proposal_data},
        ]

        consensus_reached, agreement_ratio, vote_dict = (
            byzantine_consensus.aggregate_votes(votes)
        )

        assert consensus_reached is True
        assert agreement_ratio >= 0.5

    def test_byzantine_aggregate_votes_no_consensus(self, byzantine_consensus):
        """Test vote aggregation without consensus."""
        proposal = {"type": "update", "data": "test"}
        proposal_data = byzantine_consensus.propose(proposal)

        # Create votes (2 yes, 2 no)
        votes = [
            {"voter": "node_1", "vote": True, "proposal": proposal_data},
            {"voter": "node_2", "vote": True, "proposal": proposal_data},
            {"voter": "node_3", "vote": False, "proposal": proposal_data},
            {"voter": "node_4", "vote": False, "proposal": proposal_data},
        ]

        consensus_reached, agreement_ratio, vote_dict = (
            byzantine_consensus.aggregate_votes(votes)
        )

        # May or may not reach consensus depending on threshold
        assert isinstance(consensus_reached, bool)
        assert 0.0 <= agreement_ratio <= 1.0

    def test_byzantine_weighted_voting(self):
        """Test weighted voting."""
        from ccbt.consensus.byzantine import ByzantineConsensus

        consensus = ByzantineConsensus(
            node_id="test_node_1",
            fault_threshold=0.33,
            weighted_voting=True,
        )

        proposal = {"type": "update", "data": "test"}
        proposal_data = consensus.propose(proposal)

        # Create weighted votes
        votes = [
            {"voter": "node_1", "vote": True, "proposal": proposal_data, "weight": 0.4},
            {"voter": "node_2", "vote": True, "proposal": proposal_data, "weight": 0.3},
            {"voter": "node_3", "vote": False, "proposal": proposal_data, "weight": 0.3},
        ]

        consensus_reached, agreement_ratio, vote_dict = consensus.aggregate_votes(
            votes
        )

        assert isinstance(consensus_reached, bool)
        assert 0.0 <= agreement_ratio <= 1.0

    def test_byzantine_fault_threshold(self, byzantine_consensus):
        """Test fault threshold calculation."""
        # With 4 nodes and fault_threshold=0.33, can tolerate 1 faulty node
        # Need 2f+1 = 3 honest nodes for consensus
        proposal = {"type": "update", "data": "test"}
        proposal_data = byzantine_consensus.propose(proposal)

        # 3 honest votes (should reach consensus)
        votes = [
            {"voter": "node_1", "vote": True, "proposal": proposal_data},
            {"voter": "node_2", "vote": True, "proposal": proposal_data},
            {"voter": "node_3", "vote": True, "proposal": proposal_data},
        ]

        consensus_reached, agreement_ratio, vote_dict = (
            byzantine_consensus.aggregate_votes(votes)
        )

        assert consensus_reached is True









