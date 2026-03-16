"""Unit tests for BEP 44 server (incoming get/put and BEP 5 handlers)."""

from __future__ import annotations

import socket
import time
from unittest.mock import MagicMock, patch

import pytest

from ccbt.core.bencode import BencodeDecoder, BencodeEncoder
from ccbt.discovery.dht import AsyncDHTClient, DHTNode
from ccbt.discovery.dht_storage import (
    calculate_immutable_key,
    calculate_mutable_key,
    sign_mutable_data,
)

pytestmark = [pytest.mark.unit]


def _mock_config(storage_enabled: bool = True, max_storage_size: int | None = 1000):
    """Build a mock config with discovery.dht_enable_storage and dht_max_storage_size."""
    discovery = MagicMock()
    discovery.dht_enable_storage = storage_enabled
    discovery.dht_max_storage_size = max_storage_size
    config = MagicMock()
    config.discovery = discovery
    return config


def _encode_query(q: bytes, a: dict, t: bytes = b"\x00\x01") -> bytes:
    """Build bencoded request message y=q."""
    msg = {b"y": b"q", b"q": q, b"a": a, b"t": t}
    return BencodeEncoder().encode(msg)


def _decode_response(data: bytes) -> dict:
    """Decode bencoded response from sendto payload."""
    return BencodeDecoder(data).decode()


class TestHandleDatagramGet:
    """handle_datagram with get request."""

    def test_handle_datagram_get_valid(self):
        """Get with valid target: response has token, nodes, nodes6; v if key in store."""
        client = AsyncDHTClient()
        client.transport = MagicMock()
        target = b"\x00" * 20
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            msg = _encode_query(b"get", {b"id": b"\x02" * 20, b"target": target})
            client.handle_datagram(msg, ("1.2.3.4", 6881))

        assert client.transport.sendto.call_count == 1
        payload, addr = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp.get(b"y") == b"r"
        r = resp.get(b"r", {})
        assert b"token" in r
        assert b"nodes" in r
        assert b"nodes6" in r
        assert b"v" not in r

    def test_handle_datagram_get_valid_with_value_in_store(self):
        """Get when target is in _xet_mutable_store: response includes v."""
        client = AsyncDHTClient()
        client.transport = MagicMock()
        target = b"\x00" * 20
        client._xet_mutable_store[target] = b"stored_value"
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            msg = _encode_query(b"get", {b"id": b"\x02" * 20, b"target": target})
            client.handle_datagram(msg, ("1.2.3.4", 6881))

        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp[b"r"].get(b"v") == b"stored_value"

    def test_handle_datagram_get_invalid_target(self):
        """Get with missing or wrong-length target: error 203."""
        client = AsyncDHTClient()
        client.transport = MagicMock()

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            msg = _encode_query(b"get", {b"id": b"\x02" * 20, b"target": b"short"})
            client.handle_datagram(msg, ("1.2.3.4", 6881))

        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp.get(b"y") == b"e"
        assert resp.get(b"e", [0, b""])[0] == 203


class TestHandleDatagramPut:
    """handle_datagram with put request."""

    def test_handle_datagram_put_immutable(self):
        """Put with valid token (from prior get), immutable value: store updated, success sent."""
        client = AsyncDHTClient()
        client.read_only = False
        client.transport = MagicMock()
        value = b"hello"
        target = calculate_immutable_key(value)
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))
        addr = ("1.2.3.4", 6881)

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            get_msg = _encode_query(b"get", {b"id": b"\x02" * 20, b"target": target})
            client.handle_datagram(get_msg, addr)
            payload, _ = client.transport.sendto.call_args[0]
            get_resp = _decode_response(payload)
            token = get_resp[b"r"][b"token"]

        put_msg = _encode_query(
            b"put",
            {
                b"id": b"\x02" * 20,
                b"token": token,
                b"v": value,
            },
        )
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client.handle_datagram(put_msg, addr)

        assert client._xet_mutable_store.get(target) == value
        assert client.transport.sendto.call_count >= 2
        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp.get(b"y") == b"r" and b"r" in resp


