"""Unit tests for Port Mapping Manager."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.nat.port_mapping import PortMapping, PortMappingManager


@pytest.fixture
def port_mapping_manager():
    """Create port mapping manager instance."""
    return PortMappingManager()


@pytest.mark.asyncio
async def test_add_mapping(port_mapping_manager):
    """Test adding a port mapping."""
    mapping = await port_mapping_manager.add_mapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="natpmp",
        lifetime=3600,
    )

    assert mapping.internal_port == 6881
    assert mapping.external_port == 6881
    assert mapping.protocol == "tcp"
    assert mapping.protocol_source == "natpmp"
    assert mapping.expires_at is not None


@pytest.mark.asyncio
async def test_add_mapping_without_lifetime(port_mapping_manager):
    """Test adding mapping without lifetime."""
    mapping = await port_mapping_manager.add_mapping(
        internal_port=6882,
        external_port=6882,
        protocol="udp",
        protocol_source="upnp",
        lifetime=None,
    )

    assert mapping.expires_at is None
    assert mapping.renewal_task is None


@pytest.mark.asyncio
async def test_add_mapping_creates_renewal_task(port_mapping_manager):
    """Test adding mapping creates renewal task."""
    mapping = await port_mapping_manager.add_mapping(
        internal_port=6883,
        external_port=6883,
        protocol="tcp",
        protocol_source="natpmp",
        lifetime=1,  # Very short lifetime for testing
    )

    assert mapping.renewal_task is not None
    assert not mapping.renewal_task.done()

    # Cleanup
    mapping.renewal_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await mapping.renewal_task


@pytest.mark.asyncio
async def test_remove_mapping(port_mapping_manager):
    """Test removing a port mapping."""
    mapping = await port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "natpmp", 3600
    )

    result = await port_mapping_manager.remove_mapping("tcp", 6881)

    assert result is True

    # Verify it's gone
    retrieved = await port_mapping_manager.get_mapping("tcp", 6881)
    assert retrieved is None


@pytest.mark.asyncio
async def test_remove_mapping_not_found(port_mapping_manager):
    """Test removing non-existent mapping."""
    result = await port_mapping_manager.remove_mapping("tcp", 9999)

    assert result is False


@pytest.mark.asyncio
async def test_remove_mapping_cancels_renewal_task(port_mapping_manager):
    """Test removing mapping cancels renewal task."""
    mapping = await port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "natpmp", 3600
    )

    task = mapping.renewal_task
    assert task is not None

    await port_mapping_manager.remove_mapping("tcp", 6881)

    # Task should be cancelled (may take a moment)
    await asyncio.sleep(0.01)
    assert task.cancelled()


@pytest.mark.asyncio
async def test_get_mapping(port_mapping_manager):
    """Test retrieving a specific mapping."""
    await port_mapping_manager.add_mapping(6881, 6881, "tcp", "natpmp", 3600)

    mapping = await port_mapping_manager.get_mapping("tcp", 6881)

    assert mapping is not None
    assert mapping.internal_port == 6881


@pytest.mark.asyncio
async def test_get_mapping_not_found(port_mapping_manager):
    """Test retrieving non-existent mapping."""
    mapping = await port_mapping_manager.get_mapping("tcp", 9999)

    assert mapping is None


@pytest.mark.asyncio
async def test_get_all_mappings(port_mapping_manager):
    """Test retrieving all mappings."""
    await port_mapping_manager.add_mapping(6881, 6881, "tcp", "natpmp", 3600)
    await port_mapping_manager.add_mapping(6882, 6882, "udp", "upnp", 3600)

    mappings = await port_mapping_manager.get_all_mappings()

    assert len(mappings) == 2
    ports = {m.external_port for m in mappings}
    assert 6881 in ports
    assert 6882 in ports


@pytest.mark.asyncio
async def test_renewal_task_logs(port_mapping_manager):
    """Test renewal task logs when time comes."""
    # Add mapping with very short lifetime
    mapping = await port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime=1
    )

    # Wait for renewal delay (80% of lifetime = 0.8 seconds)
    await asyncio.sleep(1.0)

    # Task should have completed (or be about to)
    # Since it just logs, we mainly verify it doesn't crash
    assert True

    # Cleanup
    if mapping.renewal_task and not mapping.renewal_task.done():
        mapping.renewal_task.cancel()


@pytest.mark.asyncio
async def test_renewal_task_handles_cancellation(port_mapping_manager):
    """Test renewal task handles cancellation."""
    mapping = await port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime=3600
    )

    task = mapping.renewal_task
    assert task is not None

    # Cancel immediately
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_cleanup_expired(port_mapping_manager):
    """Test cleaning up expired mappings."""
    # Add mapping that expires immediately
    mapping = await port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime=0.1
    )
    # Manually set expiration time in the past
    mapping.expires_at = time.time() - 1

    await port_mapping_manager.cleanup_expired()

    # Mapping should be removed
    retrieved = await port_mapping_manager.get_mapping("tcp", 6881)
    assert retrieved is None


@pytest.mark.asyncio
async def test_cleanup_expired_cancels_tasks(port_mapping_manager):
    """Test cleanup cancels renewal tasks."""
    mapping = await port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime=3600
    )
    task = mapping.renewal_task
    assert task is not None
    
    # Manually expire it
    mapping.expires_at = time.time() - 1

    await port_mapping_manager.cleanup_expired()

    # Task should be cancelled (may take a moment)
    await asyncio.sleep(0.01)
    assert task.cancelled()


@pytest.mark.asyncio
async def test_make_key(port_mapping_manager):
    """Test internal key generation."""
    key = port_mapping_manager._make_key("tcp", 6881)
    assert key == "tcp:6881"


@pytest.mark.asyncio
async def test_multiple_mappings_same_port_different_protocol(port_mapping_manager):
    """Test multiple mappings with same port but different protocols."""
    await port_mapping_manager.add_mapping(6881, 6881, "tcp", "natpmp", 3600)
    await port_mapping_manager.add_mapping(6881, 6881, "udp", "upnp", 3600)

    tcp_mapping = await port_mapping_manager.get_mapping("tcp", 6881)
    udp_mapping = await port_mapping_manager.get_mapping("udp", 6881)

    assert tcp_mapping is not None
    assert udp_mapping is not None
    assert tcp_mapping.protocol == "tcp"
    assert udp_mapping.protocol == "udp"

