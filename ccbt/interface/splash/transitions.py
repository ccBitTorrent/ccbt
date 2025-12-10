"""Transition system for smooth animation transitions.

Provides base classes and implementations for various transition types with precise duration control.
"""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from typing import Any

from ccbt.interface.splash.color_matching import (
    generate_random_duration,
    generate_smooth_transition_palette,
    interpolate_palette,
)
from ccbt.interface.splash.animation_config import BackgroundConfig


class Transition(ABC):
    """Base class for all transitions."""
    
    def __init__(
        self,
        duration: float | None = None,
        min_duration: float = 1.5,
        max_duration: float = 2.5,
    ) -> None:
        """Initialize transition.
        
        Args:
            duration: Fixed duration (if None, random between min/max)
            min_duration: Minimum duration for random generation
            max_duration: Maximum duration for random generation
        """
        if duration is None:
            duration = generate_random_duration(min_duration, max_duration)
        self.duration = duration
        self.min_duration = min_duration
        self.max_duration = max_duration
    
    @abstractmethod
    async def execute(
        self,
        controller: Any,
        text: str,
        **kwargs: Any,
    ) -> None:
        """Execute the transition.
        
        Args:
            controller: AnimationController instance
            text: Text to animate
            **kwargs: Additional transition parameters
        """
        pass
    
    def get_duration(self) -> float:
        """Get transition duration.
        
        Returns:
            Duration in seconds
        """
        return self.duration


class ColorTransition(Transition):
    """Color transition with precise duration control and smooth color matching."""
    
    def __init__(
        self,
        logo_color_start: str | list[str],
        logo_color_finish: str | list[str],
        bg_color_start: str | list[str] | None = None,
        bg_color_finish: str | list[str] | None = None,
        bg_config: BackgroundConfig | None = None,
        duration: float | None = None,
        min_duration: float = 1.5,
        max_duration: float = 2.5,
        ensure_smooth: bool = True,
    ) -> None:
        """Initialize color transition.
        
        Args:
            logo_color_start: Logo starting color or palette
            logo_color_finish: Logo finishing color or palette
            bg_color_start: Background starting color or palette
            bg_color_finish: Background finishing color or palette
            bg_config: Background configuration
            duration: Fixed duration (if None, random between min/max)
            min_duration: Minimum duration for random generation
            max_duration: Maximum duration for random generation
            ensure_smooth: Whether to ensure smooth color matching
        """
        super().__init__(duration, min_duration, max_duration)
        self.logo_color_start = logo_color_start
        self.logo_color_finish = logo_color_finish
        self.bg_color_start = bg_color_start
        self.bg_color_finish = bg_color_finish
        self.bg_config = bg_config or BackgroundConfig()
        self.ensure_smooth = ensure_smooth
        
        # Ensure smooth transition if requested
        if ensure_smooth:
            self._ensure_smooth_colors()
    
    def _ensure_smooth_colors(self) -> None:
        """Ensure smooth color matching between start and finish."""
        # Ensure logo colors transition smoothly
        if isinstance(self.logo_color_start, list) and isinstance(self.logo_color_finish, list):
            self.logo_color_start, self.logo_color_finish = generate_smooth_transition_palette(
                self.logo_color_start, self.logo_color_finish, ensure_match=True
            )
        
        # Ensure background colors transition smoothly
        if (
            isinstance(self.bg_color_start, list)
            and isinstance(self.bg_color_finish, list)
            and self.bg_color_start
            and self.bg_color_finish
        ):
            self.bg_color_start, self.bg_color_finish = generate_smooth_transition_palette(
                self.bg_color_start, self.bg_color_finish, ensure_match=True
            )
    
    async def execute(
        self,
        controller: Any,
        text: str,
        update_callback: Any | None = None,
    ) -> None:
        """Execute color transition with precise timing.
        
        Args:
            controller: AnimationController instance
            text: Logo text to animate
            update_callback: Optional callback for updates (for Textual widgets) - currently not used
        """
        # Use controller's animate_color_transition method
        # Note: update_callback is not supported by animate_color_transition, so we ignore it
        await controller.animate_color_transition(
            text,
            bg_config=self.bg_config,
            logo_color_start=self.logo_color_start,
            logo_color_finish=self.logo_color_finish,
            bg_color_start=self.bg_color_start,
            bg_color_finish=self.bg_color_finish,
            duration=self.duration,
        )


