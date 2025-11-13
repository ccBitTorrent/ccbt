"""Tests for state manager with msgpack serialization.

from __future__ import annotations

Tests state save/load, JSON export, and state migration.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ccbt.daemon.state_manager import StateManager
from ccbt.daemon.state_models import DaemonState, SessionState, TorrentState
from ccbt.session.session import AsyncSessionManager


@pytest.fixture
def temp_state_dir():
    """Create temporary state directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def state_manager(temp_state_dir):
    """Create state manager for testing."""
    return StateManager(state_dir=temp_state_dir)


@pytest.mark.asyncio
async def test_save_and_load_state(state_manager, temp_state_dir):
    """Test saving and loading state."""
    # Create a test state
    state = DaemonState(
        version="1.0",
        torrents={
            "abc123": TorrentState(
                info_hash="abc123",
                name="Test Torrent",
                status="downloading",
                progress=0.5,
                output_dir=str(temp_state_dir),
            ),
        },
        session=SessionState(),
    )

    # Save state (using a mock session manager)
    class MockSessionManager:
        async def get_status(self):
            return {
                "abc123": {
                    "name": "Test Torrent",
                    "status": "downloading",
                    "progress": 0.5,
                    "output_dir": str(temp_state_dir),
                    "download_rate": 1000.0,
                    "upload_rate": 500.0,
                    "num_peers": 5,
                    "total_size": 1000000,
                    "downloaded": 500000,
                    "uploaded": 250000,
                },
            }

        async def get_global_stats(self):
            return {
                "num_torrents": 1,
                "download_rate": 1000.0,
                "upload_rate": 500.0,
            }

        @property
        def config(self):
            class MockConfig:
                discovery = type("obj", (object,), {"enable_dht": False})()
                nat = type("obj", (object,), {"auto_map_ports": False})()

            return MockConfig()

        @property
        def dht_client(self):
            return None

    mock_session = MockSessionManager()
    await state_manager.save_state(mock_session)

    # Verify file was created
    assert state_manager.state_file.exists()

    # Load state
    loaded_state = await state_manager.load_state()
    assert loaded_state is not None
    assert loaded_state.version == "1.0"
    assert len(loaded_state.torrents) == 1
    assert "abc123" in loaded_state.torrents
    assert loaded_state.torrents["abc123"].name == "Test Torrent"


@pytest.mark.asyncio
async def test_json_export(state_manager, temp_state_dir):
    """Test JSON export functionality."""
    # Create and save a test state
    state = DaemonState(
        version="1.0",
        torrents={
            "abc123": TorrentState(
                info_hash="abc123",
                name="Test Torrent",
                status="downloading",
                progress=0.5,
                output_dir=str(temp_state_dir),
            ),
        },
        session=SessionState(),
    )

    # Save state first
    class MockSessionManager:
        async def get_status(self):
            return {
                "abc123": {
                    "name": "Test Torrent",
                    "status": "downloading",
                    "progress": 0.5,
                    "output_dir": str(temp_state_dir),
                    "download_rate": 0.0,
                    "upload_rate": 0.0,
                    "num_peers": 0,
                    "total_size": 0,
                    "downloaded": 0,
                    "uploaded": 0,
                },
            }

        async def get_global_stats(self):
            return {}

        @property
        def config(self):
            class MockConfig:
                discovery = type("obj", (object,), {"enable_dht": False})()
                nat = type("obj", (object,), {"auto_map_ports": False})()

            return MockConfig()

        @property
        def dht_client(self):
            return None

    mock_session = MockSessionManager()
    await state_manager.save_state(mock_session)

    # Export to JSON
    json_path = await state_manager.export_to_json()

    # Verify JSON file exists and is valid
    assert json_path.exists()
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
        assert "version" in data
        assert "torrents" in data
        assert data["version"] == "1.0"


@pytest.mark.asyncio
async def test_state_validation(state_manager):
    """Test state validation."""
    # Valid state
    valid_state = DaemonState(
        version="1.0",
        torrents={
            "abc123": TorrentState(
                info_hash="abc123",
                name="Test",
                status="downloading",
                progress=0.5,
                output_dir=".",
            ),
        },
        session=SessionState(),
    )

    is_valid = await state_manager.validate_state(valid_state)
    assert is_valid is True

    # Invalid state (progress out of range)
    invalid_state = DaemonState(
        version="1.0",
        torrents={
            "abc123": TorrentState(
                info_hash="abc123",
                name="Test",
                status="downloading",
                progress=1.5,  # Invalid: > 1.0
                output_dir=".",
            ),
        },
        session=SessionState(),
    )

    is_valid = await state_manager.validate_state(invalid_state)
    assert is_valid is False

