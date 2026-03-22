"""CLI verbosity persists across ConfigManager() when session override is set."""

from __future__ import annotations

import logging

import pytest

from ccbt.cli.verbosity import (
    apply_cli_verbosity_to_observability,
    effective_observability_log_level,
)
from ccbt.config.config import ConfigManager, reset_config
from ccbt.models import LogLevel
from ccbt.utils.logging_config import (
    TRACE_LOG_LEVEL,
    get_cli_session_log_level_override,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_session() -> None:
    reset_config()
    yield
    reset_config()


def test_effective_observability_log_level_mapping() -> None:
    """Maps -v / -vv / -vvv to INFO / DEBUG / TRACE for a given config baseline."""
    base = LogLevel.WARNING
    assert effective_observability_log_level(base, 0) == base
    assert effective_observability_log_level(base, 1) == LogLevel.INFO
    assert effective_observability_log_level(base, 2) == LogLevel.DEBUG
    assert effective_observability_log_level(base, 3) == TRACE_LOG_LEVEL


def test_second_config_manager_respects_session_verbosity_override(
    tmp_path,
) -> None:
    """Re-loading config must not drop a prior CLI ``-vv`` effective level."""
    config_file = tmp_path / "ccbt.toml"
    config_file.write_text(
        """
[observability]
log_level = "INFO"
log_correlation_id = false
structured_logging = false
log_format = "%(message)s"
metrics_interval = 15.0
""",
        encoding="utf-8",
    )

    cm0 = ConfigManager(config_file=config_file)
    apply_cli_verbosity_to_observability(cm0.config.observability, 2)
    assert get_cli_session_log_level_override() == LogLevel.DEBUG

    ConfigManager(config_file=config_file)
    ccbt_logger = logging.getLogger("ccbt")
    assert ccbt_logger.getEffectiveLevel() == logging.DEBUG
