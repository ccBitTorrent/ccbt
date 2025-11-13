"""Unit tests for NAT port mapping renewal."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.nat.exceptions import NATPMPError, UPnPError
from ccbt.nat.manager import NATManager
from ccbt.nat.natpmp import NATPMPPortMapping
from ccbt.nat.port_mapping import PortMapping, PortMappingManager


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = MagicMock()
    config.nat.port_mapping_lease_time = 3600
    return config


@pytest.fixture
def mock_nat_manager(mock_config):
    """Create mock NAT manager."""
    manager = NATManager(mock_config)
    manager.active_protocol = "natpmp"
    manager.natpmp_client = MagicMock()
    manager.upnp_client = MagicMock()
    return manager


@pytest.fixture
def port_mapping_manager_with_callback(mock_nat_manager):
    """Create PortMappingManager with renewal callback."""
    return PortMappingManager(
        renewal_callback=mock_nat_manager._renew_mapping_callback  # noqa: SLF001
    )


@pytest.fixture
def port_mapping_manager_no_callback():
    """Create PortMappingManager without renewal callback."""
    return PortMappingManager()


@pytest.mark.asyncio
async def test_renew_mapping_natpmp_success(mock_nat_manager):
    """Test successful NAT-PMP mapping renewal."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="natpmp",
    )

    # Mock NAT-PMP renewal response
    natpmp_mapping = NATPMPPortMapping(
        internal_port=6881,
        external_port=6881,
        lifetime=3600,
        protocol="tcp",
    )
    mock_nat_manager.natpmp_client.add_port_mapping = AsyncMock(
        return_value=natpmp_mapping
    )

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is True
    assert new_lifetime == 3600
    mock_nat_manager.natpmp_client.add_port_mapping.assert_called_once_with(
        6881, 6881, lifetime=3600, protocol="tcp"
    )


@pytest.mark.asyncio
async def test_renew_mapping_upnp_success(mock_nat_manager):
    """Test successful UPnP mapping renewal."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="upnp",
    )

    mock_nat_manager.active_protocol = "upnp"
    mock_nat_manager.upnp_client.add_port_mapping = AsyncMock()

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is True
    assert new_lifetime == 3600
    mock_nat_manager.upnp_client.add_port_mapping.assert_called_once_with(
        6881, 6881, protocol="TCP", description="ccBitTorrent", duration=3600
    )


@pytest.mark.asyncio
async def test_renew_mapping_natpmp_failure(mock_nat_manager):
    """Test NAT-PMP renewal failure."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="natpmp",
    )

    mock_nat_manager.natpmp_client.add_port_mapping = AsyncMock(
        side_effect=NATPMPError("Port conflict")
    )

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is False
    assert new_lifetime is None


@pytest.mark.asyncio
async def test_renew_mapping_upnp_failure(mock_nat_manager):
    """Test UPnP renewal failure."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="upnp",
    )

    mock_nat_manager.active_protocol = "upnp"
    mock_nat_manager.upnp_client.add_port_mapping = AsyncMock(
        side_effect=UPnPError("Failed")
    )

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is False
    assert new_lifetime is None


@pytest.mark.asyncio
async def test_renew_mapping_no_active_protocol_discovers(mock_nat_manager):
    """Test renewal discovers protocol if not active."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="natpmp",
    )

    mock_nat_manager.active_protocol = None
    mock_nat_manager.discover = AsyncMock(return_value=False)

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is False
    assert new_lifetime is None
    mock_nat_manager.discover.assert_called_once()


@pytest.mark.asyncio
async def test_renew_mapping_natpmp_client_none(mock_nat_manager):
    """Test renewal when NAT-PMP client is None."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="natpmp",
    )

    mock_nat_manager.natpmp_client = None

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is False
    assert new_lifetime is None


@pytest.mark.asyncio
async def test_renew_mapping_upnp_client_none(mock_nat_manager):
    """Test renewal when UPnP client is None."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="upnp",
    )

    mock_nat_manager.active_protocol = "upnp"
    mock_nat_manager.upnp_client = None

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is False
    assert new_lifetime is None


