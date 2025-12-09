"""Unified animation adapter for splash screen system.

Provides a single interface that integrates templates, transitions, backgrounds,
and message overlays for both Rich Console and Textual widgets.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console
    from textual.widgets import Static

from ccbt.interface.splash.animation_config import BackgroundConfig
from ccbt.interface.splash.animation_helpers import AnimationController
from ccbt.interface.splash.backgrounds import BackgroundFactory, BackgroundAnimator
from ccbt.interface.splash.templates import Template, get_template
from ccbt.interface.splash.transitions import ColorTransition, Transition


class MessageOverlay:
    """Message overlay for displaying messages during splash screen."""
    
    def __init__(
        self,
        console: Any | None = None,
        textual_widget: Any | None = None,
        position: str = "bottom_right",
        max_lines: int = 1,
    ) -> None:
        """Initialize message overlay.
        
        Args:
            console: Rich Console instance (for CLI)
            textual_widget: Textual Static widget (for interface)
            position: Overlay position ("bottom_right", "bottom_left", "top_right", "top_left")
            max_lines: Maximum number of message lines
        """
        self.console = console
        self.textual_widget = textual_widget
        self.position = position
        self.max_lines = max_lines
        self.messages: list[str] = []
    
    def add_message(self, message: str) -> None:
        """Add a message to the overlay.
        
        Args:
            message: Message text
        """
        self.messages.append(message)
        if len(self.messages) > self.max_lines:
            self.messages.pop(0)
        self._update_display()
    
    def clear_messages(self) -> None:
        """Clear all messages."""
        self.messages = []
        self._update_display()
    
    def _update_display(self) -> None:
        """Update the display with current messages."""
        # Message overlay rendering is handled by the adapter
        # This is just for message management
        pass
    
    def get_messages(self) -> list[str]:
        """Get current messages.
        
        Returns:
            List of current messages
        """
        return self.messages.copy()


class AnimationAdapter:
    """Unified adapter for animation rendering.
    
    Supports both Rich Console (CLI) and Textual widgets (interface).
    Integrates templates, transitions, backgrounds, and message overlays.
    """
    
    def __init__(
        self,
        console: Any | None = None,
        textual_widget: Any | None = None,
    ) -> None:
        """Initialize animation adapter.
        
        Args:
            console: Rich Console instance (for CLI)
            textual_widget: Textual Static widget (for interface)
        """
        self.console = console
        self.textual_widget = textual_widget
        self.controller = AnimationController()
        if console:
            self.controller.renderer.console = console
        
    
    async def render_with_template(
        self,
        template_name: str,
        transition: Transition,
        bg_config: BackgroundConfig | None = None,
        update_callback: Any | None = None,
    ) -> None:
        """Render animation with template, transition, and background.
        
        Args:
            template_name: Name of template to use
            transition: Transition to apply
            bg_config: Background configuration
            update_callback: Optional callback for updates (for Textual)
        """
        # Get template
        template = get_template(template_name)
        if template is None:
            # Fallback to loading default templates
            from ccbt.interface.splash.templates import load_default_templates
            load_default_templates()
            template = get_template(template_name)
        
        if template is None:
            raise ValueError(f"Template '{template_name}' not found")
        
        # Get template content
        template_content = template.content
        
        # Create background if configured
        if bg_config is None:
            bg_config = BackgroundConfig()
        
        # Execute transition
        await transition.execute(
            controller=self.controller,
            text=template_content,
            update_callback=update_callback,
        )
    
    async def render_with_text(
        self,
        text: str,
        transition: Transition,
        bg_config: BackgroundConfig | None = None,
        update_callback: Any | None = None,
    ) -> None:
        """Render animation with text, transition, and background.
        
        Args:
            text: Text to animate
            transition: Transition to apply
            bg_config: Background configuration
            update_callback: Optional callback for updates (for Textual)
        """
        # Create background if configured
        if bg_config is None:
            bg_config = BackgroundConfig()
        
        # Execute transition
        await transition.execute(
            controller=self.controller,
            text=text,
            update_callback=update_callback,
        )
    
    def update_message(self, message: str) -> None:
        """Update message overlay.
        
        Note: Messages are now automatically captured from logging system.
        This method is kept for backward compatibility.
        
        Args:
            message: Message to display (ignored - use logging instead)
        """
        # Messages are now captured from logging system automatically
        # This method is kept for backward compatibility but does nothing
        pass
    
    def clear_messages(self) -> None:
        """Clear message overlay (deprecated - no-op)."""
        pass
    
    def render_frame_with_overlay(
        self,
        frame_content: Any,
        messages: list[str] | None = None,
    ) -> Any:
        """Render frame (overlay removed - returns frame as-is).
        
        Args:
            frame_content: Frame content (Rich renderable)
            messages: Optional messages to display (ignored)
            
        Returns:
            Frame renderable without overlay
        """
        return frame_content
    
    async def run_sequence(
        self,
        transitions: list[Transition],
        template_name: str | None = None,
        text: str | None = None,
        bg_config: BackgroundConfig | None = None,
    ) -> None:
        """Run a sequence of transitions.
        
        Args:
            transitions: List of transitions to execute
            template_name: Template name (if using template)
            text: Text content (if not using template)
            bg_config: Background configuration
        """
        if template_name:
            for transition in transitions:
                await self.render_with_template(
                    template_name=template_name,
                    transition=transition,
                    bg_config=bg_config,
                )
        elif text:
            for transition in transitions:
                await self.render_with_text(
                    text=text,
                    transition=transition,
                    bg_config=bg_config,
                )
        else:
            raise ValueError("Either template_name or text must be provided")

