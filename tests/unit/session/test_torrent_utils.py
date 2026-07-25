"""Tests for ccbt.session.torrent_utils helpers."""

from __future__ import annotations

import logging
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from ccbt.models import TorrentInfo
from ccbt.session import torrent_utils

pytestmark = pytest.mark.unit

_FAIL_MSG = "forced model failure"
_EXPECTED_RATE_LIMITED_DEBUG_CALLS = 2


class _TorrentInfoThatFails(TorrentInfo):
    def __init__(self, *_a: object, **_kw: object) -> None:
        raise RuntimeError(_FAIL_MSG)


def test_get_torrent_info_returns_none_when_piece_length_non_positive() -> None:
    """Invalid piece_length should short-circuit without building TorrentInfo."""
    logger = logging.getLogger("test_torrent_utils")
    with patch.object(logger, "debug") as mock_debug:
        out = torrent_utils.get_torrent_info(
            {
                "info_hash": b"\x02" * 20,
                "pieces_info": {"piece_length": 0, "num_pieces": 0, "piece_hashes": []},
            },
            logger=logger,
        )
    assert out is None
    mock_debug.assert_not_called()


def test_get_torrent_info_normalizes_flat_announce_list() -> None:
    """Flat announce_list from magnet/merge must become BEP 12 tiers."""
    out = torrent_utils.get_torrent_info(
        {
            "info_hash": b"\x04" * 20,
            "name": "flat-announce",
            "announce": "http://tracker.example.com/announce",
            "announce_list": [
                "http://tracker.example.com/announce",
                "udp://tracker.example.com:1337/announce",
            ],
            "files": [{"name": "a.bin", "length": 16, "path": ["a.bin"]}],
            "total_length": 16,
            "piece_length": 16,
            "pieces": [b"\x01" * 20],
            "num_pieces": 1,
        }
    )
    assert out is not None
    assert out.announce_list == [
        ["http://tracker.example.com/announce"],
        ["udp://tracker.example.com:1337/announce"],
    ]


def test_get_torrent_info_conversion_fail_debug_rate_limited() -> None:
    """Broad conversion failures should not log every call within the TTL window."""
    logger = logging.getLogger("test_torrent_utils_rate")
    logger.setLevel(logging.DEBUG)
    bad: dict[str, object] = {"info_hash": b"\x03" * 20}
    mono = [0.0, 5.0, 70.0]
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(torrent_utils, "_CONVERSION_FAIL_LOG_TTL_S", 60.0)
        )
        stack.enter_context(
            patch.object(torrent_utils.time, "monotonic", side_effect=mono)
        )
        stack.enter_context(
            patch.object(torrent_utils, "TorrentInfoModel", _TorrentInfoThatFails)
        )
        mock_debug = stack.enter_context(patch.object(logger, "debug"))
        assert torrent_utils.get_torrent_info(bad, logger=logger) is None
        assert torrent_utils.get_torrent_info(bad, logger=logger) is None
        assert torrent_utils.get_torrent_info(bad, logger=logger) is None
    assert mock_debug.call_count == _EXPECTED_RATE_LIMITED_DEBUG_CALLS
