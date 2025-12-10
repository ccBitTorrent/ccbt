"""Textual-based renderable for splash screen with stable overlay.

Uses Textual's rendering approach to prevent blinking by creating
stable renderable structures that don't get recreated on each update.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console, RenderableType
    from rich.console import RenderResult


class StableSplashRenderable:
    """A stable renderable that includes splash screen and overlay.
    
    This renderable uses Textual's rendering approach to prevent blinking
    by maintaining a stable structure that only updates content, not structure.
    """
    
    def __init__(
        self,
        frame_content: Any,
        overlay_content: Any,
    ) -> None:
        """Initialize stable splash renderable.
        
        Args:
            frame_content: The main splash screen frame content
            overlay_content: The overlay box content (logs)
        """
        self.frame_content = frame_content
        self.overlay_content = overlay_content
        self._cached_renderable: Any | None = None
    
    def update_frame(self, frame_content: Any) -> None:
        """Update the frame content without recreating structure.
        
        Args:
            frame_content: New frame content
        """
        self.frame_content = frame_content
        self._cached_renderable = None  # Invalidate cache
    
    def update_overlay(self, overlay_content: Any) -> None:
        """Update the overlay content without recreating structure.
        
        Args:
            overlay_content: New overlay content
        """
        self.overlay_content = overlay_content
        self._cached_renderable = None  # Invalidate cache
    
    def __rich_console__(
        self,
        console: Console,
        options: Any,
    ) -> RenderResult:
        """Render using Textual's approach - yields stable renderables.
        
        This method is called by Rich/Textual to render the content.
        Uses a custom approach to overlay the box on top of the frame.
        
        Args:
            console: Rich Console instance
            options: Render options
            
        Yields:
            Stable renderable structure with overlay on top
        """
        from rich.console import Group
        from rich.segment import Segment
        from rich.measure import Measurement
        
        # Rich's Group stacks vertically, which doesn't work for overlays
        # We need to render frame and overlay separately and combine them
        # The overlay is already positioned (top-right) by StableOverlayBox
        
        # Create a renderable that ensures overlay is on top
        class LayeredRenderable:
            """Renderable that ensures overlay renders on top of frame."""
            
            def __init__(self, frame: Any, overlay: Any) -> None:
                self.frame = frame
                self.overlay = overlay
            
            def __rich_measure__(
                self,
                console: Console,
                options: Any,
            ) -> Measurement:
                """Measure based on frame."""
                return Measurement.get(console, options, self.frame)
            
            def __rich_console__(
                self,
                console: Console,
                options: Any,
            ) -> RenderResult:
                """Render frame, then overlay on top."""
                # Render frame first
                yield from console.render(self.frame, options)
                # Then render overlay (already positioned by Align.right)
                # This will overlay on top
                yield from console.render(self.overlay, options)
        
        layered = LayeredRenderable(self.frame_content, self.overlay_content)
        yield layered


class StableOverlayBox:
    """A stable overlay box that doesn't blink on updates.
    
    Uses Textual's rendering approach to maintain structure while updating content.
    """
    
    def __init__(
        self,
        messages: list[str],
        title: str = "[dim]Logs[/dim]",
    ) -> None:
        """Initialize stable overlay box.
        
        Args:
            messages: List of log messages to display
            title: Box title
        """
        self.messages = messages
        self.title = title
        self._cached_panel: Any | None = None
    
    def update_messages(self, messages: list[str]) -> None:
        """Update messages without recreating box structure.
        
        Args:
            messages: New list of messages
        """
        if messages != self.messages:
            self.messages = messages
            self._cached_panel = None  # Invalidate cache
    
    def __rich_console__(
        self,
        console: Console,
        options: Any,
    ) -> RenderResult:
        """Render the overlay box using Textual's stable rendering.
        
        Args:
            console: Rich Console instance
            options: Render options
            
        Yields:
            Stable Panel renderable with messages INSIDE the box
        """
        from rich.text import Text
        from rich.align import Align
        from rich.panel import Panel
        import rich.box
        
        # Always create panel with current messages to ensure they're inside the box
        # This ensures messages are always linked to the box
        message_text = Text()
        if self.messages:
            for i, msg in enumerate(self.messages):
                # Truncate long messages to fit in box
                if len(msg) > 60:
                    msg = msg[:57] + "..."
                # Add message to text - messages are INSIDE the box
                message_text.append(msg, style="dim white")
                if i < len(self.messages) - 1:
                    message_text.append("\n")
        else:
            # Show placeholder when no messages yet
            message_text.append("Waiting for logs...", style="dim white")
        
        # Create a Panel (box) around the messages
        # CRITICAL: Messages are INSIDE the Panel - they're part of the panel content
        panel = Panel(
            message_text,  # Messages are INSIDE the box as the panel's renderable
            title=self.title,
            border_style="dim white",
            box=rich.box.ROUNDED,
            padding=(0, 1),
        )
        
        # Position panel at top-right corner
        # The Align wraps the panel, so the entire box (with messages inside) is positioned
        positioned_panel = Align.right(panel, vertical="top")
        
        yield positioned_panel

