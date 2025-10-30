"""Bencoding module for BitTorrent protocol.

This module provides a convenient interface to the core bencode functionality.
"""

from __future__ import annotations

from ccbt.core.bencode import decode, encode

__all__ = ["decode", "encode"]
