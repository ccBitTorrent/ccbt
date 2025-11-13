"""Tests for PEX refresh functionality in AsyncPexManager."""

from __future__ import annotations

import pytest
import time

from ccbt.discovery.pex import AsyncPexManager, PexSession


@pytest.mark.asyncio
async def test_pex_manager_refresh():
    """Test refresh method triggers PEX sending."""
    manager = AsyncPexManager()
    
    # Create a mock session
    session = PexSession(peer_key="test_peer", is_supported=True, ut_pex_id=1)
    session.last_pex_time = time.time()  # Set to current time
    
    manager.sessions["test_peer"] = session
    
    # Mock the _send_pex_messages method
    send_called = []
    
    async def mock_send_pex_messages():
        send_called.append(1)
    
    manager._send_pex_messages = mock_send_pex_messages
    
    # Call refresh
    await manager.refresh()
    
    # Verify that last_pex_time was reset and send was called
    assert session.last_pex_time == 0.0
    assert len(send_called) == 1


@pytest.mark.asyncio
async def test_pex_manager_refresh_resets_timers():
    """Test that last_pex_time is reset for all supported sessions."""
    manager = AsyncPexManager()
    
    # Create multiple sessions
    session1 = PexSession(peer_key="peer1", is_supported=True, ut_pex_id=1)
    session1.last_pex_time = time.time()
    
    session2 = PexSession(peer_key="peer2", is_supported=True, ut_pex_id=2)
    session2.last_pex_time = time.time()
    
    session3 = PexSession(peer_key="peer3", is_supported=False, ut_pex_id=3)
    session3.last_pex_time = time.time()
    
    manager.sessions["peer1"] = session1
    manager.sessions["peer2"] = session2
    manager.sessions["peer3"] = session3
    
    # Mock the _send_pex_messages method
    async def mock_send_pex_messages():
        pass
    
    manager._send_pex_messages = mock_send_pex_messages
    
    # Call refresh
    await manager.refresh()
    
    # Verify that only supported sessions had their timers reset
    assert session1.last_pex_time == 0.0
    assert session2.last_pex_time == 0.0
    assert session3.last_pex_time != 0.0  # Not supported, should not be reset


@pytest.mark.asyncio
async def test_pex_manager_refresh_with_no_peers():
    """Test refresh with no supported peers."""
    manager = AsyncPexManager()
    
    # No sessions
    send_called = []
    
    async def mock_send_pex_messages():
        send_called.append(1)
    
    manager._send_pex_messages = mock_send_pex_messages
    
    # Call refresh
    await manager.refresh()
    
    # Should still call send_pex_messages (it will just iterate over empty list)
    assert len(send_called) == 1


@pytest.mark.asyncio
async def test_pex_manager_refresh_error_handling():
    """Test error handling in refresh."""
    manager = AsyncPexManager()
    
    session = PexSession(peer_key="test_peer", is_supported=True, ut_pex_id=1)
    manager.sessions["test_peer"] = session
    
    # Mock _send_pex_messages to raise an exception
    async def mock_send_pex_messages():
        raise Exception("Test error")
    
    manager._send_pex_messages = mock_send_pex_messages
    
    # Call refresh - should not raise, just log warning
    await manager.refresh()
    
    # Verify timer was still reset
    assert session.last_pex_time == 0.0


@pytest.mark.asyncio
async def test_pex_manager_send_pex_with_callback():
    """Test sending PEX via callback."""
    manager = AsyncPexManager()
    
    session = PexSession(peer_key="test_peer", is_supported=True, ut_pex_id=1)
    manager.sessions["test_peer"] = session
    
    callback_called = []
    callback_args = []
    
    # Mock get_connected_peers_callback to return some peers
    async def mock_get_peers() -> list[tuple[str, int]]:
        return [("192.168.1.1", 6881), ("192.168.1.2", 6882)]
    
    manager.get_connected_peers_callback = mock_get_peers
    
    async def mock_callback(peer_key: str, peer_data: bytes, is_added: bool = True) -> bool:
        callback_called.append(1)
        callback_args.append((peer_key, peer_data, is_added))
        return True
    
    manager.send_pex_callback = mock_callback
    
    # Call _send_pex_to_peer
    await manager._send_pex_to_peer(session)
    
    # Verify callback was called (should be called for added peers)
    assert len(callback_called) > 0
    assert callback_args[0][0] == "test_peer"
    assert session.consecutive_failures == 0


@pytest.mark.asyncio
async def test_pex_manager_send_pex_without_callback():
    """Test behavior without callback."""
    manager = AsyncPexManager()
    
    session = PexSession(peer_key="test_peer", is_supported=True, ut_pex_id=1)
    manager.sessions["test_peer"] = session
    
    # No callback set
    manager.send_pex_callback = None
    
    # Call _send_pex_to_peer - should return early without error
    await manager._send_pex_to_peer(session)
    
    # Should not have changed consecutive_failures
    assert session.consecutive_failures == 0


@pytest.mark.asyncio
async def test_pex_manager_send_pex_not_supported():
    """Test sending PEX to unsupported peer."""
    manager = AsyncPexManager()
    
    session = PexSession(peer_key="test_peer", is_supported=False, ut_pex_id=1)
    manager.sessions["test_peer"] = session
    
    callback_called = []
    
    async def mock_callback(peer_key: str, message: bytes) -> bool:
        callback_called.append(1)
        return True
    
    manager.send_pex_callback = mock_callback
    
    # Call _send_pex_to_peer - should return early
    await manager._send_pex_to_peer(session)
    
    # Callback should not have been called
    assert len(callback_called) == 0


@pytest.mark.asyncio
async def test_pex_manager_send_pex_callback_failure():
    """Test handling of callback failure."""
    manager = AsyncPexManager()
    
    session = PexSession(peer_key="test_peer", is_supported=True, ut_pex_id=1)
    manager.sessions["test_peer"] = session
    initial_failures = session.consecutive_failures
    
    # Mock get_connected_peers_callback to return some peers
    async def mock_get_peers() -> list[tuple[str, int]]:
        return [("192.168.1.1", 6881), ("192.168.1.2", 6882)]
    
    manager.get_connected_peers_callback = mock_get_peers
    
    async def mock_callback(peer_key: str, peer_data: bytes, is_added: bool = True) -> bool:
        return False  # Simulate failure
    
    manager.send_pex_callback = mock_callback
    
    # Call _send_pex_to_peer
    await manager._send_pex_to_peer(session)
    
    # Should increment consecutive_failures (one for added peers, possibly one for dropped)
    assert session.consecutive_failures > initial_failures


@pytest.mark.asyncio
async def test_pex_manager_send_pex_callback_exception():
    """Test handling of callback exception."""
    manager = AsyncPexManager()
    
    session = PexSession(peer_key="test_peer", is_supported=True, ut_pex_id=1)
    manager.sessions["test_peer"] = session
    initial_failures = session.consecutive_failures
    
    # Mock get_connected_peers_callback to return some peers
    async def mock_get_peers() -> list[tuple[str, int]]:
        return [("192.168.1.1", 6881), ("192.168.1.2", 6882)]
    
    manager.get_connected_peers_callback = mock_get_peers
    
    async def mock_callback(peer_key: str, peer_data: bytes, is_added: bool = True) -> bool:
        raise Exception("Callback error")
    
    manager.send_pex_callback = mock_callback
    
    # Call _send_pex_to_peer - should handle exception gracefully
    await manager._send_pex_to_peer(session)
    
    # Should increment consecutive_failures (one for added peers exception)
    assert session.consecutive_failures > initial_failures

