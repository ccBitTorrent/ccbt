"""Tests for Bencoding implementation.
"""

import pytest

from ccbt.bencode import (
    BencodeDecodeError,
    BencodeDecoder,
    BencodeEncodeError,
    BencodeEncoder,
    decode,
    encode,
)


class TestBencodeDecoder:
    """Test cases for BencodeDecoder."""

    def test_decode_string(self):
        """Test decoding bencoded strings."""
        # Simple string
        decoder = BencodeDecoder(b"6:coding")
        assert decoder.decode() == b"coding"

        # Empty string
        decoder = BencodeDecoder(b"0:")
        assert decoder.decode() == b""

        # String with special characters
        decoder = BencodeDecoder(b"11:hello world")
        assert decoder.decode() == b"hello world"

    def test_decode_integer(self):
        """Test decoding bencoded integers."""
        # Positive integer
        decoder = BencodeDecoder(b"i100e")
        assert decoder.decode() == 100

        # Zero
        decoder = BencodeDecoder(b"i0e")
        assert decoder.decode() == 0

        # Negative integer
        decoder = BencodeDecoder(b"i-50e")
        assert decoder.decode() == -50

        # Large integer
        decoder = BencodeDecoder(b"i999999999999999999999e")
        assert decoder.decode() == 999999999999999999999

    def test_decode_list(self):
        """Test decoding bencoded lists."""
        # Simple list
        decoder = BencodeDecoder(b"l6:Coding10:Challengese")
        expected = [b"Coding", b"Challenges"]
        assert decoder.decode() == expected

        # Empty list
        decoder = BencodeDecoder(b"le")
        assert decoder.decode() == []

        # Mixed types
        decoder = BencodeDecoder(b"l6:codingi100e0:lee")
        expected = [b"coding", 100, b"", []]
        assert decoder.decode() == expected

    def test_decode_dict(self):
        """Test decoding bencoded dictionaries."""
        # Simple dictionary
        decoder = BencodeDecoder(
            b"d6:Coding10:Challenges8:website:20:codingchallenges.fyie",
        )
        expected = {
            b"Coding": b"Challenges",
            b"website:": b"codingchallenges.fyi",
        }
        assert decoder.decode() == expected

        # Empty dictionary
        decoder = BencodeDecoder(b"de")
        assert decoder.decode() == {}

        # Nested dictionary
        decoder = BencodeDecoder(
            b"d17:Coding Challengesd6:Rating7:Awesome8:website:20:codingchallenges.fyieee",
        )
        expected = {
            b"Coding Challenges": {
                b"Rating": b"Awesome",
                b"website:": b"codingchallenges.fyi",
            },
        }
        assert decoder.decode() == expected

    def test_decode_errors(self):
        """Test decoding error cases."""
        # Invalid integer (no 'e')
        decoder = BencodeDecoder(b"i100")
        with pytest.raises(BencodeDecodeError):
            decoder.decode()

        # Invalid integer (leading zero)
        decoder = BencodeDecoder(b"i03e")
        with pytest.raises(BencodeDecodeError):
            decoder.decode()

        # Invalid negative integer
        decoder = BencodeDecoder(b"i-e")
        with pytest.raises(BencodeDecodeError):
            decoder.decode()

        # Missing colon in string
        decoder = BencodeDecoder(b"6coding")
        with pytest.raises(BencodeDecodeError):
            decoder.decode()

        # Invalid string length
        decoder = BencodeDecoder(b"6:code")  # Only 4 chars but claims 6
        with pytest.raises(BencodeDecodeError):
            decoder.decode()

    def test_decode_complex_nested(self):
        """Test complex nested structures."""
        # Complex nested structure like torrent file
        data = b"d8:announce40:http://tracker.example.com:6969/announce7:comment12:Test torrente"
        decoder = BencodeDecoder(data)
        result = decoder.decode()

        expected = {
            b"announce": b"http://tracker.example.com:6969/announce",
            b"comment": b"Test torrent",
        }
        assert result == expected


