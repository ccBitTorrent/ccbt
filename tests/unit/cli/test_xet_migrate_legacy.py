"""CLI migrate-legacy (G9 / C17)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ccbt.core.tonic import TonicFile
from ccbt.storage.xet_migrate_legacy import migrate_legacy_workspace

pytestmark = [pytest.mark.timeout(30), pytest.mark.cli]


def test_xet_cli_migrate_legacy(tmp_path: Path) -> None:
    ws = tmp_path / "legacy_ws"
    ws.mkdir()
    (ws / "a.bin").write_bytes(b"legacy-content-" * 200)
    report = migrate_legacy_workspace(ws)
    assert report.ok
    assert report.files_migrated == 1
    assert report.chunks_written >= 1
    assert report.tonic_path
    parsed = TonicFile().parse(report.tonic_path)
    assert parsed.get("format_version") == 2 or parsed["info"].get("format_version") == 2
    assert "xet-blake3-gearhash-lz4:v2" in (
        parsed.get("suite") or parsed["info"].get("suite", "")
    )
