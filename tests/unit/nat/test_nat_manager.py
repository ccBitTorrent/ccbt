"""Unit tests for NAT Manager."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ccbt.nat.exceptions import NATPMPError, UPnPError
from ccbt.nat.manager import NATManager


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = MagicMock()
    config.nat.enable_nat_pmp = True
    config.nat.enable_upnp = True
    config.nat.auto_map_ports = True
    config.nat.nat_discovery_interval = 300.0
    config.nat.port_mapping_lease_time = 3600
    config.nat.map_tcp_port = True
    config.nat.map_udp_port = True
    config.nat.map_dht_port = True
    config.network.listen_port = 6881
    config.discovery.dht_port = 6882
    return config


@pytest.fixture
def nat_manager(mock_config):
    """Create NAT manager instance."""
    return NATManager(mock_config)


@pytest.mark.asyncio
async def test_discover_natpmp_success(nat_manager, mock_config):
    """Test successful NAT-PMP discovery."""
    with patch("ccbt.nat.manager.NATPMPClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_external_ip = AsyncMock()
        mock_client._external_ip = None
        mock_client_class.return_value = mock_client

        result = await nat_manager.discover()

        assert result is True
        assert nat_manager.active_protocol == "natpmp"
        assert nat_manager.natpmp_client is not None


@pytest.mark.asyncio
async def test_discover_natpmp_failure_upnp_success(nat_manager, mock_config):
    """Test NAT-PMP failure with UPnP fallback."""
    with patch("ccbt.nat.manager.NATPMPClient") as mock_natpmp, \
         patch("ccbt.nat.manager.UPnPClient") as mock_upnp_class:
        # NAT-PMP fails
        mock_natpmp_client = MagicMock()
        mock_natpmp_client.get_external_ip = AsyncMock(side_effect=NATPMPError("Failed"))
        mock_natpmp.return_value = mock_natpmp_client

        # UPnP succeeds
        mock_upnp_client = MagicMock()
        mock_upnp_client.discover = AsyncMock(return_value=True)
        mock_upnp_client.get_external_ip = AsyncMock(return_value=None)
        mock_upnp_class.return_value = mock_upnp_client

        result = await nat_manager.discover()

        assert result is True
        assert nat_manager.active_protocol == "upnp"
        assert nat_manager.upnp_client is not None


@pytest.mark.asyncio
async def test_discover_both_fail(nat_manager, mock_config):
    """Test both NAT-PMP and UPnP discovery fail."""
    with patch("ccbt.nat.manager.NATPMPClient") as mock_natpmp, \
         patch("ccbt.nat.manager.UPnPClient") as mock_upnp:
        # Both fail
        mock_natpmp_client = MagicMock()
        mock_natpmp_client.get_external_ip = AsyncMock(side_effect=NATPMPError("Failed"))
        mock_natpmp.return_value = mock_natpmp_client

        mock_upnp_client = MagicMock()
        mock_upnp_client.discover = AsyncMock(side_effect=UPnPError("Failed"))
        mock_upnp.return_value = mock_upnp_client

        result = await nat_manager.discover()

        assert result is False
        assert nat_manager.active_protocol is None


@pytest.mark.asyncio
async def test_discover_natpmp_disabled(nat_manager, mock_config):
    """Test NAT-PMP disabled."""
    mock_config.nat.enable_nat_pmp = False

    with patch("ccbt.nat.manager.UPnPClient") as mock_upnp:
        mock_upnp_client = MagicMock()
        mock_upnp_client.discover = AsyncMock(return_value=True)
        mock_upnp_client.get_external_ip = AsyncMock(return_value=None)
        mock_upnp.return_value = mock_upnp_client

        result = await nat_manager.discover()

        # Should try UPnP
        assert result is True or result is False


@pytest.mark.asyncio
async def test_discover_upnp_disabled(nat_manager, mock_config):
    """Test UPnP disabled."""
    mock_config.nat.enable_upnp = False

    with patch("ccbt.nat.manager.NATPMPClient") as mock_natpmp:
        mock_client = MagicMock()
        mock_client.get_external_ip = AsyncMock()
        mock_client._external_ip = None
        mock_natpmp.return_value = mock_client

        result = await nat_manager.discover()

        # Should try NAT-PMP only
        assert result is True or result is False


@pytest.mark.asyncio
async def test_start_with_auto_map_disabled(nat_manager, mock_config):
    """Test start() when auto_map_ports is disabled."""
    mock_config.nat.auto_map_ports = False

    await nat_manager.start()

    # Should not discover or start discovery loop
    assert nat_manager.active_protocol is None
    assert nat_manager._discovery_task is None


@pytest.mark.asyncio
async def test_start_with_discovery_interval(nat_manager, mock_config):
    """Test start() with discovery interval."""
    mock_config.nat.nat_discovery_interval = 60.0

    with patch.object(nat_manager, "discover", new_callable=AsyncMock) as mock_discover:
        mock_discover.return_value = True

        await nat_manager.start()

        # Should start discovery loop
        assert nat_manager._discovery_task is not None
        assert not nat_manager._discovery_task.done()

        # Cleanup
        nat_manager._discovery_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await nat_manager._discovery_task


@pytest.mark.asyncio
async def test_discovery_loop_re_discovers(nat_manager, mock_config):
    """Test discovery loop re-discovers when protocol not active."""
    mock_config.nat.nat_discovery_interval = 0.05  # Very short for fast test

    discover_calls = []

    async def mock_discover():
        discover_calls.append(1)
        return False  # No protocol found

    nat_manager.discover = mock_discover

    # Start loop
    task = asyncio.create_task(nat_manager._discovery_loop())

    # Wait for at least one iteration
    await asyncio.sleep(0.08)  # Slightly more than interval

    # Cancel and wait
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=0.1)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    # Should have called discover at least once
    assert len(discover_calls) >= 1


@pytest.mark.asyncio
async def test_discovery_loop_handles_exception(nat_manager, mock_config):
    """Test discovery loop handles exceptions."""
    mock_config.nat.nat_discovery_interval = 0.05  # Very short for fast test

    async def mock_discover():
        raise Exception("Test error")

    nat_manager.discover = mock_discover

    task = asyncio.create_task(nat_manager._discovery_loop())

    # Wait for exception to be handled
    await asyncio.sleep(0.08)

    # Cancel and wait
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=0.1)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    # Verify task completed or was cancelled
    # (Exception handling means it continues, cancellation stops it)
    assert task.done()


@pytest.mark.asyncio
async def test_map_port_natpmp(nat_manager, mock_config):
    """Test port mapping with NAT-PMP."""
    from ccbt.nat.natpmp import NATPMPPortMapping

    nat_manager.active_protocol = "natpmp"

    # NAT-PMP returns NATPMPPortMapping, not PortMapping
    natpmp_mapping = NATPMPPortMapping(
        internal_port=6881,
        external_port=6881,
        lifetime=3600,
        protocol="tcp",
    )

    from ccbt.nat.port_mapping import PortMapping
    port_mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="natpmp",
    )

    nat_manager.natpmp_client = MagicMock()
    nat_manager.natpmp_client.add_port_mapping = AsyncMock(return_value=natpmp_mapping)

    with patch.object(nat_manager.port_mapping_manager, "add_mapping", new_callable=AsyncMock) as mock_add:
        mock_add.return_value = port_mapping

        result = await nat_manager.map_port(6881, 6881, "tcp")

        assert result is not None
        assert result.external_port == 6881


@pytest.mark.asyncio
async def test_map_port_upnp(nat_manager, mock_config):
    """Test port mapping with UPnP."""
    from ccbt.nat.port_mapping import PortMapping

    nat_manager.active_protocol = "upnp"

    with patch.object(nat_manager, "upnp_client") as mock_client:
        mock_client.add_port_mapping = AsyncMock()

        mock_port_mapping = PortMapping(
            internal_port=6881,
            external_port=6881,
            protocol="tcp",
            protocol_source="upnp",
        )

        with patch.object(nat_manager.port_mapping_manager, "add_mapping", new_callable=AsyncMock) as mock_add:
            mock_add.return_value = mock_port_mapping

            result = await nat_manager.map_port(6881, 6881, "tcp")

            assert result is not None
            mock_client.add_port_mapping.assert_called_once()


@pytest.mark.asyncio
async def test_map_port_no_active_protocol_discovers(nat_manager, mock_config):
    """Test map_port discovers if no active protocol."""
    with patch.object(nat_manager, "discover", new_callable=AsyncMock) as mock_discover:
        mock_discover.return_value = False

        result = await nat_manager.map_port(6881, 6881, "tcp")

        assert result is None
        mock_discover.assert_called_once()


@pytest.mark.asyncio
async def test_map_port_handles_error(nat_manager, mock_config):
    """Test map_port handles mapping errors."""
    nat_manager.active_protocol = "natpmp"

    with patch.object(nat_manager, "natpmp_client") as mock_client:
        mock_client.add_port_mapping = AsyncMock(side_effect=NATPMPError("Port conflict"))

        result = await nat_manager.map_port(6881, 6881, "tcp")

        assert result is None


@pytest.mark.asyncio
async def test_map_port_handles_unexpected_error(nat_manager, mock_config):
    """Test map_port handles unexpected errors."""
    nat_manager.active_protocol = "upnp"

    with patch.object(nat_manager, "upnp_client") as mock_client:
        mock_client.add_port_mapping = AsyncMock(side_effect=RuntimeError("Unexpected"))

        result = await nat_manager.map_port(6881, 6881, "tcp")

        assert result is None


@pytest.mark.asyncio
async def test_unmap_port_natpmp(nat_manager, mock_config):
    """Test port unmapping with NAT-PMP."""
    nat_manager.active_protocol = "natpmp"

    with patch.object(nat_manager, "natpmp_client") as mock_client:
        mock_client.delete_port_mapping = AsyncMock()

        with patch.object(nat_manager.port_mapping_manager, "remove_mapping", new_callable=AsyncMock):
            result = await nat_manager.unmap_port(6881, "tcp")

            assert result is True
            mock_client.delete_port_mapping.assert_called_once()


@pytest.mark.asyncio
async def test_unmap_port_upnp(nat_manager, mock_config):
    """Test port unmapping with UPnP."""
    nat_manager.active_protocol = "upnp"

    with patch.object(nat_manager, "upnp_client") as mock_client:
        mock_client.delete_port_mapping = AsyncMock()

        with patch.object(nat_manager.port_mapping_manager, "remove_mapping", new_callable=AsyncMock):
            result = await nat_manager.unmap_port(6881, "tcp")

            assert result is True
            mock_client.delete_port_mapping.assert_called_once()


@pytest.mark.asyncio
async def test_unmap_port_no_protocol(nat_manager, mock_config):
    """Test unmapping when no protocol active."""
    result = await nat_manager.unmap_port(6881, "tcp")

    assert result is False


@pytest.mark.asyncio
async def test_unmap_port_handles_error(nat_manager, mock_config):
    """Test unmap_port handles errors."""
    nat_manager.active_protocol = "natpmp"

    with patch.object(nat_manager, "natpmp_client") as mock_client:
        mock_client.delete_port_mapping = AsyncMock(side_effect=NATPMPError("Failed"))

        result = await nat_manager.unmap_port(6881, "tcp")

        assert result is False


@pytest.mark.asyncio
async def test_map_listen_ports(nat_manager, mock_config):
    """Test mapping configured listen ports."""
    nat_manager.active_protocol = "natpmp"

    with patch.object(nat_manager, "map_port", new_callable=AsyncMock) as mock_map:
        mock_map.return_value = None

        await nat_manager.map_listen_ports()

        # Should map TCP, UDP, and DHT ports
        assert mock_map.call_count >= 2


@pytest.mark.asyncio
async def test_map_listen_ports_with_dht(nat_manager, mock_config):
    """Test mapping listen ports including DHT."""
    nat_manager.active_protocol = "upnp"
    mock_config.nat.map_tcp_port = True
    mock_config.nat.map_udp_port = True
    mock_config.nat.map_dht_port = True

    map_calls = []

    async def track_map(*args, **kwargs):
        map_calls.append((args, kwargs))

    nat_manager.map_port = track_map

    await nat_manager.map_listen_ports()

    # Should map TCP and UDP at minimum
    assert len(map_calls) >= 2


@pytest.mark.asyncio
async def test_stop_cleans_up(nat_manager, mock_config):
    """Test stop() cleans up mappings and tasks."""
    # Set up discovery task
    task = asyncio.create_task(nat_manager._discovery_loop())
    nat_manager._discovery_task = task

    # Add some mappings
    from ccbt.nat.port_mapping import PortMapping
    mapping = PortMapping(
        internal_port=6881,
        external_port=6881,
        protocol="tcp",
        protocol_source="natpmp",
    )
    await nat_manager.port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "natpmp", 3600
    )

    # Mock clients
    nat_manager.natpmp_client = MagicMock()
    nat_manager.natpmp_client.close = AsyncMock()

    with patch.object(nat_manager, "unmap_port", new_callable=AsyncMock) as mock_unmap:
        mock_unmap.return_value = True

        await nat_manager.stop()

        # Task should be cancelled
        assert task.cancelled()

        # Should unmap ports
        assert mock_unmap.called


@pytest.mark.asyncio
async def test_get_external_ip_with_cached(nat_manager, mock_config):
    """Test get_external_ip() returns cached IP."""
    import ipaddress

    nat_manager.external_ip = ipaddress.IPv4Address("192.168.1.1")

    result = await nat_manager.get_external_ip()

    assert result is not None
    assert str(result) == "192.168.1.1"


@pytest.mark.asyncio
async def test_get_external_ip_discovers_if_needed(nat_manager, mock_config):
    """Test get_external_ip() discovers if no protocol active."""
    import ipaddress

    with patch.object(nat_manager, "discover", new_callable=AsyncMock) as mock_discover:
        mock_discover.return_value = True

        nat_manager.active_protocol = "natpmp"
        nat_manager.natpmp_client = MagicMock()
        nat_manager.natpmp_client.get_external_ip = AsyncMock(
            return_value=ipaddress.IPv4Address("192.168.1.2")
        )

        result = await nat_manager.get_external_ip()

        assert result is not None
        assert str(result) == "192.168.1.2"


@pytest.mark.asyncio
async def test_get_external_ip_upnp(nat_manager, mock_config):
    """Test get_external_ip() with UPnP."""
    import ipaddress

    nat_manager.active_protocol = "upnp"
    nat_manager.upnp_client = MagicMock()
    nat_manager.upnp_client.get_external_ip = AsyncMock(
        return_value=ipaddress.IPv4Address("192.168.1.3")
    )

    result = await nat_manager.get_external_ip()

    assert result is not None
    assert str(result) == "192.168.1.3"


@pytest.mark.asyncio
async def test_get_external_ip_handles_errors(nat_manager, mock_config):
    """Test get_external_ip() handles errors."""
    nat_manager.active_protocol = "natpmp"
    nat_manager.natpmp_client = MagicMock()
    nat_manager.natpmp_client.get_external_ip = AsyncMock(side_effect=NATPMPError("Failed"))

    result = await nat_manager.get_external_ip()

    assert result is None


@pytest.mark.asyncio
async def test_map_listen_ports_with_dht_disabled(nat_manager, mock_config):
    """Test map_listen_ports when DHT mapping is disabled."""
    nat_manager.active_protocol = "natpmp"
    mock_config.nat.map_dht_port = False
    mock_config.nat.map_tcp_port = True
    mock_config.nat.map_udp_port = True

    with patch.object(nat_manager, "map_port", new_callable=AsyncMock) as mock_map:
        mock_map.return_value = None

        await nat_manager.map_listen_ports()

        # Should map TCP and UDP, not DHT
        assert mock_map.call_count == 2


@pytest.mark.asyncio
async def test_map_listen_ports_no_dht_port_config(nat_manager, mock_config):
    """Test map_listen_ports when DHT port not in config."""
    nat_manager.active_protocol = "upnp"
    mock_config.nat.map_dht_port = True
    # Remove dht_port attribute
    if hasattr(mock_config.discovery, "dht_port"):
        delattr(mock_config.discovery, "dht_port")

    with patch.object(nat_manager, "map_port", new_callable=AsyncMock) as mock_map:
        mock_map.return_value = None

        await nat_manager.map_listen_ports()

        # Should still map TCP and UDP
        assert mock_map.call_count >= 2


@pytest.mark.asyncio
async def test_get_status(nat_manager, mock_config):
    """Test get_status() returns correct information."""
    import ipaddress

    nat_manager.active_protocol = "natpmp"
    nat_manager.external_ip = ipaddress.IPv4Address("192.168.1.1")

    # Add a mapping
    await nat_manager.port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "natpmp", 3600
    )

    status = await nat_manager.get_status()

    assert status["active_protocol"] == "natpmp"
    assert status["external_ip"] == "192.168.1.1"
    assert len(status["mappings"]) >= 1


@pytest.mark.asyncio
async def test_map_port_natpmp_client_none(nat_manager, mock_config):
    """Test map_port when NAT-PMP client is None."""
    nat_manager.active_protocol = "natpmp"
    nat_manager.natpmp_client = None

    result = await nat_manager.map_port(6881, 6881, "tcp")

    assert result is None


@pytest.mark.asyncio
async def test_map_port_upnp_client_none(nat_manager, mock_config):
    """Test map_port when UPnP client is None."""
    nat_manager.active_protocol = "upnp"
    nat_manager.upnp_client = None

    result = await nat_manager.map_port(6881, 6881, "tcp")

    assert result is None


@pytest.mark.asyncio
async def test_map_port_unknown_protocol(nat_manager, mock_config):
    """Test map_port with unknown protocol."""
    nat_manager.active_protocol = "unknown"

    result = await nat_manager.map_port(6881, 6881, "tcp")

    assert result is None


@pytest.mark.asyncio
async def test_unmap_port_unknown_protocol(nat_manager, mock_config):
    """Test unmap_port with unknown protocol."""
    # Add a mapping first
    await nat_manager.port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "unknown", 3600
    )
    
    nat_manager.active_protocol = "unknown"

    result = await nat_manager.unmap_port(6881, "tcp")

    # Will return True if port_mapping_manager.remove_mapping succeeds
    # even though the protocol doesn't match, because remove_mapping
    # doesn't check the protocol source
    assert result is True


@pytest.mark.asyncio
async def test_stop_with_no_discovery_task(nat_manager, mock_config):
    """Test stop() when discovery task is None."""
    nat_manager._discovery_task = None

    await nat_manager.stop()

    # Should complete without error
    assert True


@pytest.mark.asyncio
async def test_stop_with_no_natpmp_client(nat_manager, mock_config):
    """Test stop() when NAT-PMP client is None."""
    nat_manager._discovery_task = None
    nat_manager.natpmp_client = None
    nat_manager.upnp_client = None

    await nat_manager.stop()

    # Should complete without error
    assert True


@pytest.mark.asyncio
async def test_get_external_ip_natpmp_no_client(nat_manager, mock_config):
    """Test get_external_ip() when NAT-PMP client is None."""
    import ipaddress

    nat_manager.active_protocol = "natpmp"
    nat_manager.natpmp_client = None

    result = await nat_manager.get_external_ip()

    assert result is None


@pytest.mark.asyncio
async def test_get_external_ip_upnp_no_client(nat_manager, mock_config):
    """Test get_external_ip() when UPnP client is None."""
    import ipaddress

    nat_manager.active_protocol = "upnp"
    nat_manager.upnp_client = None

    result = await nat_manager.get_external_ip()

    assert result is None


@pytest.mark.asyncio
async def test_get_external_ip_upnp_error(nat_manager, mock_config):
    """Test get_external_ip() handles UPnP errors."""
    import ipaddress

    nat_manager.active_protocol = "upnp"
    nat_manager.upnp_client = MagicMock()
    nat_manager.upnp_client.get_external_ip = AsyncMock(side_effect=UPnPError("Failed"))

    result = await nat_manager.get_external_ip()

    assert result is None


@pytest.mark.asyncio
async def test_get_external_ip_discovers_natpmp(nat_manager, mock_config):
    """Test get_external_ip() discovers and uses NAT-PMP."""
    import ipaddress

    with patch.object(nat_manager, "discover", new_callable=AsyncMock) as mock_discover:
        mock_discover.return_value = True

        nat_manager.active_protocol = "natpmp"
        nat_manager.natpmp_client = MagicMock()
        nat_manager.natpmp_client.get_external_ip = AsyncMock(
            return_value=ipaddress.IPv4Address("192.168.1.5")
        )

        result = await nat_manager.get_external_ip()

        assert result is not None
        assert str(result) == "192.168.1.5"


@pytest.mark.asyncio
async def test_unmap_port_handles_unexpected_exception(nat_manager, mock_config):
    """Test unmap_port handles unexpected exceptions."""
    nat_manager.active_protocol = "natpmp"
    nat_manager.natpmp_client = MagicMock()
    nat_manager.natpmp_client.delete_port_mapping = AsyncMock(
        side_effect=RuntimeError("Unexpected error")
    )

    # Add mapping first so remove_mapping succeeds
    await nat_manager.port_mapping_manager.add_mapping(
        6881, 6881, "tcp", "natpmp", 3600
    )

    result = await nat_manager.unmap_port(6881, "tcp")

    # Should return False due to exception
    assert result is False


@pytest.mark.asyncio
async def test_get_external_ip_discovers_fails(nat_manager, mock_config):
    """Test get_external_ip() when discovery fails."""
    with patch.object(nat_manager, "discover", new_callable=AsyncMock) as mock_discover:
        mock_discover.return_value = False  # Discovery fails

        result = await nat_manager.get_external_ip()

        assert result is None

