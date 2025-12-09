"""Rich logging integration for ccBitTorrent.

Provides Rich-based logging handlers and formatters with i18n support.
"""

from __future__ import annotations

import logging
import re
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
    Text = None  # type: ignore[assignment,misc]


class CorrelationRichHandler(RichHandler):  # type: ignore[misc]
    """RichHandler with correlation ID support and enhanced formatting.

    Note: Icons/emojis have been removed per user preference.
    Method names are colored pink (#ff69b4), action text is colored bright cyan,
    and ALL_CAPS words (like HANDSHAKE_COMPLETE, MESSAGE) are colored orange.
    """

    # Icons removed - no longer using emojis in log messages
    LEVEL_ICONS: dict[str, str] = {}

    # Colors for log levels
    LEVEL_COLORS: dict[str, str] = {
        "DEBUG": "dim",
        "INFO": "cyan",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold red",
    }

    # Patterns for action text that should be colored bright cyan
    ACTION_PATTERNS = [
        r"PIECE_MANAGER:",
        r"PIECE_MESSAGE:",
        r"Sent \d+ REQUEST message\(s\)",
        r"Received piece",
        r"state transition:",
        r"No available peers",
        r"Checking \d+ active peers",
    ]

    def __init__(
        self,
        *args: Any,
        console: Console | None = None,
        show_icons: bool = False,  # Always False - icons removed
        show_colors: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize RichHandler with correlation ID filter.

        Args:
            *args: Positional arguments for RichHandler
            console: Optional Rich Console instance
            show_icons: Whether to show icons for log levels (deprecated, always False)
            show_colors: Whether to use colors for log levels
            **kwargs: Keyword arguments for RichHandler

        """
        if not _RICH_AVAILABLE:
            # Fallback to StreamHandler if Rich not available
            super().__init__(*args, **kwargs)
            return

        # Set default console if not provided
        if console is None:
            # CRITICAL: Explicitly enable markup processing and color system in Rich Console
            import sys
            console = RichConsole(
                file=sys.stdout,
                markup=True,
                force_terminal=True,
                color_system="auto",  # Auto-detect color system (256 colors, truecolor, etc.)
            )

        self.show_icons = False  # Always False
        self.show_colors = show_colors

        # CRITICAL: RichHandler does NOT process markup by default
        # We must pass markup=True to RichHandler constructor to enable markup processing
        # This allows Rich markup like [#ff69b4]text[/#ff69b4] to be rendered
        # Only set if not already in kwargs to avoid duplicate argument error
        if 'markup' not in kwargs:
            kwargs['markup'] = True  # Enable Rich markup processing in RichHandler
        
        super().__init__(*args, console=console, **kwargs)  # type: ignore[misc]

    def _colorize_action_text(self, message: str) -> str:
        """Colorize action/operation text in the message with bright cyan.
        Also colorizes ALL_CAPS words (like HANDSHAKE_COMPLETE, MESSAGE) in orange.
        
        Args:
            message: Original log message
            
        Returns:
            Message with action text and ALL_CAPS words colorized
        """
        if not _RICH_AVAILABLE:
            return message
        
        # Colorize action patterns with bright cyan
        for pattern in self.ACTION_PATTERNS:
            # Find all matches and wrap them in bright cyan color
            matches = list(re.finditer(pattern, message))
            # Process from end to start to preserve indices
            for match in reversed(matches):
                start, end = match.span()
                matched_text = message[start:end]
                # Only colorize if not already colorized
                if "[bright_cyan]" not in message[max(0, start-20):start]:
                    message = (
                        message[:start]
                        + f"[bright_cyan]{matched_text}[/bright_cyan]"
                        + message[end:]
                    )
        
        # Colorize ALL_CAPS words (like HANDSHAKE_COMPLETE, MESSAGE, MESSAGE_LOOP) in orange
        # Pattern matches words that are all uppercase letters, possibly with underscores
        # Must be at least 2 characters and contain at least one letter (not just underscores)
        all_caps_pattern = r'\b[A-Z][A-Z_]*[A-Z]\b|\b[A-Z]{2,}\b'
        matches = list(re.finditer(all_caps_pattern, message))
        # Process from end to start to preserve indices
        for match in reversed(matches):
            start, end = match.span()
            matched_text = message[start:end]
            # Verify it's actually all caps (not mixed case)
            # Must be all uppercase letters, possibly with underscores
            if not (matched_text.isupper() or (matched_text.replace('_', '').isupper() and '_' in matched_text)):
                continue
            
            # Check if this text is already inside Rich markup tags
            # Simple heuristic: if there's a '[' nearby before and ']' nearby after, skip
            # to avoid double-wrapping
            before_context = message[max(0, start-30):start]
            after_context = message[end:min(len(message), end+30)]
            
            # Skip if already inside markup (has opening bracket before and closing after)
            if '[' in before_context and ']' in after_context:
                # Check if there's a closing tag marker [/ which would indicate we're inside markup
                if '[/' in after_context:
                    continue
                # Also check if we're right after an opening tag (like [orange1]WORD)
                if before_context.rstrip().endswith(']'):
                    continue
            
            # Only colorize if not already colorized (check for common color tags)
            if "[orange1]" not in before_context and "[orange3]" not in before_context and "[#ff8c00]" not in before_context:
                message = (
                    message[:start]
                    + f"[orange1]{matched_text}[/orange1]"
                    + message[end:]
                )
        
        return message

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record with correlation ID, method name coloring, and action text coloring."""
        try:
            # Add correlation ID to record (lazy import to avoid circular dependency)
            if not hasattr(record, "correlation_id"):
                try:
                    from ccbt.utils.logging_config import correlation_id

                    record.correlation_id = correlation_id.get() or "no-correlation-id"
                except ImportError:
                    record.correlation_id = "no-correlation-id"

            # Process message with colorization if Rich is available
            if _RICH_AVAILABLE:
                # Format message with Rich markup
                # RichHandler should process this if markup=True is set on both console and handler
                original_msg = record.getMessage()
                func_name = getattr(record, "funcName", "unknown")
                
                # Step 1: Colorize action text in the message (bright cyan)
                colored_msg = self._colorize_action_text(original_msg)
                
                # Step 2: Add pink-colored method name at the beginning
                # Format: [#ff69b4]method_name[/#ff69b4] message
                # Using hex color #ff69b4 (hot pink) as Rich doesn't have "pink" as a named color
                if func_name and func_name != "unknown":
                    pink_markup = f"[#ff69b4]{func_name}[/#ff69b4]"
                    if pink_markup not in colored_msg:
                        formatted_msg = f"{pink_markup} {colored_msg}"
                    else:
                        formatted_msg = colored_msg
                else:
                    formatted_msg = colored_msg
                
                # Set the formatted message with markup
                # RichHandler will process this through its LogRender if markup is enabled
                record.msg = formatted_msg
                record.args = ()  # Clear args since we've formatted the message

            # Call parent emit - RichHandler will format and render
            # Both console.markup=True and handler.markup=True are set in __init__
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
    show_icons: bool = False,  # Default to False - icons removed
    show_colors: bool = True,
) -> logging.Handler:
    """Create a RichHandler with correlation ID support and method name coloring.

    Args:
        console: Optional Rich Console instance
        level: Log level
        show_path: Whether to show file paths in log output
        rich_tracebacks: Whether to use rich tracebacks
        show_icons: Whether to show icons for log levels (deprecated, always False)
        show_colors: Whether to use colors for log levels

    Returns:
        Configured RichHandler instance

    Note:
        Icons/emojis have been removed. Method names are colored pink.
        Action text (like "PIECE_MANAGER:", "Sent 1 REQUEST") is colored bright cyan.
        ALL_CAPS words (like HANDSHAKE_COMPLETE, MESSAGE) are colored orange.

    """
    if not _RICH_AVAILABLE:
        # Fallback to StreamHandler
        import sys

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        return handler

    if console is None:
        # CRITICAL FIX: Create Rich Console with file=sys.stdout and explicit markup=True
        # This ensures immediate output without buffering and proper markup processing
        import sys
        console = RichConsole(
            file=sys.stdout,
            force_terminal=True,  # Force terminal output even if redirected
            force_interactive=False,  # Don't force interactive mode (avoids prompts)
            width=None,  # Auto-detect width
            legacy_windows=False,  # Use modern Windows terminal handling
            markup=True,  # CRITICAL: Explicitly enable markup processing
        )

    handler = CorrelationRichHandler(
        console=console,
        level=level,
        show_path=show_path,
        rich_tracebacks=rich_tracebacks,
        show_icons=False,  # Always False - icons removed
        show_colors=show_colors,
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
