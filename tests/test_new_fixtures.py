"""Test the new fixtures and port pool manager to ensure they work correctly."""

from __future__ import annotations

import pytest

from tests.fixtures.network_mocks import (
    apply_network_mocks_to_session,
)
from tests.utils.port_pool import PortPool, get_free_port


class TestPortPool:
    """Test port pool manager functionality."""

    def test_port_pool_singleton(self):
        """Test that PortPool is a singleton."""
        pool1 = PortPool.get_instance()
        pool2 = PortPool.get_instance()
        assert pool1 is pool2

    def test_get_free_port_allocates_unique_ports(self):
        """Test that get_free_port returns unique ports."""
        pool = PortPool.get_instance()
        pool.release_all_ports()  # Start fresh

        port1 = get_free_port()
        port2 = get_free_port()
        port3 = get_free_port()

        assert port1 != port2
        assert port2 != port3
        assert port1 != port3

        # Check that ports are tracked
        assert pool.get_allocated_count() == 3
        assert port1 in pool.get_allocated_ports()
        assert port2 in pool.get_allocated_ports()
        assert port3 in pool.get_allocated_ports()

        # Cleanup
        pool.release_all_ports()

    def test_release_port(self):
        """Test releasing a port back to the pool."""
        pool = PortPool.get_instance()
        pool.release_all_ports()

        port = get_free_port()
        assert pool.get_allocated_count() == 1

        pool.release_port(port)
        assert pool.get_allocated_count() == 0
        assert port not in pool.get_allocated_ports()

    def test_release_all_ports(self):
        """Test releasing all ports at once."""
        pool = PortPool.get_instance()
        pool.release_all_ports()

        port1 = get_free_port()
        port2 = get_free_port()
        assert pool.get_allocated_count() == 2

        pool.release_all_ports()
        assert pool.get_allocated_count() == 0

    def test_port_is_actually_available(self):
        """Test that allocated ports are actually available (not in use by OS)."""
        import socket

        pool = PortPool.get_instance()
        pool.release_all_ports()

        port = get_free_port()

        # Try to bind to the port - should succeed since it's available
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                # Port is available
                assert True
        except OSError:
            pytest.fail(f"Port {port} should be available but bind failed")
        finally:
            pool.release_port(port)


class TestNetworkMocks:
    """Test network operation mock fixtures."""

    def test_mock_nat_manager(self, mock_nat_manager):
        """Test that mock_nat_manager fixture works."""
        assert mock_nat_manager is not None
        assert hasattr(mock_nat_manager, "start")
        assert hasattr(mock_nat_manager, "stop")
        assert hasattr(mock_nat_manager, "map_listen_ports")
        assert hasattr(mock_nat_manager, "wait_for_mapping")

    @pytest.mark.asyncio
    async def test_mock_nat_manager_async_methods(self, mock_nat_manager):
        """Test that mock NAT manager async methods work."""
        await mock_nat_manager.start()
        await mock_nat_manager.stop()
        await mock_nat_manager.map_listen_ports(6881, 6881)
        await mock_nat_manager.wait_for_mapping(6881, "tcp")

        # Verify methods were called
        mock_nat_manager.start.assert_called_once()
        mock_nat_manager.stop.assert_called_once()

    def test_mock_dht_client(self, mock_dht_client):
        """Test that mock_dht_client fixture works."""
        assert mock_dht_client is not None
        assert hasattr(mock_dht_client, "start")
        assert hasattr(mock_dht_client, "stop")
        assert hasattr(mock_dht_client, "bootstrap")
        assert hasattr(mock_dht_client, "get_peers")

    @pytest.mark.asyncio
    async def test_mock_dht_client_async_methods(self, mock_dht_client):
        """Test that mock DHT client async methods work."""
        await mock_dht_client.start()
        await mock_dht_client.stop()
        await mock_dht_client.bootstrap([("127.0.0.1", 6881)])
        peers = await mock_dht_client.get_peers(b"test_hash")

        assert peers == []
        mock_dht_client.start.assert_called_once()
        mock_dht_client.stop.assert_called_once()

    def test_mock_tcp_server(self, mock_tcp_server):
        """Test that mock_tcp_server fixture works."""
        assert mock_tcp_server is not None
        assert hasattr(mock_tcp_server, "start")
        assert hasattr(mock_tcp_server, "stop")
        assert mock_tcp_server.port is None
        assert mock_tcp_server.is_running is False

    @pytest.mark.asyncio
    async def test_mock_tcp_server_async_methods(self, mock_tcp_server):
        """Test that mock TCP server async methods work."""
        await mock_tcp_server.start()
        await mock_tcp_server.stop()

        mock_tcp_server.start.assert_called_once()
        mock_tcp_server.stop.assert_called_once()

    def test_mock_network_components(self, mock_network_components):
        """Test that mock_network_components fixture provides all components."""
        assert "nat" in mock_network_components
        assert "dht" in mock_network_components
        assert "tcp_server" in mock_network_components

        assert mock_network_components["nat"] is not None
        assert mock_network_components["dht"] is not None
        assert mock_network_components["tcp_server"] is not None

    @pytest.mark.asyncio
    async def test_apply_network_mocks_to_session(self, mock_network_components):
        """Test applying network mocks to a session."""
        from unittest.mock import MagicMock

        # Create a mock session
        session = MagicMock()
        session._make_nat_manager = MagicMock()
        session.dht_client = None
        session.tcp_server = None

        # Apply mocks
        from unittest.mock import patch
        with patch.object(session, "_make_nat_manager", return_value=mock_network_components["nat"]):
            apply_network_mocks_to_session(session, mock_network_components)

            # Verify mocks were applied
            assert session.dht_client == mock_network_components["dht"]
            assert session.tcp_server == mock_network_components["tcp_server"]






