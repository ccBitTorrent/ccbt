from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from ccbt.daemon.ipc_server import IPCServer
from ccbt.executor.base import CommandResult


class _FakeRequest:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.remote = "127.0.0.1"

    async def json(self) -> dict[str, Any]:
        return self._payload


def _build_server() -> IPCServer:
    server = IPCServer.__new__(IPCServer)
    server.executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=CommandResult(
                success=True,
                data={"info_hash": "a" * 40},
            )
        )
    )
    server.session_manager = SimpleNamespace(get_session_for_info_hash=AsyncMock())
    server.emit_websocket_event = AsyncMock()
    return server


@pytest.mark.asyncio
async def test_add_torrent_returns_success_when_registration_visible_immediately() -> None:
    server = _build_server()
    server.session_manager.get_session_for_info_hash.return_value = object()

    response = await server._handle_add_torrent(
        _FakeRequest({"path_or_magnet": "/tmp/file.torrent", "resume": False})
    )

    assert response.status == 200
    payload = json.loads(response.text)
    assert payload["status"] == "added"
    assert payload["info_hash"] == "a" * 40
    assert payload["visibility_ready"] is True
    server.session_manager.get_session_for_info_hash.assert_awaited()


@pytest.mark.asyncio
async def test_add_torrent_waits_until_registration_visible() -> None:
    server = _build_server()
    server.session_manager.get_session_for_info_hash.side_effect = [
        None,
        None,
        object(),
    ]

    response = await server._handle_add_torrent(
        _FakeRequest({"path_or_magnet": "magnet:?xt=urn:btih:" + ("a" * 40)})
    )

    assert response.status == 200
    payload = json.loads(response.text)
    assert payload["status"] == "added"
    assert payload["visibility_ready"] is True
    assert server.session_manager.get_session_for_info_hash.await_count >= 3


@pytest.mark.asyncio
async def test_add_torrent_returns_success_with_warning_when_visibility_lags() -> None:
    server = _build_server()
    server.session_manager.get_session_for_info_hash.return_value = None

    response = await server._handle_add_torrent(
        _FakeRequest({"path_or_magnet": "/tmp/file.torrent"})
    )

    assert response.status == 200
    payload = json.loads(response.text)
    assert payload["status"] == "added"
    assert payload["visibility_ready"] is False
    assert payload["warning_code"] == "ADD_VISIBILITY_NOT_READY"
