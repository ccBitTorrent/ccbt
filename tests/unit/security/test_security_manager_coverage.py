"""Additional tests for security_manager.py to achieve 100% coverage."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]

from ccbt.security.security_manager import PeerReputation, SecurityManager, ThreatType


class TestPeerReputation:
    """Test PeerReputation coverage gaps."""

    def test_update_reputation_failed_connection(self):
        """Test update_reputation with failed connection (line 81)."""
        reputation = PeerReputation(
            peer_id="test_peer",
            ip="192.168.1.100",
            reputation_score=0.5,
        )

        initial_score = reputation.reputation_score
        initial_failed = reputation.failed_connections

        # Update with failed connection
        reputation.update_reputation(success=False)

        # Should increment failed_connections and decrease reputation
        assert reputation.failed_connections == initial_failed + 1
        assert reputation.reputation_score < initial_score
        assert reputation.reputation_score >= 0.0  # Should be clamped to 0.0