class TestHandlePutErrors:
    """_handle_put_request error paths."""

    def test_put_without_token(self):
        """Put without token: error 203."""
        client = AsyncDHTClient()
        client.read_only = False
        client.transport = MagicMock()
        a = {b"id": b"\x00" * 20, b"v": b"x"}
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client._handle_put_request(a, b"t1", ("1.2.3.4", 6881))
        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp[b"e"][0] == 203

    def test_put_wrong_token(self):
        """Put with wrong token: error 203 (token not issued for this addr/key)."""
        client = AsyncDHTClient()
        client.read_only = False
        client.transport = MagicMock()
        value = b"v"
        key = calculate_immutable_key(value)
        a = {
            b"id": b"\x00" * 20,
            b"token": b"wrong_token_32_bytes!!!!!!!!!!!!!!",
            b"v": value,
        }
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client._handle_put_request(a, b"t1", ("1.2.3.4", 6881))
        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp[b"e"][0] == 203

    def test_put_value_too_big(self):
        """Put value larger than dht_max_storage_size: error 205."""
        client = AsyncDHTClient()
        client.read_only = False
        client.transport = MagicMock()
        target = b"\x00" * 20
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))
        addr = ("1.2.3.4", 6881)

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config(max_storage_size=10)):
            get_msg = _encode_query(b"get", {b"id": b"\x02" * 20, b"target": target})
            client.handle_datagram(get_msg, addr)
            get_resp = _decode_response(client.transport.sendto.call_args[0][0])
            token = get_resp[b"r"][b"token"]

        big_value = b"x" * 20
        put_msg = _encode_query(
            b"put",
            {b"id": b"\x02" * 20, b"token": token, b"v": big_value},
        )
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config(max_storage_size=10)):
            client.handle_datagram(put_msg, addr)

        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp.get(b"y") == b"e"
        assert resp[b"e"][0] == 205

    def test_put_mutable_invalid_signature(self):
        """Put mutable with invalid signature: error 206."""
        client = AsyncDHTClient()
        client.read_only = False
        client.transport = MagicMock()
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))
        addr = ("1.2.3.4", 6881)

        pub = b"\x00" * 32
        mutable_key = calculate_mutable_key(pub, b"")
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            get_msg = _encode_query(
                b"get", {b"id": b"\x02" * 20, b"target": mutable_key}
            )
            client.handle_datagram(get_msg, addr)
            get_resp = _decode_response(client.transport.sendto.call_args[0][0])
            token = get_resp[b"r"][b"token"]

        a_put = {
            b"id": b"\x02" * 20,
            b"token": token,
            b"k": pub,
            b"seq": 1,
            b"sig": b"\x00" * 64,
            b"v": b"data",
        }
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client._handle_put_request(a_put, b"t1", addr)

        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp[b"e"][0] == 206

    def test_put_mutable_seq_less_than_current(self):
        """Put mutable with seq <= stored: error 302."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        client = AsyncDHTClient()
        client.read_only = False
        client.transport = MagicMock()
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))
        addr = ("1.2.3.4", 6881)

        priv = ed25519.Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes_raw()
        priv_bytes = priv.private_bytes_raw()
        mutable_key = calculate_mutable_key(pub, b"")

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            get_msg = _encode_query(
                b"get", {b"id": b"\x02" * 20, b"target": mutable_key}
            )
            client.handle_datagram(get_msg, addr)
            get_resp = _decode_response(client.transport.sendto.call_args[0][0])
            token = get_resp[b"r"][b"token"]

        data = b"first"
        sig = sign_mutable_data(data, pub, priv_bytes, 1, b"")
        put1 = _encode_query(
            b"put",
            {
                b"id": b"\x02" * 20,
                b"token": token,
                b"k": pub,
                b"seq": 1,
                b"sig": sig,
                b"v": data,
            },
        )
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client.handle_datagram(put1, addr)

        # Second put with same seq (302)
        sig2 = sign_mutable_data(b"second", pub, priv_bytes, 1, b"")
        put2 = _encode_query(
            b"put",
            {
                b"id": b"\x02" * 20,
                b"token": token,
                b"k": pub,
                b"seq": 1,
                b"sig": sig2,
                b"v": b"second",
            },
        )
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client.handle_datagram(put2, addr)

        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp.get(b"y") == b"e"
        assert resp[b"e"][0] == 302

    def test_put_mutable_cas_mismatch(self):
        """Put mutable with cas != current seq: error 301."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        client = AsyncDHTClient()
        client.read_only = False
        client.transport = MagicMock()
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))
        addr = ("1.2.3.4", 6881)

        priv = ed25519.Ed25519PrivateKey.generate()
        pub = priv.public_key().public_bytes_raw()
        priv_bytes = priv.private_bytes_raw()
        mutable_key = calculate_mutable_key(pub, b"")

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            get_msg = _encode_query(
                b"get", {b"id": b"\x02" * 20, b"target": mutable_key}
            )
            client.handle_datagram(get_msg, addr)
            get_resp = _decode_response(client.transport.sendto.call_args[0][0])
            token = get_resp[b"r"][b"token"]

        # First put seq=1 so current seq is 1
        data1 = b"first"
        sig1 = sign_mutable_data(data1, pub, priv_bytes, 1, b"")
        put1 = _encode_query(
            b"put",
            {
                b"id": b"\x02" * 20,
                b"token": token,
                b"k": pub,
                b"seq": 1,
                b"sig": sig1,
                b"v": data1,
            },
        )
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client.handle_datagram(put1, addr)

        # Second put with seq=2 but cas=0 (current is 1) -> 301
        data2 = b"second"
        sig2 = sign_mutable_data(data2, pub, priv_bytes, 2, b"")
        put2 = _encode_query(
            b"put",
            {
                b"id": b"\x02" * 20,
                b"token": token,
                b"k": pub,
                b"seq": 2,
                b"sig": sig2,
                b"v": data2,
                b"cas": 0,
            },
        )
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client.handle_datagram(put2, addr)

        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp.get(b"y") == b"e"
        assert resp[b"e"][0] == 301


