"""Unit tests for XET metadata exchange request tracking."""

from __future__ import annotations

import asyncio

import pytest

from ccbt.core.tonic import TonicFile
from ccbt.extensions.xet import XetExtension
from ccbt.extensions.xet_metadata import XetMetadataExchange
from ccbt.models import XetTorrentMetadata

pytestmark = [pytest.mark.unit, pytest.mark.extensions, pytest.mark.asyncio]


def _build_minimal_tonic_bytes(folder_name: str) -> tuple[bytes, bytes]:
    tonic_file = TonicFile()
    tonic_bytes = tonic_file.create(
        folder_name=folder_name,
        xet_metadata=XetTorrentMetadata(),
        sync_mode="best_effort",
    )
    parsed = tonic_file.parse_bytes(tonic_bytes)
    return tonic_bytes, tonic_file.get_info_hash(parsed)


async def test_request_metadata_resolves_when_response_arrives() -> None:
    """A pending metadata request should resolve with the received bytes."""
    exchange = XetMetadataExchange(XetExtension())
    metadata_bytes, info_hash = _build_minimal_tonic_bytes("workspace")
    requested: list[tuple[str, bytes, int]] = []

    async def requester(peer_id: str, requested_hash: bytes, piece: int) -> bool:
        requested.append((peer_id, requested_hash, piece))
        return True

    exchange.set_piece_requester(requester)

    fetch_task = asyncio.create_task(exchange.request_metadata("peer-1", info_hash))
    await asyncio.sleep(0)

    assert requested == [("peer-1", info_hash, 0)]

    await exchange.handle_metadata_response(
        "peer-1",
        info_hash,
        0,
        1,
        metadata_bytes,
    )

    assert await fetch_task == metadata_bytes


async def test_request_metadata_resolves_none_when_peer_reports_missing() -> None:
    """A metadata request should resolve to None on an explicit not-found reply."""
    exchange = XetMetadataExchange(XetExtension())
    _, info_hash = _build_minimal_tonic_bytes("workspace")

    async def requester(_peer_id: str, _requested_hash: bytes, _piece: int) -> bool:
        return True

    exchange.set_piece_requester(requester)

    fetch_task = asyncio.create_task(exchange.request_metadata("peer-1", info_hash))
    await asyncio.sleep(0)
    await exchange.handle_metadata_not_found("peer-1", info_hash)

    assert await fetch_task is None
