"""Compatibility tests for ccBitTorrent.

These tests verify compatibility with real BitTorrent trackers, peers, and protocols.
They require network connectivity and may be flaky due to external dependencies.

These tests are NOT run in pre-commit hooks - they run only in CI/CD pipelines.
"""

from __future__ import annotations

import pytest

# Register compatibility marker if not already registered
pytestmark = [pytest.mark.compatibility, pytest.mark.slow]



