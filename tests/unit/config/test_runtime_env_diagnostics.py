from __future__ import annotations

import pytest

from ccbt.config.config import ConfigManager


@pytest.mark.unit
def test_runtime_env_diagnostics_exposes_dotenv_provenance(monkeypatch) -> None:
    """Runtime diagnostics should include dotenv provenance keys."""
    monkeypatch.setenv("CCBT_DOTENV_LOADED", "1")
    monkeypatch.setenv("CCBT_DOTENV_PATH_EFFECTIVE", "C:/tmp/.env")
    monkeypatch.setenv("CCBT_DOTENV_KEYS_LOADED", "3")
    manager = ConfigManager()
    diag = manager.get_runtime_env_diagnostics()
    assert diag["dotenv_loaded"] == "1"
    assert diag["dotenv_path_effective"] == "C:/tmp/.env"
    assert diag["dotenv_keys_loaded"] == "3"
    assert "tracker_immediate_per_tracker_cooldown_enabled" in diag
