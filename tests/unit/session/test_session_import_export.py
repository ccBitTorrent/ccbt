"""Tests for session import/export functionality."""

import pytest
import json
from pathlib import Path


@pytest.mark.asyncio
async def test_export_session_state_writes_json(monkeypatch, tmp_path):
    """Test export_session_state writes session data to JSON file."""
    from ccbt.session.session import AsyncSessionManager

    class _Session:
        async def get_status(self):
            return {"name": "test-torrent", "progress": 0.5}

    mgr = AsyncSessionManager(str(tmp_path))
    ih_bytes = b"1" * 20

    async with mgr.lock:
        mgr.torrents[ih_bytes] = _Session()

    export_path = tmp_path / "session.json"
    await mgr.export_session_state(export_path)

    assert export_path.exists()
    data = json.loads(export_path.read_text(encoding="utf-8"))
    assert "torrents" in data
    assert "config" in data
    assert ih_bytes.hex() in data["torrents"]
    assert data["torrents"][ih_bytes.hex()]["name"] == "test-torrent"


@pytest.mark.asyncio
async def test_export_session_state_with_empty_torrents(tmp_path):
    """Test export_session_state handles empty torrent list."""
    from ccbt.session.session import AsyncSessionManager

    mgr = AsyncSessionManager(str(tmp_path))

    export_path = tmp_path / "empty_session.json"
    await mgr.export_session_state(export_path)

    assert export_path.exists()
    data = json.loads(export_path.read_text(encoding="utf-8"))
    assert data["torrents"] == {}


@pytest.mark.asyncio
async def test_import_session_state_reads_json(tmp_path):
    """Test import_session_state reads and parses JSON file."""
    from ccbt.session.session import AsyncSessionManager

    session_data = {
        "torrents": {
            "a" * 40: {"name": "torrent1", "progress": 0.5},
            "b" * 40: {"name": "torrent2", "progress": 0.8},
        },
        "config": {"network": {"port": 6881}},
    }

    import_path = tmp_path / "session.json"
    import_path.write_text(json.dumps(session_data), encoding="utf-8")

    mgr = AsyncSessionManager(str(tmp_path))
    data = await mgr.import_session_state(import_path)

    assert data == session_data
    assert len(data["torrents"]) == 2
    assert "a" * 40 in data["torrents"]


@pytest.mark.asyncio
async def test_import_session_state_handles_malformed_json(tmp_path):
    """Test import_session_state raises error for malformed JSON."""
    from ccbt.session.session import AsyncSessionManager

    import_path = tmp_path / "bad.json"
    import_path.write_text("{invalid json}", encoding="utf-8")

    mgr = AsyncSessionManager(str(tmp_path))

    with pytest.raises(json.JSONDecodeError):
        await mgr.import_session_state(import_path)

