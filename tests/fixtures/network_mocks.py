"""Network operation mocks for unit tests.

This module provides reusable fixtures and helpers for mocking network operations
(DHT, TCP server, NAT) to prevent actual network operations in unit tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from typing import Any

import pytest


@pytest.fixture
def mock_nat_manager():
    """Create a mocked NAT manager that doesn't perform actual network operations.
    
    Returns:
        MagicMock: Mocked NAT manager with async start/stop methods
    """
    mock_nat = MagicMock()
    mock_nat.start = AsyncMock()
    mock_nat.stop = AsyncMock()
    mock_nat.map_listen_ports = AsyncMock()
    mock_nat.wait_for_mapping = AsyncMock()
    mock_nat.get_external_port = AsyncMock(return_value=None)
    mock_nat.get_external_ip = AsyncMock(return_value=None)
    mock_nat.discover = AsyncMock()
    return mock_nat


@pytest.fixture
def mock_dht_client():
    """Create a mocked DHT client that doesn't perform actual network operations.
    
    Returns:
        MagicMock: Mocked DHT client with async start/stop methods
    """
    mock_dht = MagicMock()
    mock_dht.start = AsyncMock()
    mock_dht.stop = AsyncMock()
    mock_dht.bootstrap = AsyncMock()
    mock_dht.get_peers = AsyncMock(return_value=[])
    mock_dht.announce_peer = AsyncMock()
    mock_dht.is_running = False
    return mock_dht


@pytest.fixture
def mock_tcp_server():
    """Create a mocked TCP server that doesn't bind to actual ports.
    
    Returns:
        MagicMock: Mocked TCP server with async start/stop methods
    """
    mock_server = MagicMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.port = None
    mock_server.server = None
    mock_server.is_running = False
    return mock_server


@pytest.fixture
def mock_network_components(mock_nat_manager, mock_dht_client, mock_tcp_server):
    """Create all mocked network components.
    
    Returns:
        dict: Dictionary with 'nat', 'dht', and 'tcp_server' keys
    """
    return {
        "nat": mock_nat_manager,
        "dht": mock_dht_client,
        "tcp_server": mock_tcp_server,
    }


def apply_network_mocks_to_session(session: Any, mock_network_components: dict) -> None:
    """Apply network mocks to an AsyncSessionManager or AsyncTorrentSession.
    
    Args:
        session: Session instance to apply mocks to
        mock_network_components: Dictionary from mock_network_components fixture
    """
    from unittest.mock import patch
    
    # Mock NAT manager creation
    if hasattr(session, "_make_nat_manager"):
        patch.object(session, "_make_nat_manager", return_value=mock_network_components["nat"]).start()
    
    # Mock DHT client
    if hasattr(session, "dht_client"):
        session.dht_client = mock_network_components["dht"]
    
    # Mock TCP server
    if hasattr(session, "tcp_server"):
        session.tcp_server = mock_network_components["tcp_server"]


@pytest.fixture
def session_with_mocked_network(mock_network_components):
    """Fixture that provides a context manager for applying network mocks to sessions.
    
    Usage:
        with session_with_mocked_network() as mocks:
            session = AsyncSessionManager()
            apply_network_mocks_to_session(session, mocks)
            # ... test code ...
    """
    from contextlib import contextmanager
    
    @contextmanager
    def _session_with_mocks():
        yield mock_network_components
    
    return _session_with_mocks()

