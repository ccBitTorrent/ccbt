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


def setup_logging(config: ObservabilityConfig) -> None:
    """Set up logging configuration with Rich support."""
    # Create log directory if needed
    if config.log_file:
        log_path = Path(config.log_file)
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
                "format": "%(asctime)s %(levelname)s %(correlation_id)s %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "structured": {
                "()": StructuredFormatter,
            },
            "simple": {
                "()": FileFormatter,
                "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
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
        }

    logging_config["loggers"]["ccbt"]["handlers"].append("console")
    logging_config["root"]["handlers"].append("console")

    # Add file handler if log file is specified
    if config.log_file:
        logging_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": config.log_level.value,
            "formatter": "structured" if config.structured_logging else "simple",
            "filters": ["correlation"],
            "filename": config.log_file,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
        }
        logging_config["loggers"]["ccbt"]["handlers"].append("file")

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
    """Context manager for logging operations."""

    def __init__(self, operation: str, **kwargs):
        """Initialize operation context manager."""
        self.operation = operation
        self.kwargs = kwargs
        self.logger = get_logger(self.__class__.__module__)
        self.start_time = None

    def __enter__(self):
        """Enter the context manager."""
        self.start_time = time.time()
        set_correlation_id()
        self.logger.info("Starting %s", self.operation, extra=self.kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        duration = time.time() - self.start_time if self.start_time else 0

        if exc_type is None:
            self.logger.info(
                "Completed %s in %.3fs",
                self.operation,
                duration,
                extra=self.kwargs,
            )
        else:
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
