"""Bencoding implementation for BitTorrent protocol.

Bencoding is the encoding used in BitTorrent for torrent files and peer communication.
This module provides encoding and decoding functionality according to the BitTorrent specification.
"""

from typing import Any, Dict, List

from .exceptions import BencodeError


class BencodeDecodeError(BencodeError):
    """Exception raised when bencode decoding fails."""


class BencodeEncodeError(BencodeError):
    """Exception raised when bencode encoding fails."""


class BencodeDecoder:
    """Decoder for Bencoded data."""

    def __init__(self, data: bytes) -> None:
        """Initialize decoder with bencoded data."""
        self.data: bytes = data
        self.pos: int = 0

    def decode(self) -> Any:
        """Decode the bencoded data and return Python object."""
        if self.pos >= len(self.data):
            raise BencodeDecodeError("Unexpected end of data")

        char = chr(self.data[self.pos])

        if char == "i":
            result = self._decode_integer()
        elif char == "l":
            result = self._decode_list()
        elif char == "d":
            result = self._decode_dict()
        elif char.isdigit():
            result = self._decode_string()
        else:
            raise BencodeDecodeError(f"Invalid bencode character: {char}")

        return result

    def _decode_integer(self) -> int:
        """Decode a bencoded integer."""
        self.pos += 1  # Skip 'i'
        start = self.pos

        # Find the 'e' terminator
        while self.pos < len(self.data) and chr(self.data[self.pos]) != "e":
            self.pos += 1

        if self.pos >= len(self.data):
            raise BencodeDecodeError("Missing 'e' terminator for integer")

        # Extract the number string
        number_str = self.data[start:self.pos].decode("utf-8")
        self.pos += 1  # Skip 'e'

        # Handle negative numbers
        if number_str.startswith("-"):
            if len(number_str) == 1:
                raise BencodeDecodeError("Invalid negative integer")
            return -int(number_str[1:])
        if number_str.startswith("0") and len(number_str) > 1:
            raise BencodeDecodeError("Invalid integer with leading zero")
        return int(number_str)

    def _decode_string(self) -> bytes:
        """Decode a bencoded string."""
        # Find the colon
        start = self.pos
        while self.pos < len(self.data) and chr(self.data[self.pos]) != ":":
            self.pos += 1

        if self.pos >= len(self.data):
            raise BencodeDecodeError("Missing colon in string")

        # Extract length
        length_str = self.data[start:self.pos].decode("utf-8")
        try:
            length = int(length_str)
        except ValueError:
            raise BencodeDecodeError(f"Invalid string length: {length_str}")

        self.pos += 1  # Skip colon
        start = self.pos

        # Check if we have enough data
        if self.pos + length > len(self.data):
            raise BencodeDecodeError("String length exceeds available data")

        # Extract string data
        string_data = self.data[self.pos:self.pos + length]
        self.pos += length

        return string_data

    def _decode_list(self) -> List[Any]:
        """Decode a bencoded list."""
        self.pos += 1  # Skip 'l'
        result = []

        while self.pos < len(self.data) and chr(self.data[self.pos]) != "e":
            result.append(self.decode())

        if self.pos >= len(self.data):
            raise BencodeDecodeError("Missing 'e' terminator for list")

        self.pos += 1  # Skip 'e'
        return result

    def _decode_dict(self) -> Dict[bytes, Any]:
        """Decode a bencoded dictionary."""
        self.pos += 1  # Skip 'd'
        result = {}

        while self.pos < len(self.data) and chr(self.data[self.pos]) != "e":
            # Decode key (must be string)
            key = self._decode_string()

            # Decode value
            value = self.decode()

            result[key] = value

        if self.pos >= len(self.data):
            raise BencodeDecodeError("Missing 'e' terminator for dictionary")

        self.pos += 1  # Skip 'e'
        return result


class BencodeEncoder:
    """Encoder for Python objects to Bencoded data."""

    def encode(self, obj: Any) -> bytes:
        """Encode a Python object to bencoded data."""
        if isinstance(obj, bytes):
            return self._encode_string(obj)
        if isinstance(obj, str):
            return self._encode_string(obj.encode("utf-8"))
        if isinstance(obj, int):
            return self._encode_integer(obj)
        if isinstance(obj, list):
            return self._encode_list(obj)
        if isinstance(obj, dict):
            return self._encode_dict(obj)
        raise BencodeEncodeError(f"Cannot encode type: {type(obj)}")

    def _encode_string(self, data: bytes) -> bytes:
        """Encode bytes as bencoded string."""
        return f"{len(data)}:".encode() + data

    def _encode_integer(self, num: int) -> bytes:
        """Encode integer as bencoded integer."""
        return f"i{num}e".encode()

    def _encode_list(self, lst: List[Any]) -> bytes:
        """Encode list as bencoded list."""
        result = b"l"
        for item in lst:
            result += self.encode(item)
        result += b"e"
        return result

    def _encode_dict(self, dct: Dict[Any, Any]) -> bytes:
        """Encode dictionary as bencoded dictionary."""
        # Sort keys for bencode specification compliance
        try:
            sorted_items = sorted(dct.items(), key=lambda x: x[0] if isinstance(x[0], bytes) else x[0].encode("utf-8"))
        except AttributeError:
            raise BencodeEncodeError(f"Dictionary key must be string or bytes, got {type(list(dct.keys())[0])}")

        result = b"d"
        for key, value in sorted_items:
            if not isinstance(key, (str, bytes)):
                raise BencodeEncodeError(f"Dictionary key must be string or bytes, got {type(key)}")
            result += self.encode(key)
            result += self.encode(value)
        result += b"e"
        return result


def decode(data: bytes) -> Any:
    """Convenience function to decode bencoded data."""
    decoder = BencodeDecoder(data)
    return decoder.decode()


def encode(obj: Any) -> bytes:
    """Convenience function to encode Python object to bencoded data."""
    encoder = BencodeEncoder()
    return encoder.encode(obj)
