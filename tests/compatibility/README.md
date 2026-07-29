# Compatibility Tests

This directory contains compatibility tests that verify ccBitTorrent works correctly with real BitTorrent trackers, peers, and protocols.

## Test Categories

- **trackers/**: Tests against real BitTorrent trackers
- **peers/**: Tests against real BitTorrent peers
- **protocols/**: Protocol compliance tests
- **interoperability/**: Cross-client compatibility tests

## Running Compatibility Tests

### Local Development
```bash
# Run all compatibility tests
uv run pytest -c dev/pytest.ini tests/compatibility/ -m "compatibility"

# Run specific category
uv run pytest -c dev/pytest.ini tests/compatibility/trackers/
```

### CI/CD
Compatibility tests run automatically in CI/CD pipelines but are excluded from pre-commit hooks.

## Test Requirements

- Network connectivity
- Access to public BitTorrent trackers (for tracker tests)
- Stable network conditions (tests may be flaky)

## Test Markers

All tests in this directory should be marked with:
- `@pytest.mark.compatibility` - Marks as compatibility test
- `@pytest.mark.slow` - Marks as slow test

## Notes

- These tests may be flaky due to network conditions
- Consider retry logic for network-dependent tests
- Tests should be optional in CI (warn, don't fail on network issues)