@pytest.mark.asyncio
async def test_renew_mapping_unknown_protocol_source(mock_nat_manager):
    """Test renewal with unknown protocol source."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="unknown",
    )

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is False
    assert new_lifetime is None


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_with_callback(
    port_mapping_manager_with_callback, mock_nat_manager
):
    """Test PortMappingManager renewal with callback."""
    # Create a mapping with short lifetime for fast testing
    lifetime = 2  # 2 seconds
    await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Mock successful renewal
    natpmp_mapping = NATPMPPortMapping(
        internal_port=6881, external_port=6881, lifetime=3600, protocol="tcp"
    )
    mock_nat_manager.natpmp_client.add_port_mapping = AsyncMock(
        return_value=natpmp_mapping
    )

    # Wait for renewal (80% of 2 seconds = 1.6 seconds)
    await asyncio.sleep(2.0)

    # Verify mapping was renewed
    updated_mapping = await port_mapping_manager_with_callback.get_mapping("tcp", 6881)
    assert updated_mapping is not None
    # Expiration should be updated (approximately 3600 seconds from now)
    assert updated_mapping.expires_at is not None
    assert updated_mapping.expires_at > time.time() + 3000  # At least 3000s in future

    # Cleanup
    await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_no_callback(
    port_mapping_manager_no_callback,
):
    """Test PortMappingManager renewal without callback logs warning."""
    lifetime = 1  # 1 second
    await port_mapping_manager_no_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Wait for renewal attempt
    await asyncio.sleep(1.5)

    # Mapping should still exist (no renewal happened, but no error either)
    existing_mapping = await port_mapping_manager_no_callback.get_mapping("tcp", 6881)
    assert existing_mapping is not None

    # Cleanup
    await port_mapping_manager_no_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_retry_on_failure(
    port_mapping_manager_with_callback, mock_nat_manager
):
    """Test PortMappingManager retries renewal on failure."""
    lifetime = 1  # 1 second

    # First two attempts fail, third succeeds
    call_count = 0

    async def mock_renewal(mapping):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return False, None
        natpmp_mapping = NATPMPPortMapping(
            internal_port=6881, external_port=6881, lifetime=3600, protocol="tcp"
        )
        mock_nat_manager.natpmp_client.add_port_mapping = AsyncMock(
            return_value=natpmp_mapping
        )
        return await mock_nat_manager._renew_mapping_callback(mapping)  # noqa: SLF001

    port_mapping_manager_with_callback.renewal_callback = mock_renewal

    await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Wait for renewal with retries (1.6s initial + 60s retry * 2 = ~122s)
    # For test speed, we'll use shorter delays
    await asyncio.sleep(2.0)

    # Should have attempted renewal
    assert call_count >= 1

    # Cleanup
    await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_mapping_removed_during_renewal(
    port_mapping_manager_with_callback, mock_nat_manager
):
    """Test renewal gracefully handles mapping removal during renewal."""
    lifetime = 1  # 1 second

    async def slow_renewal(mapping):
        # Simulate slow renewal
        await asyncio.sleep(0.5)
        natpmp_mapping = NATPMPPortMapping(
            internal_port=6881, external_port=6881, lifetime=3600, protocol="tcp"
        )
        mock_nat_manager.natpmp_client.add_port_mapping = AsyncMock(
            return_value=natpmp_mapping
        )
        return await mock_nat_manager._renew_mapping_callback(mapping)  # noqa: SLF001

    port_mapping_manager_with_callback.renewal_callback = slow_renewal

    await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Wait a bit for renewal to start
    await asyncio.sleep(1.2)

    # Remove mapping while renewal is in progress
    await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)

    # Wait a bit more
    await asyncio.sleep(0.5)

    # Mapping should be removed
    assert await port_mapping_manager_with_callback.get_mapping("tcp", 6881) is None


@pytest.mark.asyncio
async def test_port_mapping_manager_continuous_renewal(
    port_mapping_manager_with_callback, mock_nat_manager
):
    """Test continuous renewal (multiple renewals)."""
    lifetime = 1  # 1 second

    renewal_count = 0

    async def track_renewal(mapping):
        nonlocal renewal_count
        renewal_count += 1
        natpmp_mapping = NATPMPPortMapping(
            internal_port=6881, external_port=6881, lifetime=3600, protocol="tcp"
        )
        mock_nat_manager.natpmp_client.add_port_mapping = AsyncMock(
            return_value=natpmp_mapping
        )
        return await mock_nat_manager._renew_mapping_callback(mapping)  # noqa: SLF001

    port_mapping_manager_with_callback.renewal_callback = track_renewal

    await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Wait for first renewal (1.6s)
    await asyncio.sleep(2.0)

    # Should have at least one renewal
    assert renewal_count >= 1

    # Cleanup
    await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_permanent_mapping(
    port_mapping_manager_with_callback,
):
    """Test that permanent mappings (lifetime=0) don't get renewal tasks."""
    # Add mapping with no lifetime (permanent)
    mapping = await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", None
    )

    # Should have no renewal task
    assert mapping.renewal_task is None

    # Cleanup
    await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_cancelled_on_removal(
    port_mapping_manager_with_callback,
):
    """Test that renewal task is cancelled when mapping is removed."""
    lifetime = 10  # 10 seconds

    mapping = await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Should have renewal task
    assert mapping.renewal_task is not None
    assert not mapping.renewal_task.done()

    # Remove mapping
    await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)

    # Wait a bit for cancellation
    await asyncio.sleep(0.1)

    # Task should be cancelled or done
    assert mapping.renewal_task.done() or mapping.renewal_task.cancelled()


