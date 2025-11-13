from __future__ import annotations

import asyncio
from typing import Any

from ccbt.session.models import SessionContext
from ccbt.session.peers import PeerManagerInitializer
from ccbt.config.config import get_config


class FakePeerManager:
    def __init__(self, *_: Any, **__: Any) -> None:
        self._started = False
        self._security_manager = None
        self._is_private = False

    async def start(self) -> None:
        self._started = True


async def test_peer_initializer_binds_and_starts(monkeypatch: Any) -> None:
    # Monkeypatch the async peer manager used inside the initializer
    import ccbt.session.peers as peers_mod

    peers_mod.AsyncPeerConnectionManager = FakePeerManager  # type: ignore[attr-defined]

    class DM:
        def __init__(self) -> None:
            self.torrent_data = {"info_hash": b"x" * 20, "name": "t", "announce": "http://t"}
            self.piece_manager = object()
            self.our_peer_id = b"-CC0101-xxxxxxxxxxxx"
            self.peer_manager = None
            self.security_manager = None

    dm = DM()
    config = get_config()
    ctx = SessionContext(
        config=config,
        torrent_data=dm.torrent_data,
        output_dir=config.disk.download_dir,
    )

    initializer = PeerManagerInitializer()
    pm = await initializer.init_and_bind(
        dm,
        is_private=False,
        session_ctx=ctx,
        on_peer_connected=None,
        on_peer_disconnected=None,
        on_piece_received=None,
        on_bitfield_received=None,
        logger=None,
    )
    assert pm is not None
    assert dm.peer_manager is pm
    assert getattr(pm, "_started", True) or getattr(pm, "_started", False) is not False



