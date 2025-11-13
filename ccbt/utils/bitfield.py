"""Bitfield parsing and utilities for BitTorrent piece availability."""

from __future__ import annotations


def parse_bitfield(bitfield: bytes, num_pieces: int) -> set[int]:
    """Parse a bitfield into a set of piece indices (bits set to 1).

    Bits are numbered big-endian within each byte per BitTorrent spec.
    """
    pieces: set[int] = set()
    if not bitfield or num_pieces <= 0:
        return pieces
    for byte_idx, byte_val in enumerate(bitfield):
        for bit_idx in range(8):
            piece_idx = byte_idx * 8 + bit_idx
            if piece_idx >= num_pieces:
                return pieces
            if byte_val & (1 << (7 - bit_idx)):
                pieces.add(piece_idx)
    return pieces


def count_bits(bitfield: bytes) -> int:
    """Count the number of set bits in a bitfield."""
    if not bitfield:
        return 0
    return sum(bin(b).count("1") for b in bitfield)