class TestHandlePutReadOnly:
    """read_only node rejects put."""

    def test_handle_put_read_only(self):
        """read_only: put sends 203 and does not update store."""
        client = AsyncDHTClient()
        client.read_only = True
        client.transport = MagicMock()
        target = b"\x00" * 20
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))
        addr = ("1.2.3.4", 6881)

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            get_msg = _encode_query(b"get", {b"id": b"\x02" * 20, b"target": target})
            client.handle_datagram(get_msg, addr)
            get_resp = _decode_response(client.transport.sendto.call_args[0][0])
            token = get_resp[b"r"][b"token"]

        value = b"x"
        key = calculate_immutable_key(value)
        put_msg = _encode_query(
            b"put",
            {b"id": b"\x02" * 20, b"token": token, b"v": value},
        )
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client.handle_datagram(put_msg, addr)

        assert key not in client._xet_mutable_store
        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp[b"e"][0] == 203


class TestHandleRequestStorageDisabled:
    """dht_enable_storage False: no response for get/put."""

    def test_handle_request_storage_disabled(self):
        """When dht_enable_storage False, get/put do not call sendto."""
        client = AsyncDHTClient()
        client.transport = MagicMock()

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config(storage_enabled=False)):
            msg = _encode_query(
                b"get",
                {b"id": b"\x02" * 20, b"target": b"\x00" * 20},
            )
            client.handle_datagram(msg, ("1.2.3.4", 6881))

        client.transport.sendto.assert_not_called()


