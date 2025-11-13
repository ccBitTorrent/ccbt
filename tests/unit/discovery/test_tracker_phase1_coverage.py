"""Additional tests for tracker Phase 1 to achieve 100% coverage.

Tests exponential backoff and linear backoff paths.
"""

from __future__ import annotations

import random
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.tracker, pytest.mark.network]

from ccbt.discovery.tracker import AsyncTrackerClient, TrackerSession


def test_handle_tracker_failure_exponential_backoff():
    """Test _handle_tracker_failure with exponential backoff."""
    client = AsyncTrackerClient()
    url = "http://tracker.example.com/announce"
    
    # Create session
    session = TrackerSession(url=url)
    client.sessions[url] = session
    
    # Set failure count
    session.failure_count = 2
    
    # Mock config for exponential backoff
    with patch.object(client.config.network, 'retry_exponential_backoff', True):
        with patch.object(client.config.network, 'retry_base_delay', 1.0):
            with patch.object(client.config.network, 'retry_max_delay', 300.0):
                # Mock random.uniform
                with patch.object(random, 'uniform', return_value=0.5):
                    client._handle_tracker_failure(url)
                    
                    # Should use exponential backoff: 1.0 * 2^3 + 0.5 = 8.5 (failure_count becomes 3)
                    assert session.backoff_delay >= 8.0  # Allow for calculation
                    assert session.backoff_delay <= 9.0
                    assert session.failure_count == 3


def test_handle_tracker_failure_linear_backoff():
    """Test _handle_tracker_failure with linear backoff."""
    client = AsyncTrackerClient()
    url = "http://tracker.example.com/announce"
    
    # Create session
    session = TrackerSession(url=url)
    client.sessions[url] = session
    
    # Set failure count
    session.failure_count = 2
    
    # Mock config for linear backoff
    with patch.object(client.config.network, 'retry_exponential_backoff', False):
        with patch.object(client.config.network, 'retry_base_delay', 1.0):
            with patch.object(client.config.network, 'retry_max_delay', 300.0):
                # Mock random.uniform
                with patch.object(random, 'uniform', return_value=0.5):
                    client._handle_tracker_failure(url)
                    
                    # Should use linear backoff: 1.0 * 3 + 0.5 = 3.5 (failure_count becomes 3)
                    assert session.backoff_delay == pytest.approx(3.5, abs=0.1)
                    assert session.failure_count == 3


def test_handle_tracker_failure_max_delay_cap():
    """Test _handle_tracker_failure respects max delay."""
    client = AsyncTrackerClient()
    url = "http://tracker.example.com/announce"
    
    # Create session with high failure count
    session = TrackerSession(url=url)
    client.sessions[url] = session
    session.failure_count = 20  # Very high
    
    # Mock config
    with patch.object(client.config.network, 'retry_exponential_backoff', True):
        with patch.object(client.config.network, 'retry_base_delay', 1.0):
            with patch.object(client.config.network, 'retry_max_delay', 300.0):
                with patch.object(random, 'uniform', return_value=0.5):
                    client._handle_tracker_failure(url)
                    
                    # Should be capped at max_delay
                    assert session.backoff_delay <= 300.0


def test_handle_tracker_failure_new_session():
    """Test _handle_tracker_failure creates new session if needed."""
    client = AsyncTrackerClient()
    url = "http://tracker.example.com/announce"
    
    # No session exists yet
    assert url not in client.sessions
    
    # Mock config
    with patch.object(client.config.network, 'retry_exponential_backoff', True):
        with patch.object(client.config.network, 'retry_base_delay', 1.0):
            with patch.object(client.config.network, 'retry_max_delay', 300.0):
                with patch.object(random, 'uniform', return_value=0.5):
                    client._handle_tracker_failure(url)
                    
                    # Should create session
                    assert url in client.sessions
                    assert client.sessions[url].failure_count == 1

