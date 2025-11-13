"""Rich logging integration for ccBitTorrent.

Provides Rich-based logging handlers and formatters with i18n support.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console

try:
    from rich.console import Console as RichConsole
    from rich.logging import RichHandler as _RichHandler
    from rich.text import Text

    _RICH_AVAILABLE = True
    RichHandler = _RichHandler  # type: ignore[assignment]
except ImportError:
    _RICH_AVAILABLE = False

    # Fallback classes
    class RichHandler(logging.Handler):  # type: ignore[misc]
        """Fallback RichHandler when rich is not available."""

    RichConsole = None  # type: ignore[assignment,misc]


class CorrelationRichHandler(RichHandler):  # type: ignore[misc]
    """RichHandler with correlation ID support."""

    def __init__(
        self,
        *args: Any,
        console: Console | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize RichHandler with correlation ID filter.

        Args:
            *args: Positional arguments for RichHandler
            console: Optional Rich Console instance
            **kwargs: Keyword arguments for RichHandler

        """
        if not _RICH_AVAILABLE:
            # Fallback to StreamHandler if Rich not available
            super().__init__(*args, **kwargs)
            return

        # Set default console if not provided
        if console is None:
            console = RichConsole()

        super().__init__(*args, console=console, **kwargs)  # type: ignore[misc]

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record with correlation ID."""
        try:
            # Add correlation ID to record (lazy import to avoid circular dependency)
            if not hasattr(record, "correlation_id"):
                try:
                    from ccbt.utils.logging_config import correlation_id

                    record.correlation_id = correlation_id.get() or "no-correlation-id"
                except ImportError:
                    record.correlation_id = "no-correlation-id"

            # Call parent emit
            super().emit(record)
        except Exception:
            # CRITICAL FIX: Prevent circular logging errors
            # If logging fails, don't try to log the error (which could fail again)
            # Instead, silently ignore or use sys.stderr as last resort
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        """Handle errors during logging to prevent circular errors."""
        # Use sys.stderr directly to avoid any logging framework
        import sys

        try:
            sys.stderr.write(
                f"Logging error (suppressed to prevent circular errors): "
                f"{record.levelname} {record.name}: {record.getMessage()}\n"
            )
            sys.stderr.flush()
        except Exception:
            # Last resort: completely silent failure
            pass


class RichFormatter(logging.Formatter):
    """Formatter that preserves Rich markup in log messages."""

    def __init__(
        self,
        *args: Any,
        preserve_rich_markup: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize Rich formatter.

        Args:
            *args: Positional arguments for Formatter
            preserve_rich_markup: Whether to preserve Rich markup in messages
            **kwargs: Keyword arguments for Formatter

        """
        super().__init__(*args, **kwargs)
        self.preserve_rich_markup = preserve_rich_markup

    def format(self, record: logging.LogRecord) -> str:
        """Format log record, preserving Rich markup if enabled."""
        # Get the formatted message
        message = super().format(record)

        # If preserving Rich markup, ensure it's not stripped
        if self.preserve_rich_markup and _RICH_AVAILABLE:
            # Rich markup is already in the message, just return it
            return message

        return message


def strip_rich_markup(text: str) -> str:
    """Strip Rich markup from text for file logging.

    Args:
        text: Text with Rich markup

    Returns:
        Text without Rich markup

    """
    if not _RICH_AVAILABLE:
        return text

    import re

    # Remove Rich markup tags like [red], [bold], etc.
    # Pattern matches [tag], [tag=value], [/tag]
    pattern = r"\[/?[^\]]+\]"
    return re.sub(pattern, "", text)


class FileFormatter(logging.Formatter):
    """Formatter for file output that strips Rich markup."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record, stripping Rich markup for file output."""
        # First format normally
        formatted = super().format(record)

        # Strip Rich markup for file output
        return strip_rich_markup(formatted)


def create_rich_handler(
    console: Console | None = None,
    level: int = logging.INFO,
    show_path: bool = False,
    rich_tracebacks: bool = True,
) -> logging.Handler:
    """Create a RichHandler with correlation ID support.

    Args:
        console: Optional Rich Console instance
        level: Log level
        show_path: Whether to show file paths in log output
        rich_tracebacks: Whether to use rich tracebacks

    Returns:
        Configured RichHandler instance

    """
    if not _RICH_AVAILABLE:
        # Fallback to StreamHandler
        import sys

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        return handler

    if console is None:
        console = RichConsole()

    handler = CorrelationRichHandler(
        console=console,
        level=level,
        show_path=show_path,
        rich_tracebacks=rich_tracebacks,
    )

    return handler


# i18n logging helpers
def log_info_translated(
    logger: logging.Logger,
    message: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Log an info message with i18n translation and Rich markup support.

    Args:
        logger: Logger instance
        message: Message to translate and log (supports Rich markup)
        *args: Format arguments
        **kwargs: Additional logging arguments

    """
    try:
        from ccbt.i18n import _

        translated = _(message)
        logger.info(translated, *args, **kwargs)
    except Exception:
        # Fallback if i18n not available
        logger.info(message, *args, **kwargs)


def log_error_translated(
    logger: logging.Logger,
    message: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Log an error message with i18n translation and Rich markup support.

    Args:
        logger: Logger instance
        message: Message to translate and log (supports Rich markup)
        *args: Format arguments
        **kwargs: Additional logging arguments

    """
    try:
        from ccbt.i18n import _

        translated = _(message)
        logger.error(translated, *args, **kwargs)
    except Exception:
        # Fallback if i18n not available
        logger.error(message, *args, **kwargs)


def log_warning_translated(
    logger: logging.Logger,
    message: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Log a warning message with i18n translation and Rich markup support.

    Args:
        logger: Logger instance
        message: Message to translate and log (supports Rich markup)
        *args: Format arguments
        **kwargs: Additional logging arguments

    """
    try:
        from ccbt.i18n import _

        translated = _(message)
        logger.warning(translated, *args, **kwargs)
    except Exception:
        # Fallback if i18n not available
        logger.warning(message, *args, **kwargs)


def log_debug_translated(
    logger: logging.Logger,
    message: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Log a debug message with i18n translation and Rich markup support.

    Args:
        logger: Logger instance
        message: Message to translate and log (supports Rich markup)
        *args: Format arguments
        **kwargs: Additional logging arguments

    """
    try:
        from ccbt.i18n import _

        translated = _(message)
        logger.debug(translated, *args, **kwargs)
    except Exception:
        # Fallback if i18n not available
        logger.debug(message, *args, **kwargs)