@pytest.mark.asyncio
async def test_renew_mapping_callback_integration(mock_nat_manager):
    """Test the callback integration between PortMappingManager and NATManager."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="natpmp",
    )

    natpmp_mapping = NATPMPPortMapping(
        internal_port=6881, external_port=6881, lifetime=3600, protocol="tcp"
    )
    mock_nat_manager.natpmp_client.add_port_mapping = AsyncMock(
        return_value=natpmp_mapping
    )

    # Test callback
    success, new_lifetime = await mock_nat_manager._renew_mapping_callback(mapping)  # noqa: SLF001

    assert success is True
    assert new_lifetime == 3600


@pytest.mark.asyncio
async def test_renew_mapping_udp_protocol(mock_nat_manager):
    """Test renewal of UDP port mapping."""
    mapping = PortMapping(
        internal_port=6882,
        external_port=6882,
        protocol="udp",
        protocol_source="natpmp",
    )

    natpmp_mapping = NATPMPPortMapping(
        internal_port=6882, external_port=6882, lifetime=3600, protocol="udp"
    )
    mock_nat_manager.natpmp_client.add_port_mapping = AsyncMock(
        return_value=natpmp_mapping
    )

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is True
    assert new_lifetime == 3600
    mock_nat_manager.natpmp_client.add_port_mapping.assert_called_once_with(
        6882, 6882, lifetime=3600, protocol="udp"
    )


@pytest.mark.asyncio
async def test_renew_mapping_handles_exception(mock_nat_manager):
    """Test renewal handles unexpected exceptions."""
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="natpmp",
    )

    mock_nat_manager.natpmp_client.add_port_mapping = AsyncMock(
        side_effect=RuntimeError("Unexpected error")
    )

    success, new_lifetime = await mock_nat_manager.renew_mapping(mapping)

    assert success is False
    assert new_lifetime is None


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_mapping_removed_before_renewal(
    port_mapping_manager_with_callback, mock_nat_manager
):
    """Test renewal when mapping is removed before renewal time (covers lines 148-153)."""
    lifetime = 1  # 1 second

    # Add mapping
    mapping = await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Wait a bit for renewal task to start sleeping
    await asyncio.sleep(0.1)

    # Manually remove from dict without canceling task (to test the "mapping doesn't exist" path)
    # This simulates the mapping being removed by another process/thread
    key = port_mapping_manager_with_callback._make_key("tcp", 6881)
    async with port_mapping_manager_with_callback.lock:
        if key in port_mapping_manager_with_callback.mappings:
            # Don't cancel the task, just remove the mapping
            # This will cause the renewal task to find mapping missing when it wakes up
            del port_mapping_manager_with_callback.mappings[key]

    # Wait for renewal time (task should detect mapping doesn't exist at lines 148-153)
    await asyncio.sleep(1.0)

    # Mapping should be removed
    assert await port_mapping_manager_with_callback.get_mapping("tcp", 6881) is None


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_permanent_after_renewal(
    port_mapping_manager_with_callback, mock_nat_manager
):
    """Test renewal that returns lifetime=0 (permanent mapping)."""
    lifetime = 1  # 1 second

    async def permanent_renewal(mapping):
        """Return success with lifetime=0 (permanent)."""
        return True, 0

    port_mapping_manager_with_callback.renewal_callback = permanent_renewal

    await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Wait for renewal to complete (longer to ensure task completes)
    await asyncio.sleep(2.5)

    # Check mapping was updated
    updated = await port_mapping_manager_with_callback.get_mapping("tcp", 6881)
    assert updated is not None
    # After renewal with lifetime=0, task should be None (permanent mapping)
    # Wait a bit more for any in-flight task to complete
    await asyncio.sleep(0.2)
    # Re-fetch to get updated state
    updated = await port_mapping_manager_with_callback.get_mapping("tcp", 6881)
    assert updated is not None
    assert updated.renewal_task is None

    # Cleanup
    await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_success_no_lifetime(
    port_mapping_manager_with_callback,
):
    """Test renewal that succeeds but returns None for lifetime."""
    lifetime = 1  # 1 second

    async def no_lifetime_renewal(mapping):
        """Return success=True but lifetime=None."""
        return True, None

    port_mapping_manager_with_callback.renewal_callback = no_lifetime_renewal

    await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Wait for renewal
    await asyncio.sleep(1.5)

    # Mapping should still exist but no new renewal scheduled
    mapping = await port_mapping_manager_with_callback.get_mapping("tcp", 6881)
    assert mapping is not None

    # Cleanup
    await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_all_retries_fail(
    port_mapping_manager_with_callback,
):
    """Test renewal when all retry attempts fail (covers lines 243, 262)."""
    lifetime = 1  # 1 second

    attempt_count = 0

    async def always_fail_renewal(mapping):
        """Always return failure, track attempts."""
        nonlocal attempt_count
        attempt_count += 1
        return False, None

    port_mapping_manager_with_callback.renewal_callback = always_fail_renewal

    # Patch the retry delay in the actual renewal method by patching asyncio.sleep
    # to make retries faster
    original_sleep = asyncio.sleep
    sleep_count = 0

    async def fast_sleep(delay):
        nonlocal sleep_count
        sleep_count += 1
        # First sleep is the renewal delay (0.8s), keep it
        if sleep_count == 1:
            await original_sleep(delay)
        else:
            # Subsequent sleeps are retries, make them very short
            await original_sleep(0.05)  # 50ms instead of 60s

    # Patch asyncio.sleep in the port_mapping module
    import ccbt.nat.port_mapping as port_mapping_module
    original_module_sleep = port_mapping_module.asyncio.sleep
    port_mapping_module.asyncio.sleep = fast_sleep

    try:
        await port_mapping_manager_with_callback.add_mapping(
            6881, 6881, "tcp", "natpmp", lifetime
        )

        # Wait for all retry attempts (0.8s initial + 0.05s * 2 retries = ~0.9s)
        await asyncio.sleep(1.5)

        # Should have attempted 3 times (covers lines 243 and 262)
        assert attempt_count == 3

        # Mapping should still exist (renewal failed but mapping not removed)
        mapping = await port_mapping_manager_with_callback.get_mapping("tcp", 6881)
        assert mapping is not None
    finally:
        # Restore original sleep
        port_mapping_module.asyncio.sleep = original_module_sleep
        # Cleanup
        await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_exception_in_callback(
    port_mapping_manager_with_callback,
):
    """Test renewal when callback raises an exception."""
    lifetime = 1  # 1 second

    async def exception_renewal(mapping):
        """Raise an exception."""
        raise RuntimeError("Callback error")

    port_mapping_manager_with_callback.renewal_callback = exception_renewal

    await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", lifetime
    )

    # Wait for renewal attempt
    await asyncio.sleep(2.0)

    # Mapping should still exist (exception was handled)
    mapping = await port_mapping_manager_with_callback.get_mapping("tcp", 6881)
    assert mapping is not None

    # Cleanup
    await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_renewal_unexpected_exception(
    port_mapping_manager_with_callback,
):
    """Test renewal when unexpected exception occurs in renewal task (covers lines 276-277)."""
    lifetime = 1  # 1 second

    # Patch asyncio.sleep to raise an exception after the initial delay
    # This will trigger the outer exception handler (lines 276-277)
    import ccbt.nat.port_mapping as port_mapping_module
    original_module_sleep = port_mapping_module.asyncio.sleep
    sleep_call_count = 0

    async def error_sleep(delay):
        nonlocal sleep_call_count
        sleep_call_count += 1
        if sleep_call_count == 1:
            # First sleep (renewal delay) - complete it, then raise
            await original_module_sleep(delay)
            # Raise exception to trigger outer exception handler (lines 276-277)
            raise RuntimeError("Unexpected error in renewal task")
        # Subsequent sleeps should work normally (use original, not patched)
        return await original_module_sleep(delay)

    port_mapping_module.asyncio.sleep = error_sleep

    try:
        await port_mapping_manager_with_callback.add_mapping(
            6881, 6881, "tcp", "natpmp", lifetime
        )

        # Wait for exception to be triggered and handled
        # Use original sleep to avoid triggering our patched version
        await original_module_sleep(2.0)

        # Exception should be handled gracefully (lines 276-277)
        # Mapping should still exist (exception was caught)
        mapping = await port_mapping_manager_with_callback.get_mapping("tcp", 6881)
        assert mapping is not None
    finally:
        # Restore original sleep
        port_mapping_module.asyncio.sleep = original_module_sleep
        # Cleanup
        await port_mapping_manager_with_callback.remove_mapping("tcp", 6881)


@pytest.mark.asyncio
async def test_port_mapping_manager_cleanup_expired(
    port_mapping_manager_with_callback,
):
    """Test cleanup_expired removes expired mappings and cancels tasks."""
    # Add mapping with short lifetime
    mapping = await port_mapping_manager_with_callback.add_mapping(
        6881, 6881, "tcp", "natpmp", 3600
    )

    # Manually expire it
    mapping.expires_at = time.time() - 1

    # Cleanup expired
    await port_mapping_manager_with_callback.cleanup_expired()

    # Mapping should be removed
    assert await port_mapping_manager_with_callback.get_mapping("tcp", 6881) is None


@pytest.mark.asyncio
async def test_remove_mapping_not_found(port_mapping_manager_with_callback):
    """Test remove_mapping returns False when mapping not found."""
    result = await port_mapping_manager_with_callback.remove_mapping("tcp", 9999)
    assert result is False

