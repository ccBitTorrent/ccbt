"""Splash screen manager for verbosity-aware display.

Manages when to show splash screens based on verbosity levels and long-running tasks.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console
    from textual.widgets import Static

from ccbt.cli.verbosity import VerbosityManager
from ccbt.interface.splash.animation_adapter import AnimationAdapter
from ccbt.interface.splash.splash_screen import SplashScreen


class SplashManager:
    """Manages splash screen display based on verbosity and task duration."""
    
    def __init__(
        self,
        console: Any | None = None,
        textual_widget: Any | None = None,
        verbosity: VerbosityManager | None = None,
    ) -> None:
        """Initialize splash manager.
        
        Args:
            console: Rich Console instance (for CLI)
            textual_widget: Textual Static widget (for interface)
            verbosity: VerbosityManager instance (defaults to NORMAL)
        """
        self.console = console
        self.textual_widget = textual_widget
        self.verbosity = verbosity or VerbosityManager(0)  # NORMAL by default
        self._splash_screen: SplashScreen | None = None
        self._adapter: AnimationAdapter | None = None
        self._stop_event = threading.Event()  # Event to signal splash to stop
        self._running_task: asyncio.Task[None] | None = None  # Track running task for cancellation
    
    def should_show_splash(self) -> bool:
        """Check if splash screen should be shown.
        
        Splash screen is shown when:
        - Verbosity is NORMAL (no -v flags)
        - Not in verbose/debug/trace mode
        
        Returns:
            True if splash should be shown
        """
        # Show splash ONLY when verbosity is NORMAL (verbosity_count == 0)
        # Do NOT show when any verbosity flags are used (-v, -vv, -vvv)
        return self.verbosity.verbosity_count == 0
    
    def create_splash_screen(
        self,
        duration: float = 90.0,
        logo_text: str | None = None,
    ) -> SplashScreen:
        """Create a splash screen instance.
        
        Args:
            duration: Animation duration in seconds
            logo_text: Logo text (defaults to LOGO_1)
            
        Returns:
            SplashScreen instance
        """
        splash = SplashScreen(
            console=self.console,
            textual_widget=self.textual_widget,
            logo_text=logo_text,
            duration=duration,
        )
        self._splash_screen = splash
        return splash
    
    def create_adapter(self) -> AnimationAdapter:
        """Create an animation adapter instance.
        
        Returns:
            AnimationAdapter instance
        """
        adapter = AnimationAdapter(
            console=self.console,
            textual_widget=self.textual_widget,
        )
        self._adapter = adapter
        return adapter
    
    async def show_splash_for_task(
        self,
        task_name: str,
        task_duration: float | None = None,
        max_duration: float = 90.0,
        show_progress: bool = True,
    ) -> None:
        """Show splash screen for a long-running task.
        
        Args:
            task_name: Name of the task
            task_duration: Expected task duration (None = use max_duration)
            max_duration: Maximum splash duration
            show_progress: Whether to show progress messages
        """
        if not self.should_show_splash():
            # Don't show splash if verbosity flags are set
            return
        
        # CRITICAL: Don't show splash if no console or textual_widget is available
        # The splash screen requires either a Rich Console or a Textual widget to render
        if not self.console and not self.textual_widget:
            return
        
        # Create splash screen
        duration = task_duration if task_duration else max_duration
        splash = self.create_splash_screen(duration=duration)
        # Store reference to splash manager in splash screen for stop event checking
        splash._splash_manager = self  # type: ignore[attr-defined]
        
        # Create adapter for message overlay
        adapter = self.create_adapter()
        
        # Start splash screen in background
        if show_progress:
            adapter.update_message(f"Starting {task_name}...")
        
        # Run splash screen
        try:
            # Store reference to running task for cancellation
            self._running_task = asyncio.create_task(splash.run())
            
            # Run splash screen asynchronously with stop event checking
            try:
                await asyncio.wait_for(
                    self._running_task,
                    timeout=duration,
                )
            except asyncio.TimeoutError:
                # Splash completed (timeout reached)
                pass
            except asyncio.CancelledError:
                # Task was cancelled (expected when stop_splash is called)
                pass
        except Exception:
            # Error occurred, but don't fail the task
            pass
        finally:
            # Cancel task if still running
            if self._running_task and not self._running_task.done():
                self._running_task.cancel()
                try:
                    await self._running_task
                except (asyncio.CancelledError, Exception):
                    pass
            
            if adapter:
                adapter.clear_messages()
            # Ensure console is cleared when splash ends
            if self.console:
                try:
                    self.console.clear()
                except Exception:
                    pass
    
    def update_progress_message(self, message: str) -> None:
        """Update progress message in splash screen.
        
        Args:
            message: Progress message
        """
        if self._adapter:
            self._adapter.update_message(message)
    
    def clear_progress_messages(self) -> None:
        """Clear progress messages."""
        if self._adapter:
            self._adapter.clear_messages()
    
    def stop_splash(self) -> None:
        """Stop the splash screen animation immediately.
        
        This method signals the splash to stop and clears the console.
        Note: The running task may be in a different thread, so we can't
        directly cancel it, but setting the stop event will cause it to exit.
        """
        # Signal splash to stop (checked in animation loop)
        self._stop_event.set()
        
        # Try to cancel running task if it exists and we're in the same event loop
        # Note: This may not work if the task is in a different thread, but that's OK
        # because the stop event will cause the animation loop to exit
        if self._running_task and not self._running_task.done():
            try:
                # Only cancel if we're in the same event loop
                loop = asyncio.get_running_loop()
                if loop == self._running_task.get_loop():
                    self._running_task.cancel()
            except (RuntimeError, AttributeError):
                # Not in an event loop or task is in different thread - that's OK
                pass
        
        # Clear progress messages
        if self._adapter:
            self._adapter.clear_messages()
        
        # CRITICAL: Clear the console to stop the Live context display
        # This ensures the splash screen actually stops displaying
        # Multiple clear attempts to ensure it's fully cleared
        if self.console:
            try:
                # Clear the console to stop the Live context
                self.console.clear()
                # Print a blank line to ensure terminal is ready for Textual
                # This helps prevent splash content from leaking into the dashboard
                self.console.print("")
            except Exception:
                pass
    
    @staticmethod
    def from_cli_context(
        ctx: dict[str, Any] | None = None,
        console: Any | None = None,
    ) -> SplashManager:
        """Create SplashManager from CLI context.
        
        Args:
            ctx: Click context object
            console: Rich Console instance
            
        Returns:
            SplashManager instance
        """
        from ccbt.cli.verbosity import get_verbosity_from_ctx
        
        verbosity = get_verbosity_from_ctx(ctx)
        return SplashManager(console=console, verbosity=verbosity)
    
    @staticmethod
    def from_verbosity_count(
        verbosity_count: int = 0,
        console: Any | None = None,
    ) -> SplashManager:
        """Create SplashManager from verbosity count.
        
        Args:
            verbosity_count: Number of -v flags (0-3)
            console: Rich Console instance
            
        Returns:
            SplashManager instance
        """
        verbosity = VerbosityManager.from_count(verbosity_count)
        return SplashManager(console=console, verbosity=verbosity)


async def show_splash_if_needed(
    task_name: str,
    verbosity: VerbosityManager | None = None,
    console: Any | None = None,
    duration: float = 90.0,
) -> SplashManager | None:
    """Show splash screen if verbosity allows.
    
    Convenience function to show splash screen for a task.
    
    Args:
        task_name: Name of the task
        verbosity: VerbosityManager instance
        console: Rich Console instance
        duration: Splash duration
        
    Returns:
        SplashManager instance if splash was shown, None otherwise
    """
    manager = SplashManager(console=console, verbosity=verbosity)
    
    if manager.should_show_splash():
        await manager.show_splash_for_task(
            task_name=task_name,
            max_duration=duration,
            show_progress=True,
        )
        return manager
    
    return None