class FadeTransition(Transition):
    """Fade transition (fade in/out)."""
    
    def __init__(
        self,
        fade_type: str = "in",  # "in", "out", "in_out"
        duration: float | None = None,
        min_duration: float = 1.5,
        max_duration: float = 2.5,
    ) -> None:
        """Initialize fade transition.
        
        Args:
            fade_type: Type of fade ("in", "out", "in_out")
            duration: Fixed duration
            min_duration: Minimum duration
            max_duration: Maximum duration
        """
        super().__init__(duration, min_duration, max_duration)
        self.fade_type = fade_type
    
    async def execute(
        self,
        controller: Any,
        text: str,
        color: str = "white",
        **kwargs: Any,
    ) -> None:
        """Execute fade transition.
        
        Args:
            controller: AnimationController instance
            text: Text to animate
            color: Color for fade
            **kwargs: Additional parameters
        """
        steps = int(self.duration * 20)  # 20 steps per second
        
        if self.fade_type == "in":
            await controller.fade_in(text, steps=steps, color=color)
        elif self.fade_type == "out":
            await controller.fade_out(text, steps=steps, color=color)
        elif self.fade_type == "in_out":
            await controller.fade_in(text, steps=steps // 2, color=color)
            await asyncio.sleep(self.duration / 2)
            await controller.fade_out(text, steps=steps // 2, color=color)


class SlideTransition(Transition):
    """Slide transition (slide in/out from direction)."""
    
    def __init__(
        self,
        direction: str = "left",
        slide_type: str = "in",
        duration: float | None = None,
        min_duration: float = 1.5,
        max_duration: float = 2.5,
    ) -> None:
        """Initialize slide transition.
        
        Args:
            direction: Slide direction ("left", "right", "top", "bottom")
            slide_type: Type of slide ("in", "out")
            duration: Fixed duration
            min_duration: Minimum duration
            max_duration: Maximum duration
        """
        super().__init__(duration, min_duration, max_duration)
        self.direction = direction
        self.slide_type = slide_type
    
    async def execute(
        self,
        controller: Any,
        text: str,
        color: str = "white",
        **kwargs: Any,
    ) -> None:
        """Execute slide transition.
        
        Args:
            controller: AnimationController instance
            text: Text to animate
            color: Color for slide
            **kwargs: Additional parameters
        """
        # Map direction to reveal direction
        direction_map = {
            "left": "right_left",
            "right": "left_right",
            "top": "top_down",
            "bottom": "down_up",
        }
        reveal_direction = direction_map.get(self.direction, "left_right")
        
        steps = int(self.duration * 20)
        
        if self.slide_type == "in":
            await controller.reveal_animation(
                text, direction=reveal_direction, color=color, steps=steps
            )
        else:
            # For slide out, we'd need a disappear animation
            # For now, use fade out
            await controller.fade_out(text, steps=steps, color=color)


class CrossfadeTransition(Transition):
    """Crossfade transition between two texts."""
    
    def __init__(
        self,
        text1: str,
        text2: str,
        color1: str = "white",
        color2: str = "white",
        duration: float | None = None,
        min_duration: float = 1.5,
        max_duration: float = 2.5,
    ) -> None:
        """Initialize crossfade transition.
        
        Args:
            text1: First text
            text2: Second text
            color1: Color for first text
            color2: Color for second text
            duration: Fixed duration
            min_duration: Minimum duration
            max_duration: Maximum duration
        """
        super().__init__(duration, min_duration, max_duration)
        self.text1 = text1
        self.text2 = text2
        self.color1 = color1
        self.color2 = color2
    
    async def execute(
        self,
        controller: Any,
        text: str,  # Ignored, uses text1 and text2
        **kwargs: Any,
    ) -> None:
        """Execute crossfade transition.
        
        Args:
            controller: AnimationController instance
            text: Ignored
            **kwargs: Additional parameters
        """
        # Fade out text1, fade in text2
        steps = int(self.duration * 20)
        half_steps = steps // 2
        
        # Fade out first text
        await controller.fade_out(self.text1, steps=half_steps, color=self.color1)
        
        # Fade in second text
        await controller.fade_in(self.text2, steps=half_steps, color=self.color2)

