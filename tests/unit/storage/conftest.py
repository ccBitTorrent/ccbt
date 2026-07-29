"""Shared fixtures for storage unit tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_db_path() -> str:
    """Provide an isolated SQLite cache path with a dedicated chunk store directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield str(Path(tmpdir) / "cache.db")
