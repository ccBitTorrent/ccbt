# Tracker Compatibility Tests

Tests that verify ccBitTorrent works correctly with real BitTorrent trackers.

## Test Requirements

- Network connectivity
- Access to public BitTorrent trackers
- Stable network conditions

## Example Test Structure

```python
"""Compatibility test for real tracker."""

import pytest

pytestmark = [pytest.mark.compatibility, pytest.mark.slow, pytest.mark.tracker]

@pytest.mark.asyncio
async def test_announce_to_real_tracker():
    """Test announcing to a real tracker."""
    # This test would connect to a real tracker
    # and verify the announce protocol works correctly
    pass
```

## Notes

- These tests may be flaky due to network conditions
- Consider using retry logic
- Tests should be optional in CI (warn, don't fail)



