"""Tests for logging enhancements.

Tests CorrelationRichHandler, logging helpers, and Rich logging features.
"""

from __future__ import annotations

import logging
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

pytestmark = [pytest.mark.cli, pytest.mark.unit]

from ccbt.cli.verbosity import VerbosityManager
from ccbt.utils.console_utils import (
    log_operation,
    log_result,
    log_user_output,
)
from ccbt.utils.rich_logging import (
    CorrelationRichHandler,
    create_rich_handler,
    log_debug_translated,
    log_error_translated,
    log_info_translated,
    log_warning_translated,
)


class TestCorrelationRichHandler:
    """Test CorrelationRichHandler class."""

    def test_init_with_console(self):
        """Test CorrelationRichHandler initialization with console."""
        console = Console(file=StringIO(), width=80)
        handler = CorrelationRichHandler(console=console)
        assert handler.console is console
        assert handler.show_icons is True
        assert handler.show_colors is True

    def test_init_without_console(self):
        """Test CorrelationRichHandler initialization without console."""
        handler = CorrelationRichHandler()
        assert handler.console is not None

    def test_init_with_options(self):
        """Test CorrelationRichHandler initialization with options."""
        console = Console(file=StringIO(), width=80)
        handler = CorrelationRichHandler(
            console=console, show_icons=False, show_colors=False
        )
        assert handler.show_icons is False
        assert handler.show_colors is False

    def test_level_icons(self):
        """Test that level icons are defined."""
        assert "DEBUG" in CorrelationRichHandler.LEVEL_ICONS
        assert "INFO" in CorrelationRichHandler.LEVEL_ICONS
        assert "WARNING" in CorrelationRichHandler.LEVEL_ICONS
        assert "ERROR" in CorrelationRichHandler.LEVEL_ICONS
        assert "CRITICAL" in CorrelationRichHandler.LEVEL_ICONS

    def test_level_colors(self):
        """Test that level colors are defined."""
        assert "DEBUG" in CorrelationRichHandler.LEVEL_COLORS
        assert "INFO" in CorrelationRichHandler.LEVEL_COLORS
        assert "WARNING" in CorrelationRichHandler.LEVEL_COLORS
        assert "ERROR" in CorrelationRichHandler.LEVEL_COLORS
        assert "CRITICAL" in CorrelationRichHandler.LEVEL_COLORS

    def test_emit_with_correlation_id(self):
        """Test that emit adds correlation ID to record."""
        console = Console(file=StringIO(), width=80)
        handler = CorrelationRichHandler(console=console)
        
        # Mock correlation_id context from logging_config
        with patch("ccbt.utils.logging_config.correlation_id") as mock_correlation:
            mock_correlation.get.return_value = "test-correlation-id"
            
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            
            handler.emit(record)
            assert hasattr(record, "correlation_id")
            assert record.correlation_id == "test-correlation-id"

    def test_emit_without_correlation_id(self):
        """Test that emit handles missing correlation ID."""
        console = Console(file=StringIO(), width=80)
        handler = CorrelationRichHandler(console=console)
        
        with patch("ccbt.utils.logging_config.correlation_id") as mock_correlation:
            mock_correlation.get.return_value = None
            
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            
            handler.emit(record)
            assert hasattr(record, "correlation_id")
            assert record.correlation_id == "no-correlation-id"


class TestCreateRichHandler:
    """Test create_rich_handler function."""

    def test_create_rich_handler_default(self):
        """Test creating Rich handler with defaults."""
        handler = create_rich_handler()
        assert isinstance(handler, CorrelationRichHandler)
        assert handler.level == logging.INFO

    def test_create_rich_handler_with_level(self):
        """Test creating Rich handler with custom level."""
        handler = create_rich_handler(level=logging.DEBUG)
        assert handler.level == logging.DEBUG

    def test_create_rich_handler_with_console(self):
        """Test creating Rich handler with console."""
        console = Console(file=StringIO(), width=80)
        handler = create_rich_handler(console=console)
        assert handler.console is console

    def test_create_rich_handler_with_options(self):
        """Test creating Rich handler with options."""
        handler = create_rich_handler(
            show_icons=False, show_colors=False, show_path=True
        )
        assert handler.show_icons is False
        assert handler.show_colors is False


