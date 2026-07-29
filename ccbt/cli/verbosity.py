"""Verbosity management for ccBitTorrent CLI.

Provides multi-level verbosity control with -v, -vv, -vvv flags.
"""

from __future__ import annotations

import logging
from enum import IntEnum
from typing import Any, ClassVar, Optional

from ccbt.utils.logging_config import TRACE_LOG_LEVEL, get_logger

logger = get_logger(__name__)


class VerbosityLevel(IntEnum):
    """Verbosity levels for CLI commands."""

    QUIET = 0  # Only errors
    NORMAL = 1  # Default: errors, warnings, info
    VERBOSE = 2  # -v: All above + detailed info
    DEBUG = 3  # -vv: All above + debug messages
    TRACE = 4  # -vvv: All above + trace with stack traces


class VerbosityManager:
    """Manages verbosity levels and maps them to logging levels."""

    # Map verbosity count to VerbosityLevel
    COUNT_TO_LEVEL: ClassVar[dict[int, VerbosityLevel]] = {
        0: VerbosityLevel.NORMAL,
        1: VerbosityLevel.VERBOSE,
        2: VerbosityLevel.DEBUG,
        3: VerbosityLevel.TRACE,
    }

    # Map VerbosityLevel to logging level
    LEVEL_TO_LOGGING: ClassVar[dict[VerbosityLevel, int]] = {
        VerbosityLevel.QUIET: logging.ERROR,
        VerbosityLevel.NORMAL: logging.INFO,
        VerbosityLevel.VERBOSE: logging.INFO,
        VerbosityLevel.DEBUG: logging.DEBUG,
        VerbosityLevel.TRACE: TRACE_LOG_LEVEL,  # TRACE uses dedicated TRACE level
    }

    def __init__(self, verbosity_count: int = 0):
        """Initialize verbosity manager.

        Args:
            verbosity_count: Number of -v flags (0-3)

        """
        self.verbosity_count = max(0, min(3, verbosity_count))  # Clamp to 0-3
        self.level = self.COUNT_TO_LEVEL.get(
            self.verbosity_count, VerbosityLevel.NORMAL
        )
        self.logging_level = self.LEVEL_TO_LOGGING[self.level]

    @classmethod
    def from_count(cls, count: int) -> VerbosityManager:
        """Create VerbosityManager from count.

        Args:
            count: Number of -v flags

        Returns:
            VerbosityManager instance

        """
        return cls(count)

    def should_log(self, log_level: int) -> bool:
        """Check if a log level should be displayed.

        Args:
            log_level: Logging level (logging.ERROR, logging.WARNING, etc.)

        Returns:
            True if should log, False otherwise

        """
        return log_level >= self.logging_level

    def should_show_stack_trace(self) -> bool:
        """Check if stack traces should be shown.

        Returns:
            True if TRACE level, False otherwise

        """
        return self.level == VerbosityLevel.TRACE

    def get_logging_level(self) -> int:
        """Get the logging level for this verbosity.

        Returns:
            Logging level constant

        """
        return self.logging_level_for_verbosity()

    def logging_level_for_verbosity(self) -> int:
        """Return the effective logging level for this verbosity.

        Returns:
            The logging level constant.

        """
        return self.logging_level

    def is_verbose(self) -> bool:
        """Check if verbose mode is enabled.

        Returns:
            True if VERBOSE or higher

        """
        return self.level >= VerbosityLevel.VERBOSE

    def is_debug(self) -> bool:
        """Check if debug mode is enabled.

        Returns:
            True if DEBUG or higher

        """
        return self.level >= VerbosityLevel.DEBUG

    def is_trace(self) -> bool:
        """Check if trace mode is enabled.

        Returns:
            True if TRACE level

        """
        return self.level == VerbosityLevel.TRACE


def effective_observability_log_level(base_log_level: Any, verbosity_count: int) -> Any:
    """Resolve effective log level from observability baseline and ``-v`` count.

    Matches the semantics of the root ``cli()`` Click group callback in
    ``ccbt.cli.main``.
    """
    from ccbt.models import LogLevel

    vm = VerbosityManager.from_count(verbosity_count)
    effective: Any = base_log_level
    if vm.is_trace():
        effective = vm.logging_level_for_verbosity()
    elif vm.is_debug():
        effective = LogLevel.DEBUG
    elif vm.is_verbose():
        effective = LogLevel.INFO
    return effective


def apply_cli_verbosity_to_observability(
    observability: Any,
    verbosity_count: int,
) -> None:
    """Apply verbosity to logging and persist for later :class:`ConfigManager` inits."""
    from ccbt.utils.logging_config import (
        set_cli_session_log_level_override,
        setup_logging,
    )

    eff = effective_observability_log_level(observability.log_level, verbosity_count)
    set_cli_session_log_level_override(eff)
    setup_logging(observability, effective_log_level=eff)


def get_verbosity_from_ctx(ctx: Optional[dict[str, Any]]) -> VerbosityManager:
    """Get verbosity manager from Click context.

    Args:
        ctx: Click context object

    Returns:
        VerbosityManager instance (defaults to NORMAL if not found)

    """
    if ctx is None:
        return VerbosityManager(0)

    verbosity_count = ctx.get("verbosity", 0)
    return VerbosityManager.from_count(verbosity_count)


def log_with_verbosity(
    logger_instance: logging.Logger,
    verbosity: VerbosityManager,
    level: int,
    message: str,
    *args: Any,
    exc_info: Optional[bool] = None,
    **kwargs: Any,
) -> None:
    """Log a message respecting verbosity level.

    Args:
        logger_instance: Logger to use
        verbosity: VerbosityManager instance
        level: Logging level (logging.ERROR, etc.)
        message: Message to log
        *args: Format arguments
        exc_info: Whether to include exception info
        **kwargs: Additional logging kwargs

    """
    if not verbosity.should_log(level):
        return

    # For TRACE level, always include stack traces
    if verbosity.should_show_stack_trace() and exc_info is None:
        exc_info = level >= logging.WARNING

    logger_instance.log(level, message, *args, exc_info=exc_info, **kwargs)
