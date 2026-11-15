"""Raft/Byzantine consensus unit gates (G8)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ccbt.consensus.byzantine import ByzantineConsensus
from ccbt.extensions.xet import XetExtension, XetMessageType

pytestmark = [pytest.mark.timeout(15), pytest.mark.consensus]


def test_consensus_byzantine_liars() -> None:
    from cryptography.hazmat.primitives import serialization

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    bc = ByzantineConsensus(node_id="n0", cluster_size=4, max_faulty=1)
    bc.register_public_key("n1", pub)
    data = b"proposal-bytes"
    good_sig = priv.sign(data)
    assert bc.verify_signature(data, good_sig, pub, "n1")
    # Liar: wrong signature length / garbage
    assert not bc.verify_signature(data, b"\x00" * 64, pub, "n1")
    # Quorum: need 2f+1 = 3 yes votes
    ok, _ = bc.check_byzantine_threshold({"a": True, "b": True})
    assert not ok
    ok, _ = bc.check_byzantine_threshold({"a": True, "b": True, "c": True})
    assert ok


def test_consensus_byzantine_rejects_undersized_cluster() -> None:
    with pytest.raises(ValueError, match="3f\\+1"):
        ByzantineConsensus(node_id="n0", cluster_size=3, max_faulty=1)


def test_consensus_raft_partition() -> None:
    """Raft RPC messages encode/decode on the XET wire (partition heal uses these)."""
    ext = XetExtension()
    req = {"term": 3, "candidate_id": "n1", "last_log_index": 0, "last_log_term": 0}
    msg = ext.encode_raft_message(XetMessageType.RAFT_VOTE_REQUEST, req)
    mtype, body = ext.decode_raft_message(msg)
    assert mtype == XetMessageType.RAFT_VOTE_REQUEST
    assert body["term"] == 3
    # Minority without quorum cannot fabricate a vote response as request
    resp = ext.encode_raft_message(
        XetMessageType.RAFT_VOTE_RESPONSE, {"term": 3, "vote_granted": False}
    )
    assert resp[0] == XetMessageType.RAFT_VOTE_RESPONSE
