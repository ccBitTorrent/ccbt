"""Structured logging configuration for ccBitTorrent.

from __future__ import annotations

Provides comprehensive logging setup with correlation IDs, structured output,
and configurable log levels.
"""

from __future__ import annotations

import json
import logging
import logging.config
import sys
import time
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

from ccbt.utils.exceptions import CCBTError
from ccbt.utils.rich_logging import (
    FileFormatter,
    create_rich_handler,
)

if TYPE_CHECKING:  # pragma: no cover
    # Type-only import for static type checking, not executed at runtime
    from ccbt.cli.verbosity import VerbosityManager
    from ccbt.models import ObservabilityConfig

# Context variable for correlation ID
# Help type checker understand the ContextVar generic with a None default
correlation_id: ContextVar[str | None] = cast(
    "ContextVar[str | None]",
    ContextVar("correlation_id", default=None),
)


class CorrelationFilter(logging.Filter):
    """Filter to add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to log record."""
        record.correlation_id = correlation_id.get() or "no-correlation-id"
        return True


class StructuredFormatter(logging.Formatter):
    """Structured JSON formatter for logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        try:
            log_entry = {
                "timestamp": time.time(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            # Add correlation ID if available
            if hasattr(record, "correlation_id"):
                log_entry["correlation_id"] = record.correlation_id

            # Add exception info if present
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)

            # Add extra fields
            excluded_keys = {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "correlation_id",
            }
            log_entry.update(
                {
                    key: value
                    for key, value in record.__dict__.items()
                    if key not in excluded_keys
                }
            )

            return json.dumps(log_entry, default=str)
        except Exception:
            # CRITICAL FIX: Fallback to simple format if JSON serialization fails
            # This prevents "Logging error" messages from circular failures
            try:
                return f"{record.levelname} {record.name}: {record.getMessage()}"
            except Exception:
                return f"Logging error: {record.levelname} {record.name}"


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output (legacy, uses Rich now).

    Deprecated: Use RichHandler instead. Kept for backward compatibility.
    """

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET: ClassVar[str] = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with color coding."""
        try:
            # Add color to level name
            if record.levelname in self.COLORS:
                record.levelname = (
                    f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
                )

            # Add correlation ID if available
            if hasattr(record, "correlation_id"):
                record.correlation_id = f"[{record.correlation_id}]"
            else:
                record.correlation_id = ""

            return super().format(record)
        except Exception:
            # CRITICAL FIX: Fallback to simple format if formatting fails
            try:
                return f"{record.levelname} {record.name}: {record.getMessage()}"
            except Exception:
                return f"Logging error: {record.levelname} {record.name}"


def _generate_timestamped_log_filename(base_path: str | None) -> str:
    """Generate a unique timestamped log file name.
    
    Args:
        base_path: Base log file path (directory or file path)
        
    Returns:
        Timestamped log file path
        
    Format: ccbt-YYYYMMDD-HHMMSS-<random>.log
    """
    from datetime import datetime
    import random
    import string
    
    if base_path is None:
        # Default to .ccbt/logs directory
        log_dir = Path.home() / ".ccbt" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        base_dir = log_dir
    else:
        base_path_obj = Path(base_path)
        if base_path_obj.is_dir():
            base_dir = base_path_obj
        else:
            # It's a file path, use its directory
            base_dir = base_path_obj.parent
            base_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp: YYYYMMDD-HHMMSS
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Generate random suffix (4 characters) to ensure uniqueness
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    
    # Create filename: ccbt-YYYYMMDD-HHMMSS-<random>.log
    log_filename = f"ccbt-{timestamp}-{random_suffix}.log"
    
    return str(base_dir / log_filename)


def setup_logging(config: ObservabilityConfig) -> None:
    """Set up logging configuration with Rich support.
    
    Log files are automatically timestamped with format: ccbt-YYYYMMDD-HHMMSS-<random>.log
    """
    # Generate timestamped log file name if log_file is specified
    actual_log_file = config.log_file
    if config.log_file:
        actual_log_file = _generate_timestamped_log_filename(config.log_file)
        log_path = Path(actual_log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Try to use RichHandler for console output
    try:
        rich_handler = create_rich_handler(level=config.log_level.value)
        use_rich = True
    except Exception:
        # Fallback to standard handler if Rich not available
        use_rich = False
        rich_handler = None

    # Configure logging
    logging_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "colored": {
                "()": ColoredFormatter,
                "format": "%(asctime)s %(levelname)s %(correlation_id)s %(name)s.%(funcName)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "structured": {
                "()": StructuredFormatter,
            },
            "simple": {
                "()": FileFormatter,
                "format": "%(asctime)s %(levelname)s %(name)s.%(funcName)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "filters": {
            "correlation": {
                "()": CorrelationFilter,
            },
        },
        "handlers": {},
        "loggers": {
            "ccbt": {
                "level": config.log_level.value,
                "handlers": [],
                "propagate": False,
            },
        },
        "root": {
            "level": config.log_level.value,
            "handlers": [],
        },
    }

    # Add console handler
    if use_rich and rich_handler:
        # Use RichHandler for console - we'll add it directly after dictConfig
        logging_config["handlers"]["console"] = {
            "class": "logging.StreamHandler",
            "level": config.log_level.value,
            "formatter": "colored",
            "filters": ["correlation"],
            "stream": sys.stdout,
        }
    else:
        # Fallback to standard StreamHandler
        logging_config["handlers"]["console"] = {
            "class": "logging.StreamHandler",
            "level": config.log_level.value,
            "formatter": "colored" if not config.structured_logging else "structured",
            "filters": ["correlation"],
            "stream": sys.stdout,
            # CRITICAL FIX: Disable buffering for real-time log output
            # This ensures logs appear immediately instead of only on interrupt
        }

    logging_config["loggers"]["ccbt"]["handlers"].append("console")
    logging_config["root"]["handlers"].append("console")

    # Add file handler if log file is specified
    # Use timestamped filename for unique log files per session
    if config.log_file:
        logging_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": config.log_level.value,
            "formatter": "structured" if config.structured_logging else "simple",
            "filters": ["correlation"],
            "filename": actual_log_file,  # Use timestamped filename
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
        }
        logging_config["loggers"]["ccbt"]["handlers"].append("file")

    import os
    if 'PYTHONUNBUFFERED' not in os.environ:
        os.environ['PYTHONUNBUFFERED'] = '1'
    
    # Reconfigure stdout to use line buffering (flush after each line)
    try:
        # Python 3.7+ supports reconfigure
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(line_buffering=True)
        # Fallback: wrap stdout in a line-buffered TextIOWrapper
        elif hasattr(sys.stdout, 'buffer'):
            import io
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding=sys.stdout.encoding,
                errors=sys.stdout.errors,
                newline=sys.stdout.newlines,
                line_buffering=True,  # CRITICAL: Flush after each line
            )
    except Exception:
        # If reconfiguration fails, continue with default (better than crashing)
        pass

    # Apply configuration
    logging.config.dictConfig(logging_config)

    # Replace console handler with RichHandler if available
    if use_rich and rich_handler:
        root_logger = logging.getLogger()
        ccbt_logger = logging.getLogger("ccbt")

        # Remove existing console handlers
        for handler in list(root_logger.handlers):
            if (
                isinstance(handler, logging.StreamHandler)
                and handler.stream == sys.stdout
            ):
                root_logger.removeHandler(handler)
        for handler in list(ccbt_logger.handlers):
            if (
                isinstance(handler, logging.StreamHandler)
                and handler.stream == sys.stdout
            ):
                ccbt_logger.removeHandler(handler)

        # Add RichHandler
        root_logger.addHandler(rich_handler)
        ccbt_logger.addHandler(rich_handler)
        
        # Wrap emit to force flush after each log message
        if hasattr(rich_handler, 'console'):
            # Rich Console - ensure it flushes
            original_emit = rich_handler.emit
            def make_emit_with_flush(original: Any, console: Any) -> Any:
                """Create an emit function that flushes Rich Console after each log."""
                def emit_with_flush(record: logging.LogRecord) -> None:
                    original(record)
                    try:
                        # Force Rich Console to flush
                        if hasattr(console, '_file') and hasattr(console._file, 'flush'):
                            console._file.flush()
                        elif hasattr(console, 'file') and hasattr(console.file, 'flush'):
                            console.file.flush()
                    except Exception:
                        pass  # Ignore flush errors
                return emit_with_flush
            rich_handler.emit = make_emit_with_flush(original_emit, rich_handler.console)  # type: ignore[method-assign,attr-defined]
        elif hasattr(rich_handler, 'stream') and hasattr(rich_handler.stream, 'flush'):
            # Standard StreamHandler - ensure it flushes
            original_emit = rich_handler.emit
            def make_emit_with_flush(original: Any, stream: Any) -> Any:
                """Create an emit function that flushes stream after each log."""
                def emit_with_flush(record: logging.LogRecord) -> None:
                    original(record)
                    try:
                        stream.flush()
                    except Exception:
                        pass  # Ignore flush errors
                return emit_with_flush
            rich_handler.emit = make_emit_with_flush(original_emit, rich_handler.stream)  # type: ignore[method-assign]
    
    # this is for standard StreamHandlers
    for logger_name in [None, "ccbt"]:  # root logger and ccbt logger
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            # Skip RichHandler (already handled above) and handlers without stdout stream
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                # Check if this is a RichHandler (has console attribute) - skip if already handled
                if hasattr(handler, 'console'):
                    continue  # RichHandler already handled above
                
                # Create a wrapper that flushes after each emit
                original_emit = handler.emit
                def make_emit_with_flush(original: Any, stream: Any) -> Any:
                    """Create an emit function that flushes after each log."""
                    def emit_with_flush(record: logging.LogRecord) -> None:
                        original(record)
                        try:
                            stream.flush()
                        except Exception:
                            pass  # Ignore flush errors
                    return emit_with_flush
                handler.emit = make_emit_with_flush(original_emit, handler.stream)  # type: ignore[method-assign]

    # Set up correlation ID for main thread
    if config.log_correlation_id:
        correlation_id.set(str(uuid.uuid4()))


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(f"ccbt.{name}")


def set_correlation_id(corr_id: str | None = None) -> str:
    """Set correlation ID for the current context."""
    if corr_id is None:
        corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    return corr_id


def get_correlation_id() -> str | None:
    """Get the current correlation ID."""
    return correlation_id.get()


class LoggingContext:
    """Context manager for logging operations with verbosity support."""

    def __init__(
        self,
        operation: str,
        log_level: int | None = None,
        slow_threshold: float = 1.0,
        verbosity_manager: Any | None = None,
        **kwargs,
    ):
        """Initialize operation context manager.
        
        Args:
            operation: Name of the operation
            log_level: Logging level (default: DEBUG for most operations, INFO for slow ones)
            slow_threshold: Duration in seconds above which to log at INFO level (default: 1.0s)
            verbosity_manager: Optional VerbosityManager instance for verbosity-aware logging
            **kwargs: Additional context to include in logs
        """
        self.operation = operation
        self.kwargs = kwargs
        self.logger = get_logger(self.__class__.__module__)
        self.start_time = None
        self.log_level = log_level
        self.slow_threshold = slow_threshold
        self.verbosity_manager = verbosity_manager
        # Operations that should always log at INFO level (even at NORMAL verbosity)
        self.info_operations = {
            "torrent_add", "torrent_remove", "torrent_complete", 
            "session_start", "session_stop", "daemon_start", "daemon_stop"
        }
        # Operations that should only log at VERBOSE or higher
        self.verbose_operations = {
            "config_load", "config_save", "peer_connect", "peer_disconnect",
            "piece_request", "piece_received", "tracker_announce", "dht_query",
        }

    def _should_log(self, level: int) -> bool:
        """Check if should log at this level based on verbosity.
        
        Args:
            level: Logging level
            
        Returns:
            True if should log
        """
        if self.verbosity_manager is None:
            return True  # No verbosity manager, log everything
        return self.verbosity_manager.should_log(level)

    def __enter__(self):
        """Enter the context manager."""
        self.start_time = time.time()
        set_correlation_id()
        
        # Determine log level
        level = self.log_level
        if level is None:
            if self.operation in self.info_operations:
                level = logging.INFO
            elif self.operation in self.verbose_operations:
                # Verbose operations need -v flag
                level = logging.INFO  # But will be filtered by verbosity
            else:
                level = logging.DEBUG
        
        # Check if should log based on verbosity
        if self._should_log(level):
            self.logger.log(level, "Starting %s", self.operation, extra=self.kwargs)
        
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        duration = time.time() - self.start_time if self.start_time else 0

        if exc_type is None:
            # Log at INFO if operation was slow or is important, otherwise DEBUG
            level = self.log_level
            if level is None:
                if self.operation in self.info_operations or duration >= self.slow_threshold:
                    level = logging.INFO
                elif self.operation in self.verbose_operations:
                    level = logging.INFO  # Verbose operations
                else:
                    level = logging.DEBUG
            
            # Check if should log based on verbosity
            if self._should_log(level):
                self.logger.log(
                    level,
                    "Completed %s in %.3fs",
                    self.operation,
                    duration,
                    extra=self.kwargs,
                )
        else:
            # Always log errors
            self.logger.error(
                "Failed %s in %.3fs: %s",
                self.operation,
                duration,
                exc_val,
                extra=self.kwargs,
                exc_info=exc_val is not None,
            )

        return False  # Don't suppress exceptions


def log_exception(logger: logging.Logger, exc: Exception, context: str = "") -> None:
    """Log an exception with context."""
    if isinstance(exc, CCBTError):
        logger.error(
            "%s: %s",
            context,
            exc.message,
            extra={"details": exc.details},
            exc_info=True,
        )
    else:
        logger.exception("%s: %s", context, exc)


def log_with_verbosity(
    logger: logging.Logger,
    verbosity_manager: Any | None,
    level: int,
    message: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Log a message respecting verbosity level.
    
    Args:
        logger: Logger instance
        verbosity_manager: VerbosityManager instance (None = always log)
        level: Logging level (logging.INFO, logging.DEBUG, etc.)
        message: Message to log
        *args: Format arguments
        **kwargs: Additional logging kwargs
    """
    if verbosity_manager is None:
        # No verbosity manager, log everything
        logger.log(level, message, *args, **kwargs)
        return
    
    # Check if should log based on verbosity
    if verbosity_manager.should_log(level):
        logger.log(level, message, *args, **kwargs)


