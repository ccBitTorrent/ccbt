"""Unit tests for BEP 44 (DHT get/put) and related helpers."""

from __future__ import annotations

import pytest

from ccbt.discovery.dht import AsyncDHTClient
from ccbt.discovery.dht_storage import _bep44_signature_message

pytestmark = [pytest.mark.unit]


class TestBEP44SignatureMessage:
    """Test BEP 44 signature buffer format."""

    def test_bep44_signature_message_no_salt(self):
        """Buffer is 3:seqi<seq>e1:v<len>:<data> for no salt."""
        data = b"Hello World!"
        msg = _bep44_signature_message(data, seq=1, salt=b"")
        assert msg == b"3:seqi1e1:v12:Hello World!"

    def test_bep44_signature_message_with_salt(self):
        """Buffer includes 4:salt<len>:<salt> when salt non-empty."""
        data = b"Hello World!"
        msg = _bep44_signature_message(data, seq=1, salt=b"foobar")
        assert msg.startswith(b"4:salt6:foobar")
        assert b"3:seqi1e" in msg
        assert b"1:v12:Hello World!" in msg


class TestDHTXetChunkKey:
    """Test XET chunk DHT key derivation."""

    def test_xet_chunk_dht_key_32_bytes(self):
        """32-byte chunk hash becomes first 20 bytes."""
        client = AsyncDHTClient()
        chunk = b"a" * 32
        key = client._xet_chunk_dht_key(chunk)
        assert len(key) == 20
        assert key == b"a" * 20

    def test_xet_chunk_dht_key_short_padded(self):
        """Short hash is zero-padded to 20 bytes."""
        client = AsyncDHTClient()
        key = client._xet_chunk_dht_key(b"ab")
        assert len(key) == 20
        assert key == b"ab" + b"\x00" * 18


class TestDHTParseGetResponse:
    """Test _parse_get_response for immutable get."""

    @pytest.mark.asyncio
    async def test_parse_get_response_not_response(self):
        """Non-response message returns None."""
        client = AsyncDHTClient()
        msg = {b"y": b"q", b"q": b"get"}
        assert client._parse_get_response(msg, b"\x00" * 20) is None

    @pytest.mark.asyncio
    async def test_parse_get_response_no_value_returns_token_and_nodes(self):
        """Response with no v returns (None, token, nodes, nodes6)."""
        client = AsyncDHTClient()
        msg = {
            b"y": b"r",
            b"r": {
                b"id": b"\x00" * 20,
                b"token": b"tok",
                b"nodes": b"",
                b"nodes6": b"",
            },
        }
        result = client._parse_get_response(msg, b"\x00" * 20)
        assert result is not None
        value, token, nodes, nodes6 = result
        assert value is None
        assert token == b"tok"
        assert nodes == b""
        assert nodes6 == b""

    @pytest.mark.asyncio
    async def test_parse_get_response_immutable_valid(self):
        """Valid immutable value passes SHA-1 check."""
        from ccbt.discovery.dht_storage import calculate_immutable_key

        client = AsyncDHTClient()
        data = b"hello"
        key = calculate_immutable_key(data)
        msg = {
            b"y": b"r",
            b"r": {
                b"id": b"\x00" * 20,
                b"token": b"t",
                b"v": data,
                b"nodes": b"",
                b"nodes6": b"",
            },
        }
        result = client._parse_get_response(msg, key)
        assert result is not None
        value, token, _, _ = result
        assert value == data
        assert token == b"t"

    @pytest.mark.asyncio
    async def test_parse_get_response_immutable_wrong_key_rejected(self):
        """Immutable value with wrong key returns None."""
        client = AsyncDHTClient()
        msg = {
            b"y": b"r",
            b"r": {
                b"id": b"\x00" * 20,
                b"token": b"t",
                b"v": b"wrong",
                b"nodes": b"",
                b"nodes6": b"",
            },
        }
        # Target key that doesn't match SHA-1(b"wrong")
        target = b"\x00" * 20
        assert client._parse_get_response(msg, target) is None


class TestDHTPutDataBencode:
    """Test put_data encodes dict values with bencode for BEP 44 interoperability."""

    @pytest.mark.asyncio
    async def test_put_data_dict_stores_bencoded_value(self):
        """put_data with dict[bytes, bytes] stores bencoded bytes, not JSON."""
        from ccbt.core.bencode import BencodeDecoder

        client = AsyncDHTClient()
        key = b"\x01" * 20
        value_dict = {b"v": b"test data", b"k": b"extra"}
        result = await client.put_data(key=key, value=value_dict)
        assert result >= 1
        stored = client._xet_mutable_store.get(key)
        assert stored is not None
        # Must be bencoded (BEP 44): round-trip via BencodeDecoder
        decoded = BencodeDecoder(stored).decode()
        assert decoded == value_dict
        # Must not be JSON (would break cross-node key compatibility)
        assert not stored.lstrip().startswith(b"{")
