"""Unit tests for XET metadata resolver (cold link and remote URL)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ccbt.core.tonic import TonicFile
from ccbt.core.tonic_link import generate_tonic_link
from ccbt.session.xet_metadata_resolver import (
    ResolvedTonicMetadata,
    XetMetadataResolver,
    _fetch_tonic_bytes_from_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.session]


def _build_minimal_tonic_bytes(folder_name: str) -> tuple[bytes, bytes]:
    tonic_file = TonicFile()
    from ccbt.models import XetTorrentMetadata

    tonic_bytes = tonic_file.create(
        folder_name=folder_name,
        xet_metadata=XetTorrentMetadata(),
        sync_mode="best_effort",
    )
    parsed = tonic_file.parse_bytes(tonic_bytes)
    return tonic_bytes, tonic_file.get_info_hash(parsed)


@pytest.mark.asyncio
async def test_resolve_file(tmp_path: Path) -> None:
    """Resolver resolves a local .tonic file path."""
    tonic_bytes, info_hash = _build_minimal_tonic_bytes("file-ws")
    tonic_path = tmp_path / "f.tonic"
    tonic_path.write_bytes(tonic_bytes)

    resolver = XetMetadataResolver()
    result = await resolver.resolve(str(tonic_path))

    assert isinstance(result, ResolvedTonicMetadata)
    assert result.workspace_id == info_hash
    assert result.metadata_bytes == tonic_bytes
    assert result.parsed_metadata["info"]["name"] == "file-ws"
    assert result.tonic_source == str(tonic_path.resolve())


@pytest.mark.asyncio
async def test_resolve_remote_url_success() -> None:
    """Resolver resolves a remote http(s) URL when fetch returns valid .tonic bytes."""
    tonic_bytes, info_hash = _build_minimal_tonic_bytes("remote-ws")

    with patch(
        "ccbt.session.xet_metadata_resolver._fetch_tonic_bytes_from_url",
        new_callable=AsyncMock,
        return_value=tonic_bytes,
    ):
        resolver = XetMetadataResolver()
        result = await resolver.resolve("https://example.com/workspace.tonic")

    assert result.workspace_id == info_hash
    assert result.metadata_bytes == tonic_bytes
    assert result.tonic_source == "https://example.com/workspace.tonic"


@pytest.mark.asyncio
async def test_resolve_remote_url_fetch_raises_propagates() -> None:
    """When remote fetch raises RuntimeError, resolve propagates it."""
    with patch(
        "ccbt.session.xet_metadata_resolver._fetch_tonic_bytes_from_url",
        new_callable=AsyncMock,
        side_effect=RuntimeError("HTTP 404 for .tonic URL"),
    ):
        resolver = XetMetadataResolver()
        with pytest.raises(RuntimeError) as exc_info:
            await resolver.resolve("https://example.com/missing.tonic")
        assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_tonic_bytes_from_url_invalid_scheme_raises() -> None:
    """_fetch_tonic_bytes_from_url raises for non-http(s) scheme."""
    with pytest.raises(RuntimeError) as exc_info:
        await _fetch_tonic_bytes_from_url("ftp://example.com/x.tonic", timeout=1.0)
    assert "Invalid URL scheme" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resolve_cold_link_success_when_mock_discover_and_fetch() -> None:
    """Cold link resolves when discover_peers and fetch_xet_metadata_from_peers return data."""
    tonic_bytes, info_hash = _build_minimal_tonic_bytes("cold-ws")
    link = generate_tonic_link(
        info_hash=info_hash,
        display_name="cold-ws",
        sync_mode="best_effort",
        source_peers=["1.2.3.4:6881"],
    )

    with patch(
        "ccbt.session.xet_metadata_resolver.discover_peers_for_workspace",
        new_callable=AsyncMock,
        return_value=[("1.2.3.4", 6881)],
    ), patch(
        "ccbt.session.xet_metadata_resolver.fetch_xet_metadata_from_peers",
        new_callable=AsyncMock,
        return_value=tonic_bytes,
    ):
        resolver = XetMetadataResolver()
        result = await resolver.resolve(link, session_manager=None)

    assert result.workspace_id == info_hash
    assert result.metadata_bytes == tonic_bytes
    assert result.tonic_source == link


@pytest.mark.asyncio
async def test_resolve_cold_link_failure_raises_runtime_error() -> None:
    """Cold link raises RuntimeError when no peers or fetch returns None."""
    _, info_hash = _build_minimal_tonic_bytes("orphan")
    link = generate_tonic_link(
        info_hash=info_hash,
        display_name="orphan",
        sync_mode="best_effort",
    )
    # No session_manager -> no cache; mock discover to return empty so fetch not called
    with patch(
        "ccbt.session.xet_metadata_resolver.discover_peers_for_workspace",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resolver = XetMetadataResolver()
        with pytest.raises(RuntimeError) as exc_info:
            await resolver.resolve(link, session_manager=None)
    assert "Could not discover peers or fetch metadata" in str(exc_info.value)
    assert ".tonic file" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resolve_cold_link_failure_when_fetch_returns_none() -> None:
    """Cold link raises when peers exist but fetch_xet_metadata_from_peers returns None."""
    _, info_hash = _build_minimal_tonic_bytes("orphan")
    link = generate_tonic_link(
        info_hash=info_hash,
        display_name="orphan",
        sync_mode="best_effort",
        source_peers=["127.0.0.1:37999"],
    )
    with patch(
        "ccbt.session.xet_metadata_resolver.discover_peers_for_workspace",
        new_callable=AsyncMock,
        return_value=[("127.0.0.1", 37999)],
    ), patch(
        "ccbt.session.xet_metadata_resolver.fetch_xet_metadata_from_peers",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resolver = XetMetadataResolver()
        with pytest.raises(RuntimeError) as exc_info:
            await resolver.resolve(link, session_manager=None)
    assert "Could not discover peers or fetch metadata" in str(exc_info.value)