def log_info_verbose(
    logger: logging.Logger,
    verbosity_manager: Any | None,
    message: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Log at INFO level, but only if verbosity is VERBOSE or higher.
    
    Use this for detailed INFO messages that should not appear at NORMAL verbosity.
    
    Args:
        logger: Logger instance
        verbosity_manager: VerbosityManager instance
        message: Message to log
        *args: Format arguments
        **kwargs: Additional logging kwargs
    """
    if verbosity_manager is None:
        # No verbosity manager, log everything
        logger.info(message, *args, **kwargs)
        return
    
    # Only log if verbosity is VERBOSE or higher
    if verbosity_manager.is_verbose() or verbosity_manager.is_debug():
        logger.info(message, *args, **kwargs)


def log_info_normal(
    logger: logging.Logger,
    verbosity_manager: Any | None,
    message: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Log at INFO level, but only if verbosity is NORMAL or higher.
    
    Use this for important INFO messages that should appear at NORMAL verbosity.
    
    Args:
        logger: Logger instance
        verbosity_manager: VerbosityManager instance (None = always log)
        message: Message to log
        *args: Format arguments
        **kwargs: Additional logging kwargs
    """
    if verbosity_manager is None:
        # No verbosity manager, log everything
        logger.info(message, *args, **kwargs)
        return
    
    # Log if verbosity is NORMAL or higher (always log at NORMAL)
    if verbosity_manager.verbosity_count >= 0:  # NORMAL or higher
        logger.info(message, *args, **kwargs)