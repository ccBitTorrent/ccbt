"""Unit tests that BEP 53 apply is invoked after metadata merge (dht_setup path)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]


@pytest.mark.asyncio
async def test_dht_setup_apply_bep53_after_metadata_calls_session():
    """DHTDiscoverySetup._apply_bep53_after_metadata calls session._apply_magnet_file_selection_if_needed."""
    from ccbt.session.dht_setup import DHTDiscoverySetup

    session = Mock()
    session.logger = Mock()
    session._apply_magnet_file_selection_if_needed = AsyncMock()

    setup = DHTDiscoverySetup(session)
    await setup._apply_bep53_after_metadata()

    session._apply_magnet_file_selection_if_needed.assert_awaited_once()
