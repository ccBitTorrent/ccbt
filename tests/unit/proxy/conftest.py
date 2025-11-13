"""Shared fixtures and helpers for proxy tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


class AsyncContextManagerMock:
    """Helper class for creating async context manager mocks."""

    def __init__(self, response: AsyncMock):
        """Initialize with a mock response."""
        self.response = response

    async def __aenter__(self):
        """Enter async context."""
        # If response is a coroutine, await it
        if hasattr(self.response, '__await__'):
            return await self.response
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        return None
    
    def __await__(self):
        """Make this awaitable to support direct await."""
        # Not needed for context manager, but helps with compatibility
        return iter([])


def create_async_response_mock(status: int = 200, headers: dict | None = None) -> AsyncMock:
    """Create a properly configured async response mock.
    
    Args:
        status: HTTP status code
        headers: Response headers
        
    Returns:
        Configured AsyncMock response
    """
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.headers = headers or {}
    mock_response.read = AsyncMock(return_value=b"test data")
    return mock_response


def create_async_session_mock(responses: list[AsyncMock] | None = None) -> AsyncMock:
    """Create a properly configured async session mock.
    
    Args:
        responses: List of response mocks to return (cycled)
        
    Returns:
        Configured AsyncMock session
    """
    if responses is None:
        responses = [create_async_response_mock()]
    
    response_iter = iter(responses)
    
    def get_response(*args, **kwargs):
        try:
            response = next(response_iter)
        except StopIteration:
            response = responses[-1]  # Use last response if exhausted
        return AsyncContextManagerMock(response)
    
    mock_session = AsyncMock()
    mock_session.get = MagicMock(side_effect=get_response)
    mock_session.close = AsyncMock()
    return mock_session