class TestTranslatedLoggingHelpers:
    """Test translated logging helper functions."""

    def test_log_info_translated(self):
        """Test log_info_translated function."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        
        with patch.object(logger, "info") as mock_info:
            log_info_translated(logger, "Test message")
            mock_info.assert_called_once()

    def test_log_error_translated(self):
        """Test log_error_translated function."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.ERROR)
        
        with patch.object(logger, "error") as mock_error:
            log_error_translated(logger, "Test error")
            mock_error.assert_called_once()

    def test_log_warning_translated(self):
        """Test log_warning_translated function."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.WARNING)
        
        with patch.object(logger, "warning") as mock_warning:
            log_warning_translated(logger, "Test warning")
            mock_warning.assert_called_once()

    def test_log_debug_translated(self):
        """Test log_debug_translated function."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)
        
        with patch.object(logger, "debug") as mock_debug:
            log_debug_translated(logger, "Test debug")
            mock_debug.assert_called_once()


class TestLoggingHelpers:
    """Test logging helper functions from console_utils."""

    def test_log_user_output_with_verbosity(self):
        """Test log_user_output with verbosity manager."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        verbosity = VerbosityManager.from_count(1)  # VERBOSE
        
        with patch.object(logger, "log") as mock_log:
            log_user_output("Test message", verbosity_manager=verbosity, logger=logger)
            mock_log.assert_called_once()

    def test_log_user_output_without_verbosity(self):
        """Test log_user_output without verbosity manager."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        
        with patch.object(logger, "log") as mock_log:
            log_user_output("Test message", logger=logger)
            mock_log.assert_called_once()

    def test_log_user_output_verbosity_filtering(self):
        """Test that log_user_output respects verbosity levels."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)
        verbosity = VerbosityManager.from_count(0)  # NORMAL - should filter DEBUG
        
        with patch.object(logger, "log") as mock_log:
            log_user_output(
                "Debug message",
                verbosity_manager=verbosity,
                logger=logger,
                level=logging.DEBUG,
            )
            # Should not log because verbosity level is too low
            mock_log.assert_not_called()

    def test_log_operation_started(self):
        """Test log_operation with 'started' status."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        
        with patch.object(logger, "log") as mock_log:
            log_operation("Test operation", status="started", logger=logger)
            mock_log.assert_called_once()
            # Should log at INFO level
            call_args = mock_log.call_args
            assert call_args[0][0] == logging.INFO

    def test_log_operation_completed(self):
        """Test log_operation with 'completed' status."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        
        with patch.object(logger, "log") as mock_log:
            log_operation("Test operation", status="completed", logger=logger)
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0] == logging.INFO

    def test_log_operation_failed(self):
        """Test log_operation with 'failed' status."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.ERROR)
        
        with patch.object(logger, "log") as mock_log:
            log_operation("Test operation", status="failed", logger=logger)
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0] == logging.ERROR

    def test_log_result_success(self):
        """Test log_result with success=True."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        
        with patch.object(logger, "log") as mock_log:
            log_result("Test operation", success=True, logger=logger)
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0] == logging.INFO

    def test_log_result_failure(self):
        """Test log_result with success=False."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.ERROR)
        
        with patch.object(logger, "log") as mock_log:
            log_result("Test operation", success=False, logger=logger)
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0] == logging.ERROR

    def test_log_result_with_details(self):
        """Test log_result with details."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        
        with patch.object(logger, "log") as mock_log:
            log_result(
                "Test operation",
                success=True,
                details="Operation completed successfully",
                logger=logger,
            )
            mock_log.assert_called_once()
            # Message should include details
            call_args = mock_log.call_args
            message = call_args[0][1]
            assert "Operation completed successfully" in message

    def test_log_operation_with_verbosity(self):
        """Test log_operation with verbosity manager."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)
        verbosity = VerbosityManager.from_count(0)  # NORMAL
        
        with patch.object(logger, "log") as mock_log:
            log_operation(
                "Test operation",
                status="started",
                verbosity_manager=verbosity,
                logger=logger,
            )
            # Should log because INFO level is allowed
            mock_log.assert_called_once()

    def test_log_operation_verbosity_filtering(self):
        """Test that log_operation respects verbosity levels."""
        logger = logging.getLogger("test")
        logger.setLevel(logging.DEBUG)
        verbosity = VerbosityManager.from_count(0)  # NORMAL - should filter DEBUG
        
        with patch.object(logger, "log") as mock_log:
            # Create a custom status that would log at DEBUG
            # This is a bit of a workaround since log_operation doesn't support DEBUG directly
            # But we can test the verbosity filtering mechanism
            log_operation(
                "Test operation",
                status="started",
                verbosity_manager=verbosity,
                logger=logger,
            )
            # Should still log because 'started' maps to INFO level
            mock_log.assert_called_once()

