"""Tests for inbound info-hash matching on session manager."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ccbt.session.session import AsyncSessionManager

pytestmark = pytest.mark.unit

_HASH = b"\xab" * 20
_BOOM = "_get_torrent_info should not be called"


def test_session_matches_inbound_uses_dict_info_hash_before_get_torrent_info() -> None:
    """Match inbound hash from dict `info_hash` without building TorrentInfo."""
    mgr = AsyncSessionManager.__new__(AsyncSessionManager)

    def _boom(_td: object) -> None:
        raise AssertionError(_BOOM)

    session = SimpleNamespace(
        info=SimpleNamespace(info_hash=None),
        torrent_data={"info_hash": _HASH},
        _get_torrent_info=_boom,
    )
    assert mgr._session_matches_inbound_info_hash_candidates(  # noqa: SLF001
        session,
        [_HASH],
    )