class TestHandleFindNode:
    """BEP 5 find_node handler."""

    def test_handle_find_node(self):
        """find_node: response has id, nodes, nodes6."""
        client = AsyncDHTClient()
        client.transport = MagicMock()
        target = b"\x00" * 20
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            msg = _encode_query(
                b"find_node",
                {b"id": b"\x02" * 20, b"target": target},
            )
            client.handle_datagram(msg, ("1.2.3.4", 6881))

        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp.get(b"y") == b"r"
        r = resp[b"r"]
        assert b"id" in r
        assert b"nodes" in r
        assert b"nodes6" in r


class TestHandleGetPeers:
    """BEP 5 get_peers handler."""

    def test_handle_get_peers(self):
        """get_peers: response has token, nodes, nodes6; values if store has peers."""
        client = AsyncDHTClient()
        client.transport = MagicMock()
        info_hash = b"\x00" * 20
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            msg = _encode_query(
                b"get_peers",
                {b"id": b"\x02" * 20, b"info_hash": info_hash},
            )
            client.handle_datagram(msg, ("1.2.3.4", 6881))

        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp.get(b"y") == b"r"
        r = resp[b"r"]
        assert b"token" in r
        assert b"nodes" in r
        assert b"nodes6" in r


class TestHandleAnnouncePeer:
    """BEP 5 announce_peer handler."""

    def test_handle_announce_peer(self):
        """After get_peers, announce_peer with token and port: _peers_store updated, success."""
        client = AsyncDHTClient()
        client.transport = MagicMock()
        info_hash = b"\x00" * 20
        client.routing_table.add_node(DHTNode(b"\x01" * 20, "127.0.0.1", 6881))
        addr = ("1.2.3.4", 6881)

        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            get_msg = _encode_query(
                b"get_peers",
                {b"id": b"\x02" * 20, b"info_hash": info_hash},
            )
            client.handle_datagram(get_msg, addr)
            get_resp = _decode_response(client.transport.sendto.call_args[0][0])
            token = get_resp[b"r"][b"token"]

        announce_msg = _encode_query(
            b"announce_peer",
            {
                b"id": b"\x02" * 20,
                b"info_hash": info_hash,
                b"token": token,
                b"port": 9999,
            },
        )
        with patch("ccbt.discovery.dht.get_config", return_value=_mock_config()):
            client.handle_datagram(announce_msg, addr)

        assert info_hash in client._peers_store
        assert ("1.2.3.4", 9999) in client._peers_store[info_hash]
        payload, _ = client.transport.sendto.call_args[0]
        resp = _decode_response(payload)
        assert resp.get(b"y") == b"r"


class TestCleanupExpiredServerTokens:
    """_cleanup_old_data expires server token dicts."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_server_tokens(self):
        """Expired _storage_write_tokens and _get_peers_tokens are removed."""
        client = AsyncDHTClient()
        addr = ("1.2.3.4", 6881)
        target = b"\x00" * 20
        token = b"t" * 32
        client._storage_write_tokens[(addr, target)] = (token, time.time() - 100)
        client._get_peers_tokens[(addr, b"\x01" * 20)] = (token, time.time() - 100)

        await client._cleanup_old_data()

        assert (addr, target) not in client._storage_write_tokens
        assert (addr, b"\x01" * 20) not in client._get_peers_tokens


class TestBuildCompactNodesIPv6:
    """_build_compact_nodes returns nodes6 when table has IPv6."""

    def test_build_compact_nodes_ipv6(self):
        """When routing table has node with ipv6/port6, nodes6 is non-empty (38 bytes per node)."""
        client = AsyncDHTClient()
        node_id = b"\x01" * 20
        node = DHTNode(node_id, "127.0.0.1", 6881)
        node.ipv6 = "::1"
        node.port6 = 6882
        node.has_ipv6 = True
        client.routing_table.add_node(node)

        nodes, nodes6 = client._build_compact_nodes(b"\x00" * 20, count=8)

        assert len(nodes6) == 38
        assert node_id in nodes6
        assert socket.inet_pton(socket.AF_INET6, "::1") in nodes6
