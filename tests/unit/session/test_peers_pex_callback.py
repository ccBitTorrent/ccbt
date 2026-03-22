from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.extensions.protocol import ExtensionMessageType, ExtensionProtocol
from ccbt.session.peers import PexBinder


@pytest.mark.asyncio
@pytest.mark.unit
async def test_pex_send_callback_encodes_payload_without_message_type():
    """PEX callback writes BEP 11 payload directly after extension id prefix."""
    peer_key = "198.51.100.77:6881"
    peer_payload = b"\x7f\x01peer_payload"
    pex_extension_id = 31

    logger = MagicMock()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()

    connection = SimpleNamespace(
        peer_info=SimpleNamespace(ip="198.51.100.77", port=6881),
        writer=writer,
        is_connected=lambda: True,
    )

    peer_manager = SimpleNamespace(
        connection_lock=asyncio.Lock(),
        connections={peer_key: connection},
    )

    extension_protocol = ExtensionProtocol()
    extension_manager = SimpleNamespace(get_extension=MagicMock(return_value=extension_protocol))

    session = SimpleNamespace(
        is_private=False,
        logger=logger,
        info=SimpleNamespace(name="test-session"),
        download_manager=SimpleNamespace(peer_manager=peer_manager),
        extension_manager=extension_manager,
    )

    binder = PexBinder()
    await binder.bind_and_start(session)

    session.pex_manager.sessions[peer_key] = SimpleNamespace(
        peer_key=peer_key, ut_pex_id=pex_extension_id, is_supported=True
    )

    assert session.pex_manager.send_pex_callback is not None
    assert await session.pex_manager.send_pex_callback(peer_key, peer_payload) is True
    encoded = writer.write.call_args[0][0]
    assert encoded[4] == ExtensionMessageType.EXTENDED
    payload = encoded[5:]
    assert payload == bytes([pex_extension_id]) + peer_payload


@pytest.mark.asyncio
@pytest.mark.unit
async def test_pex_disabled_by_authenticated_policy():
    """PEX binder exits early when authenticated policy disables PEX."""
    logger = MagicMock()
    session = SimpleNamespace(
        is_private=False,
        logger=logger,
        info=SimpleNamespace(name="policy-blocked"),
        _is_discovery_component_disabled=lambda component: component == "pex",
        _emit_discovery_suppressed_metric=MagicMock(),
    )

    binder = PexBinder()
    await binder.bind_and_start(session)

    assert not hasattr(session, "pex_manager")
    assert session._emit_discovery_suppressed_metric.called
