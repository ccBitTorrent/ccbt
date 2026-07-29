"""CLI tests for ``btbt config peer-cap-provenance``."""

from __future__ import annotations

import json
from io import StringIO
from typing import TYPE_CHECKING

import click
import pytest

if TYPE_CHECKING:
    from pathlib import Path

import ccbt.cli.config_commands  # noqa: F401 - register commands on ``config`` group
from ccbt.cli import config_commands

pytestmark = [pytest.mark.unit, pytest.mark.cli]

_EXPECTED_FILE_MPT = 77


def test_peer_cap_provenance_emits_json_with_expected_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Command loads config and prints MaxPeersPerTorrentProvenance as JSON."""
    cfg = tmp_path / "ccbt.toml"
    cfg.write_text(
        "[optimization]\n"
        'profile = "custom"\n'
        "\n"
        "[network]\n"
        f"max_peers_per_torrent = {_EXPECTED_FILE_MPT}\n"
        "\n",
        encoding="utf-8",
    )
    buf = StringIO()

    def _capture_echo(msg: object, *_a: object, **_kw: object) -> None:
        buf.write(str(msg))
        buf.write("\n")

    monkeypatch.setattr(click, "echo", _capture_echo)
    # Invoke raw callback: CliRunner + pytest capture can close Click's internal buffer.
    config_commands.peer_cap_provenance.callback(str(cfg))
    data = json.loads(buf.getvalue().strip())
    assert data["optimization_profile"] == "custom"
    assert data["final"] == _EXPECTED_FILE_MPT
    assert "value_after_file" in data
    assert "value_after_profile" in data
    assert "value_after_env" in data
    assert "value_after_platform_clamp" in data
