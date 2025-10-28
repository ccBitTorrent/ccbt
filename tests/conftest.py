"""Pytest configuration and shared fixtures for ccBitTorrent tests.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def cleanup_logging():
    """Clean up logging handlers after each test to prevent closed file errors."""
    yield
    # Clean up all handlers to prevent "I/O operation on closed file" errors
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    # Also clean up root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)


def create_test_torrent_dict(
    name: str = "test_torrent",
    info_hash: bytes = b"\x00" * 20,
    announce: str = "http://tracker.example.com/announce",
    file_length: int = 1024,
    piece_length: int = 16384,
    num_pieces: int = 1,
) -> dict[str, Any]:
    """Create properly formatted torrent dictionary for tests.

    This helper creates torrent data that matches the expected format
    for both TorrentInfo models and dictionary-based components.

    Args:
        name: Torrent name
        info_hash: 20-byte info hash
        announce: Tracker announce URL
        file_length: Size of the test file in bytes
        piece_length: Size of each piece in bytes
        num_pieces: Number of pieces

    Returns:
        Properly formatted torrent dictionary with pieces_info and file_info
    """
    piece_hashes = [b"\x00" * 20 for _ in range(num_pieces)]

    return {
        "name": name,
        "info_hash": info_hash,
        "announce": announce,
        "files": [
            {
                "name": f"{name}.txt",
                "length": file_length,
                "path": [f"{name}.txt"],
            },
        ],
        "total_length": file_length,
        "piece_length": piece_length,
        "pieces": piece_hashes,
        "num_pieces": num_pieces,
        # Add pieces_info for compatibility with piece managers
        "pieces_info": {
            "piece_length": piece_length,
            "num_pieces": num_pieces,
            "piece_hashes": piece_hashes,
        },
        # Add file_info for compatibility with session management
        "file_info": {
            "type": "single",
            "name": name,
            "total_length": file_length,
            "files": [
                {
                    "name": f"{name}.txt",
                    "length": file_length,
                    "path": [f"{name}.txt"],
                },
            ],
        },
    }
