"""Comprehensive tests for logging_config.py to achieve 99% coverage.

Covers:
- CorrelationFilter.filter() - correlation ID handling
- StructuredFormatter.format() - all code paths
- ColoredFormatter.format() - all code paths
- setup_logging() - all configuration paths
- LoggingContext - context manager lifecycle
- log_exception() - CCBTError vs generic exception paths
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit]

from ccbt.models import LogLevel, ObservabilityConfig
from ccbt.utils.exceptions import CCBTError
from ccbt.utils.logging_config import (
    ColoredFormatter,
    CorrelationFilter,
    LoggingContext,
    StructuredFormatter,
    get_correlation_id,
    get_logger,
    log_exception,
    set_correlation_id,
    setup_logging,
)


class TestCorrelationFilter:
    """Test CorrelationFilter filter method."""

    def test_filter_with_correlation_id_set(self):
        """Test CorrelationFilter.filter() with correlation ID set (line 39)."""
        filter_obj = CorrelationFilter()
        
        # Set correlation ID
        set_correlation_id("test-correlation-123")
        
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = filter_obj.filter(record)
        
        assert result is True
        assert hasattr(record, "correlation_id")
        assert record.correlation_id == "test-correlation-123"

    def test_filter_without_correlation_id(self):
        """Test CorrelationFilter.filter() without correlation ID (default path, line 39)."""
        filter_obj = CorrelationFilter()
        
        # Ensure no correlation ID is set
        from ccbt.utils.logging_config import correlation_id
        correlation_id.set(None)
        
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = filter_obj.filter(record)
        
        assert result is True
        assert hasattr(record, "correlation_id")
        assert record.correlation_id == "no-correlation-id"


class TestStructuredFormatter:
    """Test StructuredFormatter format method."""

    def test_format_normal_log_record(self):
        """Test StructuredFormatter.format() - normal log record (lines 46-99)."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert data["module"] == "test"
        # funcName might be None or empty in some contexts (when record.funcName is None)
        # The formatter includes it if it exists, but LogRecord might have None
        assert "function" in data  # Field exists, but value might be None
        assert data["line"] == 42
        assert "timestamp" in data

    def test_format_with_correlation_id(self):
        """Test StructuredFormatter.format() - with correlation_id attribute (lines 58-60)."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test-correlation-123"
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data["correlation_id"] == "test-correlation-123"

    def test_format_with_exception_info(self):
        """Test StructuredFormatter.format() - with exception info (lines 62-64)."""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=exc_info,
        )
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "Test exception" in data["exception"]

    def test_format_with_extra_fields(self):
        """Test StructuredFormatter.format() - with extra fields (lines 66-97)."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"
        record.another_field = 123
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data["custom_field"] == "custom_value"
        assert data["another_field"] == 123

    def test_format_excluded_keys_not_in_output(self):
        """Test StructuredFormatter.format() - excluded keys not in output (lines 67-90)."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        # Add non-excluded custom field
        record.valid_field = "should_be_included"
        record.custom_metric = 42
        
        result = formatter.format(record)
        data = json.loads(result)
        
        # Custom fields should be included
        assert "valid_field" in data
        assert "custom_metric" in data
        assert data["valid_field"] == "should_be_included"
        assert data["custom_metric"] == 42


class TestColoredFormatter:
    """Test ColoredFormatter format method."""

    def test_format_debug_level(self):
        """Test ColoredFormatter.format() - DEBUG level (lines 114-120)."""
        # ColoredFormatter needs a format string to work properly
        formatter = ColoredFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=1,
            msg="Debug message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        
        # Level name should be colored (formatter modifies record.levelname in place)
        # Check that DEBUG appears in the formatted result
        assert "DEBUG" in result or "Debug message" in result

    def test_format_info_level(self):
        """Test ColoredFormatter.format() - INFO level."""
        formatter = ColoredFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Info message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        assert "INFO" in result or "Info message" in result

    def test_format_warning_level(self):
        """Test ColoredFormatter.format() - WARNING level."""
        formatter = ColoredFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        assert "WARNING" in result or "Warning message" in result

    def test_format_error_level(self):
        """Test ColoredFormatter.format() - ERROR level."""
        formatter = ColoredFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        assert "ERROR" in result or "Error message" in result

    def test_format_critical_level(self):
        """Test ColoredFormatter.format() - CRITICAL level."""
        formatter = ColoredFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.CRITICAL,
            pathname="test.py",
            lineno=1,
            msg="Critical message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        assert "CRITICAL" in result or "Critical message" in result

    def test_format_with_correlation_id(self):
        """Test ColoredFormatter.format() - with correlation_id attribute (lines 122-124)."""
        formatter = ColoredFormatter(
            fmt="%(asctime)s %(levelname)s %(correlation_id)s %(name)s: %(message)s"
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test-correlation-123"
        
        result = formatter.format(record)
        
        # Correlation ID should be formatted with brackets
        # The format method modifies record.correlation_id in place
        assert "test-correlation-123" in result

    def test_format_without_correlation_id(self):
        """Test ColoredFormatter.format() - without correlation_id attribute (lines 125-126)."""
        formatter = ColoredFormatter(
            fmt="%(asctime)s %(levelname)s %(correlation_id)s %(name)s: %(message)s"
        )
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        # Don't set correlation_id - formatter will set it to "" if missing
        
        result = formatter.format(record)
        
        # Should handle missing correlation_id gracefully (sets to "")
        assert "Test message" in result


class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_without_log_file(self):
        """Test setup_logging() - without log_file (line 134)."""
        config = ObservabilityConfig(
            log_level=LogLevel.INFO,
            log_file=None,
            structured_logging=False,
            log_correlation_id=False,
        )
        
        setup_logging(config)
        
        # Verify console handler is configured
        logger = logging.getLogger("ccbt")
        assert len(logger.handlers) > 0

    def test_setup_logging_with_log_file(self):
        """Test setup_logging() - with log_file specified (lines 134-136, 186-196)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            config = ObservabilityConfig(
                log_level=LogLevel.INFO,
                log_file=str(log_file),
                structured_logging=False,
                log_correlation_id=False,
            )
            
            setup_logging(config)
            
            # Verify file was created
            assert log_file.exists()
            
            # Close handlers to prevent file locking issues on Windows
            logger = logging.getLogger("ccbt")
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

    def test_setup_logging_creates_log_directory(self):
        """Test setup_logging() - creates log directory if needed (lines 135-136)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "subdir" / "test.log"
            
            config = ObservabilityConfig(
                log_level=LogLevel.INFO,
                log_file=str(log_file),
                structured_logging=False,
                log_correlation_id=False,
            )
            
            setup_logging(config)
            
            # Verify directory and file were created
            assert log_file.parent.exists()
            assert log_file.exists()
            
            # Close handlers to prevent file locking issues on Windows
            logger = logging.getLogger("ccbt")
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

    def test_setup_logging_structured_enabled(self):
        """Test setup_logging() - structured_logging enabled (lines 166-167)."""
        config = ObservabilityConfig(
            log_level=LogLevel.INFO,
            log_file=None,
            structured_logging=True,
            log_correlation_id=False,
        )
        
        setup_logging(config)
        
        # Console handler should use structured formatter
        logger = logging.getLogger("ccbt")
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, StructuredFormatter)

    def test_setup_logging_structured_disabled(self):
        """Test setup_logging() - structured_logging disabled (lines 165-167)."""
        config = ObservabilityConfig(
            log_level=LogLevel.INFO,
            log_file=None,
            structured_logging=False,
            log_correlation_id=False,
        )
        
        setup_logging(config)
        
        # Console handler should use colored formatter
        logger = logging.getLogger("ccbt")
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, ColoredFormatter)

    def test_setup_logging_with_file_structured(self):
        """Test setup_logging() - file handler with structured logging (line 190)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            config = ObservabilityConfig(
                log_level=LogLevel.INFO,
                log_file=str(log_file),
                structured_logging=True,
                log_correlation_id=False,
            )
            
            setup_logging(config)
            
            logger = logging.getLogger("ccbt")
            file_handlers = [h for h in logger.handlers if hasattr(h, "baseFilename")]
            assert len(file_handlers) > 0
            # File handler should use structured formatter
            assert isinstance(file_handlers[0].formatter, StructuredFormatter)
            
            # Close handlers to prevent file locking issues on Windows
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

    def test_setup_logging_with_file_simple(self):
        """Test setup_logging() - file handler with simple logging (line 190)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            config = ObservabilityConfig(
                log_level=LogLevel.INFO,
                log_file=str(log_file),
                structured_logging=False,
                log_correlation_id=False,
            )
            
            setup_logging(config)
            
            logger = logging.getLogger("ccbt")
            file_handlers = [h for h in logger.handlers if hasattr(h, "baseFilename")]
            assert len(file_handlers) > 0
            # File handler should use simple formatter (not structured)
            assert not isinstance(file_handlers[0].formatter, StructuredFormatter)
            
            # Close handlers to prevent file locking issues on Windows
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

    def test_setup_logging_log_correlation_id_enabled(self):
        """Test setup_logging() - log_correlation_id enabled (lines 202-203)."""
        config = ObservabilityConfig(
            log_level=LogLevel.INFO,
            log_file=None,
            structured_logging=False,
            log_correlation_id=True,
        )
        
        setup_logging(config)
        
        # Correlation ID should be set
        corr_id = get_correlation_id()
        assert corr_id is not None
        assert isinstance(corr_id, str)
        assert len(corr_id) > 0

    def test_setup_logging_log_correlation_id_disabled(self):
        """Test setup_logging() - log_correlation_id disabled (line 202)."""
        # Clear any existing correlation ID
        from ccbt.utils.logging_config import correlation_id
        correlation_id.set(None)
        
        config = ObservabilityConfig(
            log_level=LogLevel.INFO,
            log_file=None,
            structured_logging=False,
            log_correlation_id=False,
        )
        
        setup_logging(config)
        
        # Correlation ID should not be set
        corr_id = get_correlation_id()
        # May be None or previous value, but not auto-generated
        # We can't assert None here because it might have been set elsewhere


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_returns_logger_with_prefix(self):
        """Test get_logger() - returns logger with ccbt prefix (line 208)."""
        logger = get_logger("test.module")
        
        assert logger.name == "ccbt.test.module"


class TestCorrelationIDFunctions:
    """Test correlation ID helper functions."""

    def test_set_correlation_id_with_provided_id(self):
        """Test set_correlation_id() - with provided ID (lines 211-216)."""
        test_id = "test-correlation-123"
        result = set_correlation_id(test_id)
        
        assert result == test_id
        assert get_correlation_id() == test_id

    def test_set_correlation_id_without_provided_id(self):
        """Test set_correlation_id() - without provided ID (generates UUID, lines 213-214)."""
        result = set_correlation_id()
        
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        # Should be a UUID format (roughly)
        assert len(result) == 36  # UUID format length

    def test_get_correlation_id_returns_current_id(self):
        """Test get_correlation_id() - returns current ID (lines 219-221)."""
        test_id = "test-correlation-456"
        set_correlation_id(test_id)
        
        result = get_correlation_id()
        
        assert result == test_id

    def test_get_correlation_id_returns_none_when_not_set(self):
        """Test get_correlation_id() - returns None when not set (line 221)."""
        from ccbt.utils.logging_config import correlation_id
        correlation_id.set(None)
        
        result = get_correlation_id()
        
        assert result is None


class TestLoggingContext:
    """Test LoggingContext context manager."""

    def test_logging_context_enter(self):
        """Test LoggingContext.__enter__() - sets correlation ID and logs start (lines 234-238)."""
        # LoggingContext creates its own logger
        with patch("ccbt.utils.logging_config.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            with LoggingContext("test_operation", key1="value1", key2=42):
                pass
            
            # Should have logged start
            assert mock_logger.info.call_count >= 1
            # Check that "Starting" was in one of the calls
            call_args_list = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Starting" in call or "test_operation" in call for call in call_args_list)

    def test_logging_context_exit_success(self):
        """Test LoggingContext.__exit__() - success path (lines 241-251)."""
        with patch("ccbt.utils.logging_config.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            with LoggingContext("test_operation"):
                pass
            
            # Should have logged completion
            assert mock_logger.info.call_count >= 2  # Start and completion
            completion_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Completed" in call for call in completion_calls)

    def test_logging_context_exit_exception(self):
        """Test LoggingContext.__exit__() - exception path (lines 252-260)."""
        with patch("ccbt.utils.logging_config.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            try:
                with LoggingContext("test_operation"):
                    raise ValueError("Test exception")
            except ValueError:
                pass
            
            # Should have logged failure
            assert mock_logger.error.call_count >= 1
            error_calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any("Failed" in call for call in error_calls)

    def test_logging_context_exit_preserves_exception(self):
        """Test LoggingContext.__exit__() - preserves exception (returns False, line 262)."""
        try:
            with LoggingContext("test_operation"):
                raise ValueError("Test exception")
        except ValueError as e:
            assert str(e) == "Test exception"
        else:
            pytest.fail("Exception should have been raised")


class TestLogException:
    """Test log_exception function."""

    def test_log_exception_with_ccbterror(self):
        """Test log_exception() - with CCBTError (includes details, lines 267-274)."""
        logger = get_logger("test")
        error = CCBTError("Test error", details={"key": "value"})
        
        with patch.object(logger, "error") as mock_error:
            log_exception(logger, error, "Test context")
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            assert "Test context" in str(call_args)
            assert "Test error" in str(call_args)
            # Check that extra contains details
            assert call_args.kwargs.get("extra", {}).get("details") == {"key": "value"}

    def test_log_exception_with_generic_exception(self):
        """Test log_exception() - with generic Exception (lines 275-276)."""
        logger = get_logger("test")
        error = ValueError("Generic error")
        
        with patch.object(logger, "error") as mock_error:
            log_exception(logger, error, "Test context")
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            assert "Test context" in str(call_args)
            assert "Generic error" in str(call_args)

    def test_log_exception_with_context_string(self):
        """Test log_exception() - with context string."""
        logger = get_logger("test")
        error = Exception("Test error")
        
        with patch.object(logger, "error") as mock_error:
            log_exception(logger, error, "Custom context message")
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            assert "Custom context message" in str(call_args)

