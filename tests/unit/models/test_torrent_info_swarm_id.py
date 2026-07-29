from __future__ import annotations

import pytest

from ccbt.models import TorrentInfo


@pytest.mark.unit
def test_torrent_info_normalizes_swarm_id() -> None:
    torrent = TorrentInfo(
        name="demo",
        info_hash=b"\x00" * 20,
        announce="https://tracker.example/announce",
        total_length=0,
        piece_length=16384,
        pieces=[],
        num_pieces=0,
        meta_version=1,
        swarm_id="00112233-4455-6677-8899-AABBCCDDEEFF",
    )
    assert torrent.swarm_id == "00112233445566778899aabbccddeeff"


@pytest.mark.unit
def test_torrent_info_rejects_invalid_swarm_id() -> None:
    with pytest.raises(ValueError, match="swarm_id"):
        TorrentInfo(
            name="demo",
            info_hash=b"\x00" * 20,
            announce="https://tracker.example/announce",
            total_length=0,
            piece_length=16384,
            pieces=[],
            num_pieces=0,
            meta_version=1,
            swarm_id="not-a-hex-id",
        )
