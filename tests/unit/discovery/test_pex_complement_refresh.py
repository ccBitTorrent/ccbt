"""PEX refresh as DHT-throttle complement."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ccbt.discovery.pex import AsyncPexManager


@pytest.mark.asyncio
async def test_pex_refresh_calls_send_messages() -> None:
    """refresh() resets timing and invokes _send_pex_messages."""
    mgr = AsyncPexManager()
    with patch.object(mgr, "_send_pex_messages", new_callable=AsyncMock) as send:
        await mgr.refresh()
    send.assert_awaited_once()