class TestBencodeEncoder:
    """Test cases for BencodeEncoder."""

    def test_encode_string(self):
        """Test encoding strings."""
        encoder = BencodeEncoder()

        # Simple string
        assert encoder.encode(b"coding") == b"6:coding"

        # Empty string
        assert encoder.encode(b"") == b"0:"

        # String with special characters
        assert encoder.encode(b"hello world") == b"11:hello world"

    def test_encode_integer(self):
        """Test encoding integers."""
        encoder = BencodeEncoder()

        # Positive integer
        assert encoder.encode(100) == b"i100e"

        # Zero
        assert encoder.encode(0) == b"i0e"

        # Negative integer
        assert encoder.encode(-50) == b"i-50e"

        # Large integer
        assert encoder.encode(999999999999999999999) == b"i999999999999999999999e"

    def test_encode_list(self):
        """Test encoding lists."""
        encoder = BencodeEncoder()

        # Simple list
        assert encoder.encode([b"Coding", b"Challenges"]) == b"l6:Coding10:Challengese"

        # Empty list
        assert encoder.encode([]) == b"le"

        # Mixed types
        assert encoder.encode([b"coding", 100, b"", []]) == b"l6:codingi100e0:lee"

    def test_encode_dict(self):
        """Test encoding dictionaries."""
        encoder = BencodeEncoder()

        # Simple dictionary
        data = {
            b"Coding": b"Challenges",
            b"website:": b"codingchallenges.fyi",
        }
        result = encoder.encode(data)
        assert result == b"d6:Coding10:Challenges8:website:20:codingchallenges.fyie"

        # Empty dictionary
        assert encoder.encode({}) == b"de"

        # Nested dictionary
        data = {
            b"Coding Challenges": {
                b"Rating": b"Awesome",
                b"website:": b"codingchallenges.fyi",
            },
        }
        result = encoder.encode(data)
        expected = b"d17:Coding Challengesd6:Rating7:Awesome8:website:20:codingchallenges.fyiee"
        assert result == expected

    def test_encode_string_keys(self):
        """Test encoding dictionaries with string keys."""
        encoder = BencodeEncoder()

        # String keys should be encoded as bytes
        data = {
            "Coding": "Challenges",
            "website:": "codingchallenges.fyi",
        }
        result = encoder.encode(data)
        expected = b"d6:Coding10:Challenges8:website:20:codingchallenges.fyie"
        assert result == expected

    def test_encode_key_ordering(self):
        """Test that dictionary keys are properly sorted."""
        encoder = BencodeEncoder()

        # Keys should be in lexicographical order
        data = {b"zebra": 1, b"apple": 2, b"banana": 3}
        result = encoder.encode(data)
        # Should be sorted: apple, banana, zebra
        expected = b"d5:applei2e6:bananai3e5:zebrai1ee"
        assert result == expected

    def test_encode_errors(self):
        """Test encoding error cases."""
        encoder = BencodeEncoder()

        # Invalid type
        with pytest.raises(BencodeEncodeError):
            encoder.encode(3.14)  # Float not supported

        # Invalid dictionary key type
        with pytest.raises(BencodeEncodeError):
            encoder.encode({123: "value"})  # Integer key not allowed


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_decode_function(self):
        """Test decode() convenience function."""
        # String
        assert decode(b"6:coding") == b"coding"

        # Integer
        assert decode(b"i100e") == 100

        # List
        assert decode(b"l6:Coding10:Challengese") == [b"Coding", b"Challenges"]

        # Dictionary
        data = {b"test": b"value"}
        assert decode(encode(data)) == data

    def test_encode_function(self):
        """Test encode() convenience function."""
        # String
        assert encode(b"coding") == b"6:coding"

        # Integer
        assert encode(100) == b"i100e"

        # List
        assert encode([b"Coding", b"Challenges"]) == b"l6:Coding10:Challengese"

        # Dictionary
        data = {b"test": b"value"}
        assert encode(data) == b"d4:test5:valuee"


class TestRoundTrip:
    """Test that encode(decode(x)) == x and decode(encode(x)) == x."""

    def test_string_roundtrip(self):
        """Test string roundtrip."""
        original = b"hello world"
        assert decode(encode(original)) == original

    def test_integer_roundtrip(self):
        """Test integer roundtrip."""
        original = 42
        assert decode(encode(original)) == original

    def test_list_roundtrip(self):
        """Test list roundtrip."""
        original = [b"test", 123, [b"nested"]]
        assert decode(encode(original)) == original

    def test_dict_roundtrip(self):
        """Test dictionary roundtrip."""
        original = {
            b"string": b"value",
            b"integer": 42,
            b"list": [b"item1", b"item2"],
            b"nested": {b"key": b"value"},
        }
        assert decode(encode(original)) == original
