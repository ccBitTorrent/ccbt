"""Property-based tests for bencode encoding/decoding.

Tests invariants and properties of the bencode implementation
using Hypothesis for automatic test case generation.
"""

from hypothesis import given
from hypothesis import strategies as st

from ccbt.bencode import BencodeDecoder, decode, encode


class TestBencodeProperties:
    """Property-based tests for bencode operations."""

    @given(st.binary())
    def test_string_roundtrip(self, data):
        """Test that encoding and decoding binary data preserves it."""
        encoded = encode(data)
        decoded = decode(encoded)
        assert decoded == data

    @given(st.text())
    def test_text_encoding(self, text):
        """Test text encoding converts to bytes."""
        encoded = encode(text)
        decoded = decode(encoded)
        # Decoded value should be bytes
        assert isinstance(decoded, bytes)
        assert decoded.decode("utf-8") == text

    @given(st.integers())
    def test_integer_roundtrip(self, i):
        """Test that encoding and decoding an integer preserves it."""
        encoded = encode(i)
        decoded = decode(encoded)
        assert decoded == i

    @given(st.lists(st.binary()))
    def test_list_roundtrip(self, lst):
        """Test that encoding and decoding a list preserves it."""
        encoded = encode(lst)
        decoded = decode(encoded)
        assert decoded == lst

    @given(st.dictionaries(st.binary(), st.binary()))
    def test_dict_roundtrip(self, dct):
        """Test that encoding and decoding a dictionary preserves it."""
        encoded = encode(dct)
        decoded = decode(encoded)
        assert decoded == dct

    @given(
        st.one_of(
            st.binary(),
            st.integers(),
            st.lists(st.binary()),
            st.dictionaries(st.binary(), st.binary()),
        ),
    )
    def test_nested_roundtrip(self, obj):
        """Test that encoding and decoding nested structures preserves them."""
        encoded = encode(obj)
        decoded = decode(encoded)
        assert decoded == obj

    @given(st.binary())
    def test_binary_roundtrip(self, data):
        """Test that encoding and decoding binary data preserves it."""
        encoded = encode(data)
        decoded = decode(encoded)
        assert decoded == data

    @given(
        st.lists(
            st.one_of(
                st.binary(),
                st.integers(),
                st.lists(st.binary()),
                st.dictionaries(st.binary(), st.binary()),
            ),
        ),
    )
    def test_complex_list_roundtrip(self, lst):
        """Test that encoding and decoding complex lists preserves them."""
        encoded = encode(lst)
        decoded = decode(encoded)
        assert decoded == lst

    @given(
        st.dictionaries(
            st.binary(),
            st.one_of(
                st.binary(),
                st.integers(),
                st.lists(st.binary()),
                st.dictionaries(st.binary(), st.binary()),
            ),
        ),
    )
    def test_complex_dict_roundtrip(self, dct):
        """Test that encoding and decoding complex dictionaries preserves them."""
        encoded = encode(dct)
        decoded = decode(encoded)
        assert decoded == dct

    @given(st.binary())
    def test_string_encoding_properties(self, data):
        """Test properties of binary string encoding."""
        encoded = encode(data)

        # String should start with length and colon
        assert b":" in encoded
        colon_pos = encoded.find(b":")
        length_part = encoded[:colon_pos]

        # Length part should be valid integer
        length = int(length_part.decode("ascii"))
        assert length == len(data)

        # Data part should be the original data
        data_part = encoded[colon_pos + 1 :]
        assert data_part == data

    @given(st.integers())
    def test_integer_encoding_properties(self, i):
        """Test properties of integer encoding."""
        encoded = encode(i)

        # Integer should be wrapped in 'i' and 'e'
        assert encoded.startswith(b"i")
        assert encoded.endswith(b"e")

        # Inner part should be the integer as string
        inner = encoded[1:-1]
        assert inner == str(i).encode("ascii")

    @given(st.lists(st.binary()))
    def test_list_encoding_properties(self, lst):
        """Test properties of list encoding."""
        encoded = encode(lst)

        # List should be wrapped in 'l' and 'e'
        assert encoded.startswith(b"l")
        assert encoded.endswith(b"e")

    @given(st.dictionaries(st.binary(), st.binary()))
    def test_dict_encoding_properties(self, dct):
        """Test properties of dictionary encoding."""
        encoded = encode(dct)

        # Dictionary should be wrapped in 'd' and 'e'
        assert encoded.startswith(b"d")
        assert encoded.endswith(b"e")

    @given(st.binary())
    def test_decoder_position_invariant(self, data):
        """Test that decoder position is correctly maintained."""
        encoded = encode(data)
        decoder = BencodeDecoder(encoded)
        decoded = decoder.decode()

        # Position should be at end after decoding
        assert decoder.pos == len(encoded)
        assert decoded == data

    @given(st.lists(st.binary()))
    def test_decoder_position_list(self, lst):
        """Test that decoder position is correctly maintained for lists."""
        encoded = encode(lst)
        decoder = BencodeDecoder(encoded)
        decoded = decoder.decode()

        # Position should be at end after decoding
        assert decoder.pos == len(encoded)
        assert decoded == lst

    @given(st.dictionaries(st.binary(), st.binary()))
    def test_decoder_position_dict(self, dct):
        """Test that decoder position is correctly maintained for dictionaries."""
        encoded = encode(dct)
        decoder = BencodeDecoder(encoded)
        decoded = decoder.decode()

        # Position should be at end after decoding
        assert decoder.pos == len(encoded)
        assert decoded == dct

    @given(st.binary())
    def test_encoding_size_property(self, data):
        """Test that encoding size is reasonable."""
        encoded = encode(data)

        # Encoded size should be at least the data length plus overhead
        min_size = len(data) + len(str(len(data))) + 1  # length + colon
        assert len(encoded) >= min_size

    @given(st.integers())
    def test_integer_encoding_size(self, i):
        """Test that integer encoding size is reasonable."""
        encoded = encode(i)

        # Encoded size should be the integer string length plus 2 (i and e)
        expected_size = len(str(i)) + 2
        assert len(encoded) == expected_size

    @given(st.lists(st.binary()))
    def test_list_encoding_size(self, lst):
        """Test that list encoding size is reasonable."""
        encoded = encode(lst)

        # Encoded size should be at least the sum of element sizes plus overhead
        min_size = sum(len(encode(item)) for item in lst) + 2  # l and e
        assert len(encoded) >= min_size

    @given(st.dictionaries(st.binary(), st.binary()))
    def test_dict_encoding_size(self, dct):
        """Test that dictionary encoding size is reasonable."""
        encoded = encode(dct)

        # Encoded size should be at least the sum of key-value sizes plus overhead
        min_size = (
            sum(len(encode(k)) + len(encode(v)) for k, v in dct.items()) + 2
        )  # d and e
        assert len(encoded) >= min_size

    @given(st.binary())
    def test_string_encoding_consistency(self, data):
        """Test that binary encoding is consistent."""
        encoded1 = encode(data)
        encoded2 = encode(data)

        # Multiple encodings should be identical
        assert encoded1 == encoded2

    @given(st.integers())
    def test_integer_encoding_consistency(self, i):
        """Test that integer encoding is consistent."""
        encoded1 = encode(i)
        encoded2 = encode(i)

        # Multiple encodings should be identical
        assert encoded1 == encoded2

    @given(st.lists(st.binary()))
    def test_list_encoding_consistency(self, lst):
        """Test that list encoding is consistent."""
        encoded1 = encode(lst)
        encoded2 = encode(lst)

        # Multiple encodings should be identical
        assert encoded1 == encoded2

    @given(st.dictionaries(st.binary(), st.binary()))
    def test_dict_encoding_consistency(self, dct):
        """Test that dictionary encoding is consistent."""
        encoded1 = encode(dct)
        encoded2 = encode(dct)

        # Multiple encodings should be identical
        assert encoded1 == encoded2

    @given(st.binary())
    def test_string_decoding_robustness(self, data):
        """Test that binary decoding is robust."""
        encoded = encode(data)

        # Should decode successfully
        decoded = decode(encoded)
        assert decoded == data

        # Should handle empty data
        if data == b"":
            assert decoded == b""

    @given(st.integers())
    def test_integer_decoding_robustness(self, i):
        """Test that integer decoding is robust."""
        encoded = encode(i)

        # Should decode successfully
        decoded = decode(encoded)
        assert decoded == i

        # Should handle zero
        if i == 0:
            assert decoded == 0

    @given(st.lists(st.binary()))
    def test_list_decoding_robustness(self, lst):
        """Test that list decoding is robust."""
        encoded = encode(lst)

        # Should decode successfully
        decoded = decode(encoded)
        assert decoded == lst

        # Should handle empty lists
        if lst == []:
            assert decoded == []

    @given(st.dictionaries(st.binary(), st.binary()))
    def test_dict_decoding_robustness(self, dct):
        """Test that dictionary decoding is robust."""
        encoded = encode(dct)

        # Should decode successfully
        decoded = decode(encoded)
        assert decoded == dct

        # Should handle empty dictionaries
        if dct == {}:
            assert decoded == {}
