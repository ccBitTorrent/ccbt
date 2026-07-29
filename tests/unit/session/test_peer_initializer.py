from __future__ import annotations

from typing import Any

import ccbt.session.peers as peers_mod
from ccbt.config.config import get_config
from ccbt.session.models import SessionContext
from ccbt.session.peers import PeerManagerInitializer


class FakePeerManager:
    def __init__(self, *_: Any, **__: Any) -> None:
        self._started = False
        self._security_manager = None
        self._is_private = False
        self.connections: dict[str, Any] = {}
        self.on_peer_connected = None
        self.on_peer_disconnected = None
        self.on_piece_received = None
        self.on_bitfield_received = None

    def set_security_manager(self, _manager: Any) -> None:
        self._security_manager = _manager

    def set_is_private(self, is_private: bool) -> None:
        self._is_private = is_private

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    async def connect_to_peers(self, _peers: Any) -> None:
        return None

    def get_connected_peers(self) -> list[Any]:
        return []

    def get_active_peers(self) -> list[Any]:
        return []


async def test_peer_initializer_binds_and_starts(monkeypatch: Any) -> None:
    # Monkeypatch the async peer manager used inside the initializer
    monkeypatch.setattr(peers_mod, "AsyncPeerConnectionManager", FakePeerManager)

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



