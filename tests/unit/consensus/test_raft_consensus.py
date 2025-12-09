"""Unit tests for Raft consensus mechanism.

Tests Raft leader election, log replication, and safety guarantees.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.consensus]


class TestRaftConsensus:
    """Test Raft consensus implementation."""

    @pytest.fixture
    def temp_state_dir(self):
        """Create temporary state directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def raft_node(self, temp_state_dir):
        """Create Raft node for testing."""
        from ccbt.consensus.raft import RaftNode

        state_path = temp_state_dir / "raft_state.json"
        node = RaftNode(
            node_id="test_node_1",
            state_path=state_path,
            election_timeout=2.0,
            heartbeat_interval=0.5,
            apply_command_callback=lambda cmd: None,
        )
        yield node
        # Cleanup
        try:
            asyncio.run(node.stop())
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_raft_node_initialization(self, raft_node):
        """Test Raft node initialization."""
        assert raft_node.node_id == "test_node_1"
        assert raft_node.election_timeout == 2.0
        assert raft_node.heartbeat_interval == 0.5

    @pytest.mark.asyncio
    async def test_raft_leader_election(self, raft_node):
        """Test Raft leader election."""
        # Start node
        await raft_node.start()

        # Wait for election
        await asyncio.sleep(3.0)

        # Node should become leader (single node cluster)
        assert raft_node.state == "leader"

        await raft_node.stop()

    @pytest.mark.asyncio
    async def test_raft_log_replication(self, raft_node):
        """Test Raft log replication."""
        await raft_node.start()

        # Wait for leader election
        await asyncio.sleep(3.0)

        # Append entry
        command = {"type": "update", "data": "test"}
        success = await raft_node.append_entry(command)

        assert success is True
        assert len(raft_node.log) > 0

        await raft_node.stop()

    @pytest.mark.asyncio
    async def test_raft_state_persistence(self, temp_state_dir, raft_node):
        """Test Raft state persistence."""
        from ccbt.consensus.raft_state import RaftState

        await raft_node.start()
        await asyncio.sleep(3.0)

        # Append entry
        command = {"type": "update", "data": "test"}
        await raft_node.append_entry(command)

        # Save state
        state = RaftState(
            current_term=raft_node.current_term,
            voted_for=raft_node.voted_for,
            log=raft_node.log,
        )
        state_path = temp_state_dir / "raft_state.json"
        state.save(state_path)

        # Verify file exists
        assert state_path.exists()

        # Load state
        loaded_state = RaftState.load(state_path)
        assert loaded_state.current_term == state.current_term
        assert len(loaded_state.log) == len(state.log)

        await raft_node.stop()

    @pytest.mark.asyncio
    async def test_raft_apply_command_callback(self, temp_state_dir):
        """Test Raft apply command callback."""
        applied_commands = []

        def apply_callback(cmd: dict) -> None:
            applied_commands.append(cmd)

        from ccbt.consensus.raft import RaftNode

        state_path = temp_state_dir / "raft_state.json"
        node = RaftNode(
            node_id="test_node_2",
            state_path=state_path,
            election_timeout=1.0,
            heartbeat_interval=0.3,
            apply_command_callback=apply_callback,
        )

        await node.start()
        await asyncio.sleep(2.0)

        # Append entry
        command = {"type": "update", "data": "test_callback"}
        await node.append_entry(command)

        # Wait for commit
        await asyncio.sleep(1.0)

        # Verify callback was called
        assert len(applied_commands) > 0
        assert applied_commands[-1]["data"] == "test_callback"

        await node.stop()

    @pytest.mark.asyncio
    async def test_raft_add_peer(self, raft_node):
        """Test adding peer to Raft cluster."""
        await raft_node.start()

        # Add peer
        raft_node.add_peer("peer_2")
        assert "peer_2" in raft_node.peers

        await raft_node.stop()

    @pytest.mark.asyncio
    async def test_raft_remove_peer(self, raft_node):
        """Test removing peer from Raft cluster."""
        await raft_node.start()

        # Add then remove peer
        raft_node.add_peer("peer_3")
        raft_node.remove_peer("peer_3")
        assert "peer_3" not in raft_node.peers

        await raft_node.stop()









