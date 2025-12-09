"""Message overlay system for splash screen.

Provides bottom-right message display that can be cleared and refreshed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console
    from textual.widgets import Static


class MessageOverlay:
    """Message overlay for displaying messages during splash screen animation.
    
    Supports single-line or multi-line messages displayed in the bottom-right corner.
    Messages can be cleared and refreshed independently of the animation.
    """
    
    def __init__(
        self,
        console: Console | None = None,
        textual_widget: Static | None = None,
        position: str = "bottom_right",
        max_lines: int = 1,
        clear_on_update: bool = True,
    ) -> None:
        """Initialize message overlay.
        
        Args:
            console: Rich Console instance (for CLI)
            textual_widget: Textual Static widget (for interface)
            position: Overlay position ("bottom_right", "bottom_left", "top_right", "top_left")
            max_lines: Maximum number of message lines
            clear_on_update: Whether to clear previous messages on update
        """
        self.console = console
        self.textual_widget = textual_widget
        self.position = position
        self.max_lines = max_lines
        self.clear_on_update = clear_on_update
        self.messages: list[str] = []
        self._last_rendered: str = ""
    
    def add_message(self, message: str, clear: bool | None = None) -> None:
        """Add a message to the overlay.
        
        Args:
            message: Message text
            clear: Whether to clear previous messages (defaults to clear_on_update)
        """
        if clear is None:
            clear = self.clear_on_update
        
        if clear:
            self.messages = []
        
        self.messages.append(message)
        
        # Limit to max_lines
        if len(self.messages) > self.max_lines:
            self.messages = self.messages[-self.max_lines:]
        
        self._update_display()
    
    def clear_messages(self) -> None:
        """Clear all messages."""
        self.messages = []
        self._last_rendered = ""
        self._update_display()
    
    def get_messages(self) -> list[str]:
        """Get current messages.
        
        Returns:
            List of current messages
        """
        return self.messages.copy()
    
    def _update_display(self) -> None:
        """Update the display with current messages.
        
        This is a placeholder - actual rendering is handled by the adapter
        or splash screen that uses this overlay.
        """
        # The actual rendering happens in the animation adapter
        # This method is here for future extension
        pass
    
    def render_overlay(
        self,
        frame_content: Any,
        width: int | None = None,
        height: int | None = None,
    ) -> Any:
        """Render overlay on top of frame content.
        
        Args:
            frame_content: Frame content (Rich renderable)
            width: Terminal width (if known)
            height: Terminal height (if known)
            
        Returns:
            Combined renderable with overlay
        """
        if not self.messages:
            return frame_content
        
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.text import Text
        except ImportError:
            return frame_content
        
        # Create message text
        message_text = Text()
        for i, msg in enumerate(self.messages):
            message_text.append(msg, style="dim white")
            if i < len(self.messages) - 1:
                message_text.append("\n")
        
        # Get terminal dimensions if not provided
        if width is None or height is None:
            try:
                if self.console:
                    width = self.console.width or 80
                    height = self.console.height or 24
                else:
                    width, height = 80, 24
            except Exception:
                width, height = 80, 24
        
        # Position message overlay
        if self.position == "bottom_right":
            # Align to bottom-right
            overlay = Align.right(message_text, vertical="bottom")
        elif self.position == "bottom_left":
            overlay = Align.left(message_text, vertical="bottom")
        elif self.position == "top_right":
            overlay = Align.right(message_text, vertical="top")
        elif self.position == "top_left":
            overlay = Align.left(message_text, vertical="top")
        else:
            overlay = message_text
        
        # Combine frame and overlay
        # For Rich, we can use a Group, but positioning is tricky
        # For now, return the overlay separately and let the adapter handle it
        return Group(frame_content, overlay)
    
    def format_message(self, message: str, style: str = "dim white") -> str:
        """Format a message with style.
        
        Args:
            message: Message text
            style: Rich style string
            
        Returns:
            Formatted message
        """
        return f"[{style}]{message}[/{style}]"


class LoggingMessageOverlay(MessageOverlay):
    """Message overlay that integrates with logging system.
    
    Captures log messages and displays the last 5 log messages in the overlay.
    """
    
    def __init__(
        self,
        console: Console | None = None,
        textual_widget: Static | None = None,
        position: str = "bottom_right",
        max_lines: int = 10,  # Show last 10 log messages
        log_levels: list[str] | None = None,
    ) -> None:
        """Initialize logging message overlay.
        
        Args:
            console: Rich Console instance
            textual_widget: Textual Static widget
            position: Overlay position
            max_lines: Maximum message lines (default: 10 for last 10 logs)
            log_levels: Log levels to capture (default: all levels)
        """
        # Initialize with clear_on_update=False to preserve messages between updates
        super().__init__(console, textual_widget, position, max_lines, clear_on_update=False)
        self.log_levels = log_levels  # None = capture all levels
        self._log_handler: logging.Handler | None = None
        self._log_buffer: list[tuple[str, str]] = []  # List of (level, message) tuples
    
    def capture_log_message(self, level: str, message: str) -> None:
        """Capture a log message and add to overlay.
        
        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
        """
        # Always capture if no level filter, or if level matches
        if self.log_levels is None or level in self.log_levels:
            # Add to buffer (last 5 messages) - don't clear, just append
            self._log_buffer.append((level, message))
            if len(self._log_buffer) > self.max_lines:
                self._log_buffer.pop(0)
            
            # Update messages from buffer - rebuild from buffer, don't clear
            # This preserves messages between updates
            new_messages = []
            for log_level, log_msg in self._log_buffer:
                # Format: "LEVEL: message" (truncate long messages)
                if len(log_msg) > 60:
                    log_msg = log_msg[:57] + "..."
                formatted = f"{log_level}: {log_msg}"
                new_messages.append(formatted)
            
            # Always update messages to ensure they persist
            # This ensures messages are always available for the overlay box
            self.messages = new_messages
            # Don't call _update_display() here - the overlay box will fetch messages when rendering
    
    def setup_log_capture(self) -> None:
        """Setup log message capture using Python logging handler.
        
        Adds a custom handler to capture log messages.
        """
        import logging
        
        class LogCaptureHandler(logging.Handler):
            """Handler that captures log messages for overlay."""
            
            def __init__(self, overlay: LoggingMessageOverlay) -> None:
                super().__init__()
                self.overlay = overlay
                self.setLevel(logging.DEBUG)  # Capture all levels
            
            def emit(self, record: logging.LogRecord) -> None:
                """Emit a log record."""
                try:
                    level = record.levelname
                    message = record.getMessage()
                    self.overlay.capture_log_message(level, message)
                except Exception:
                    pass  # Ignore errors in log capture
        
        # Create and add handler
        self._log_handler = LogCaptureHandler(self)
        
        # Add to root logger to capture all logs
        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_handler)
    
    def teardown_log_capture(self) -> None:
        """Teardown log message capture."""
        if self._log_handler:
            import logging
            root_logger = logging.getLogger()
            root_logger.removeHandler(self._log_handler)
            self._log_handler = None

