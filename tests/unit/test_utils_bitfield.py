from __future__ import annotations

from ccbt.utils.bitfield import parse_bitfield, count_bits


def test_parse_bitfield_basic() -> None:
    # 1010 0000 -> pieces {0,2} for first byte (bit 7 and bit 5)
    data = bytes([0b10100000])
    pieces = parse_bitfield(data, num_pieces=8)
    assert 0 in pieces
    assert 2 in pieces
    assert len(pieces) == 2


def test_count_bits() -> None:
    data = bytes([0b11110000, 0b00001111])
    assert count_bits(data) == 8



