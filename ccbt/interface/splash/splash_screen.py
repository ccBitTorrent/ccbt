"""Splash screen with animated backgrounds and color transitions.

Compatible with both Rich Console (CLI) and Textual widgets (interface).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console
    from textual.widgets import Static

from ccbt.interface.splash.animation_config import (
    AnimationConfig,
    AnimationSequence,
    BackgroundConfig,
    OCEAN_PALETTE,
    RAINBOW_PALETTE,
    SUNSET_PALETTE,
)
from ccbt.interface.splash.color_themes import COLOR_TEMPLATES
from ccbt.interface.splash.animation_executor import AnimationExecutor
from ccbt.interface.splash.animation_helpers import AnimationController
from ccbt.interface.splash.ascii_art.logo_1 import LOGO_1
from ccbt.interface.splash.sequence_generator import SequenceGenerator


class SplashScreen:
    """Splash screen with animated backgrounds and color transitions.
    
    Compatible with:
    - Rich Console: Use with `rich.live.Live` for CLI
    - Textual Static widget: Use with `Static.update()` for interface
    
    Example (Rich Console):
        ```python
        from rich.live import Live
        from rich.console import Console
        
        console = Console()
        splash = SplashScreen(console=console)
        
        with Live(splash, console=console, refresh_per_second=60):
            await splash.run()
        ```
    
    Example (Textual):
        ```python
        from textual.widgets import Static
        
        splash_widget = Static()
        splash = SplashScreen(textual_widget=splash_widget)
        
        await splash.run()
        ```
    """
    
    def __init__(
        self,
        console: Console | None = None,
        textual_widget: Static | None = None,
        logo_text: str | None = None,
        duration: float = 90.0,
        use_random_sequence: bool = True,
    ) -> None:
        """Initialize splash screen.
        
        Args:
            console: Rich Console instance (for CLI usage)
            textual_widget: Textual Static widget (for interface usage)
            logo_text: Logo text to display (defaults to LOGO_1)
            duration: Total animation duration in seconds (default: 90.0)
            use_random_sequence: Whether to use random sequence generator (default: True)
        """
        self.console = console
        self.textual_widget = textual_widget
        self.logo_text = logo_text or LOGO_1
        self.duration = duration
        self.use_random_sequence = use_random_sequence
        
        # Create controller with console and splash screen reference for overlay
        # Pass splash screen to renderer so it can always include overlay
        from ccbt.interface.splash.animation_helpers import FrameRenderer
        frame_renderer = FrameRenderer(console=console, splash_screen=self)
        self.controller = AnimationController(frame_renderer=frame_renderer)
        
        # Store current frame renderable for overlay integration
        self._current_frame: Any = None
        
        # Create executor with controller
        self.executor = AnimationExecutor(controller=self.controller)
        
        # Copy color templates so we can extend them at runtime without mutating globals
        self._color_templates: dict[str, list[str]] = {
            key: list(value) for key, value in COLOR_TEMPLATES.items()
        }
        self._color_templates.update(
            {
                "ocean_current": ["cyan", "deep_sky_blue1", "blue", "bright_white"],
                "ember_core": ["orange_red1", "gold1", "deep_pink2", "white"],
            }
        )
        # Build animation sequence - always use programmatic random generation
        self.sequence = self._build_random_sequence()
    
    
    def _build_random_sequence(self) -> AnimationSequence:
        """Build a random animation sequence using SequenceGenerator.
        
        Returns:
            AnimationSequence with random animations
        """
        generator = SequenceGenerator(
            target_duration=self.duration,
            min_segment_duration=1.5,
            max_segment_duration=2.5,
        )
        return generator.generate(
            logo_text=self.logo_text,
            ensure_smooth=True,
        )
    
    def _build_animation_sequence(self) -> AnimationSequence:
        """Build a comprehensive 90+ second animation sequence.
        
        Returns:
            AnimationSequence with various transitions and patterns
        """
        sequence = AnimationSequence()
        
        # Segment durations - longer to allow complete transitions
        # Each segment has: fade in (0.5s) -> full (2s) -> fade out (0.5s) -> fade in (0.5s) -> full (2.5s)
        # Improved calculation: ensure segments fit evenly into total duration
        segment_duration = 6.0  # Each segment is 6 seconds (allows complete cycle)
        num_segments = max(1, int(self.duration / segment_duration))
        
        # Adjust segment duration to fit exactly into total duration for smoother transitions
        if num_segments > 0:
            segment_duration = self.duration / num_segments
        
        # Animation patterns to cycle through with varied styles and directions
        patterns = [
            # 1. Color transition: Rainbow solid background with transition, ocean logo -> rainbow logo
            {
                "style": "color_transition",
                "bg_type": "solid",
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color_start": OCEAN_PALETTE,
                "logo_color_finish": RAINBOW_PALETTE,
                "bg_speed": 4.0,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 2. Rainbow: Waves background with transition, left-to-right rainbow
            {
                "style": "background_rainbow",
                "bg_type": "waves",
                "bg_wave_char": "~",
                "bg_wave_lines": 5,
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color_palette": RAINBOW_PALETTE,
                "direction": "left_to_right",
                "bg_speed": 4.5,  # Increased
                "bg_animation_speed": 1.1,  # Increased
            },
            # 4. Disappear: Pattern background with transition, radiant disappear
            {
                "style": "background_disappear",
                "bg_type": "pattern",
                "bg_pattern_char": "·",
                "bg_pattern_density": 0.2,
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": SUNSET_PALETTE,
                "logo_color": SUNSET_PALETTE,  # Will be converted to palette
                "direction": "radiant",
                "bg_speed": 5.0,  # Increased
                "bg_animation_speed": 1.3,  # Increased
            },
            # 5. Fade in: Particles background with transition, fade in with ocean colors
            {
                "style": "background_fade_in",
                "bg_type": "particles",
                "bg_pattern_density": 0.15,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color": OCEAN_PALETTE,  # Will be converted to palette
                "bg_speed": 4.0,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 6. Rainbow: Stars background (dense) with transition, radiant rainbow
            {
                "style": "background_rainbow",
                "bg_type": "stars",
                "bg_star_count": 200,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color_palette": OCEAN_PALETTE,
                "direction": "radiant_center_out",
                "bg_speed": 5.5,  # Increased
                "bg_animation_speed": 1.4,  # Increased
            },
            # 7. Reveal: Waves background (thick) with transition, right-to-left reveal
            {
                "style": "background_reveal",
                "bg_type": "waves",
                "bg_wave_char": "═",
                "bg_wave_lines": 7,
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": SUNSET_PALETTE,
                "logo_color": SUNSET_PALETTE,  # Will be converted to palette
                "direction": "right_left",
                "bg_speed": 4.2,  # Increased
                "bg_animation_speed": 1.1,  # Increased
            },
            # 8. Glitch: Pattern background (dense) with transition, glitch effect
            {
                "style": "background_glitch",
                "bg_type": "pattern",
                "bg_pattern_char": "░",
                "bg_pattern_density": 0.3,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color": RAINBOW_PALETTE,  # Will be converted to palette
                "glitch_intensity": 0.15,
                "bg_speed": 4.8,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 9. Fade out: Particles background (sparse) with transition, fade out
            {
                "style": "background_fade_out",
                "bg_type": "particles",
                "bg_pattern_density": 0.1,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color": OCEAN_PALETTE,  # Will be converted to palette
                "bg_speed": 3.8,  # Increased
                "bg_animation_speed": 1.0,  # Increased
            },
            # 10. Color transition: Solid background with transition, ocean -> sunset
            {
                "style": "color_transition",
                "bg_type": "solid",
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": SUNSET_PALETTE,
                "logo_color_start": SUNSET_PALETTE,
                "logo_color_finish": OCEAN_PALETTE,
                "bg_speed": 4.5,  # Increased
                "bg_animation_speed": 1.3,  # Increased
            },
            # 11. Rainbow: Stars background (medium) with transition, bottom-to-top rainbow
            {
                "style": "background_rainbow",
                "bg_type": "stars",
                "bg_star_count": 150,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color_palette": RAINBOW_PALETTE,
                "direction": "bottom_to_top",
                "bg_speed": 4.3,  # Increased
                "bg_animation_speed": 1.1,  # Increased
            },
            # 12. Reveal: Waves background (thin) with transition, down-up reveal
            {
                "style": "background_reveal",
                "bg_type": "waves",
                "bg_wave_char": "─",
                "bg_wave_lines": 4,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color": OCEAN_PALETTE,  # Will be converted to palette
                "direction": "down_up",
                "bg_speed": 5.0,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 13. Disappear: Pattern background (medium) with transition, left-to-right disappear
            {
                "style": "background_disappear",
                "bg_type": "pattern",
                "bg_pattern_char": "▒",
                "bg_pattern_density": 0.25,
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": SUNSET_PALETTE,
                "logo_color": SUNSET_PALETTE,  # Will be converted to palette
                "direction": "left_right",
                "bg_speed": 4.6,  # Increased
                "bg_animation_speed": 1.1,  # Increased
            },
            # 14. Rainbow: Particles background (medium) with transition, top-to-bottom rainbow
            {
                "style": "background_rainbow",
                "bg_type": "particles",
                "bg_pattern_density": 0.2,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color_palette": RAINBOW_PALETTE,
                "direction": "top_to_bottom",
                "bg_speed": 4.4,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 15. Glitch: Stars background with transition, glitch with rainbow
            {
                "style": "background_glitch",
                "bg_type": "stars",
                "bg_star_count": 100,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color": OCEAN_PALETTE,  # Will be converted to palette
                "glitch_intensity": 0.12,
                "bg_speed": 3.0,  # Increased
                "bg_animation_speed": 0.9,  # Increased
            },
            # 16. Reveal: Solid background with transition, radiant reveal
            {
                "style": "background_reveal",
                "bg_type": "solid",
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color": RAINBOW_PALETTE,  # Will be converted to palette
                "direction": "radiant",
                "bg_speed": 4.0,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 17. Rainbow: Waves background with transition, right-to-left rainbow
            {
                "style": "background_rainbow",
                "bg_type": "waves",
                "bg_wave_char": "~",
                "bg_wave_lines": 6,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color_palette": OCEAN_PALETTE,
                "direction": "right_to_left",
                "bg_speed": 4.7,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 18. Fade in: Pattern background with transition, fade in with sunset
            {
                "style": "background_fade_in",
                "bg_type": "pattern",
                "bg_pattern_char": "·",
                "bg_pattern_density": 0.18,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": SUNSET_PALETTE,
                "logo_color": SUNSET_PALETTE,  # Will be converted to palette
                "bg_speed": 4.1,  # Increased
                "bg_animation_speed": 1.1,  # Increased
            },
            # 19. Color transition: Stars background with transition, rainbow -> ocean
            {
                "style": "color_transition",
                "bg_type": "stars",
                "bg_star_count": 180,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color_start": OCEAN_PALETTE,
                "logo_color_finish": RAINBOW_PALETTE,
                "bg_speed": 4.9,  # Increased
                "bg_animation_speed": 1.3,  # Increased
            },
            # 21. Rainbow: Pattern background, radiant center in
            {
                "style": "background_rainbow",
                "bg_type": "pattern",
                "bg_pattern_char": "▓",
                "bg_pattern_density": 0.28,
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": SUNSET_PALETTE,
                "logo_color_palette": RAINBOW_PALETTE,
                "direction": "radiant_center_in",
                "bg_speed": 5.2,  # Increased
                "bg_animation_speed": 1.4,  # Increased
            },
            # 22. Reveal: Particles background (dense), left-to-right reveal
            {
                "style": "background_reveal",
                "bg_type": "particles",
                "bg_pattern_density": 0.3,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color": RAINBOW_PALETTE,  # Will be converted to palette
                "direction": "left_right",
                "bg_speed": 4.8,  # Increased
                "bg_animation_speed": 1.3,  # Increased
            },
            # 23. Glitch: Waves background (very thick), glitch effect
            {
                "style": "background_glitch",
                "bg_type": "waves",
                "bg_wave_char": "█",
                "bg_wave_lines": 8,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color": OCEAN_PALETTE,  # Will be converted to palette
                "glitch_intensity": 0.18,
                "bg_speed": 5.5,  # Increased
                "bg_animation_speed": 1.5,  # Increased
            },
            # 24. Fade out: Stars background (very dense), fade out
            {
                "style": "background_fade_out",
                "bg_type": "stars",
                "bg_star_count": 250,
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": SUNSET_PALETTE,
                "logo_color": SUNSET_PALETTE,  # Will be converted to palette
                "bg_speed": 4.2,  # Increased
                "bg_animation_speed": 1.1,  # Increased
            },
            # 25. Rainbow: Pattern background (very dense), top-to-bottom rainbow
            {
                "style": "background_rainbow",
                "bg_type": "pattern",
                "bg_pattern_char": "█",
                "bg_pattern_density": 0.35,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color_palette": OCEAN_PALETTE,
                "direction": "top_to_bottom",
                "bg_speed": 5.0,  # Increased
                "bg_animation_speed": 1.4,  # Increased
            },
            # 26. Disappear: Waves background (very thin), down-up disappear
            {
                "style": "background_disappear",
                "bg_type": "waves",
                "bg_wave_char": ".",
                "bg_wave_lines": 3,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color": OCEAN_PALETTE,  # Will be converted to palette
                "direction": "down_up",
                "bg_speed": 4.6,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 27. Color transition: Particles background (very sparse), sunset -> rainbow
            {
                "style": "color_transition",
                "bg_type": "particles",
                "bg_pattern_density": 0.08,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color_start": RAINBOW_PALETTE,
                "logo_color_finish": SUNSET_PALETTE,
                "bg_speed": 4.4,  # Increased
                "bg_animation_speed": 1.3,  # Increased
            },
            # 28. Reveal: Stars background (ultra dense), right-to-left reveal
            {
                "style": "background_reveal",
                "bg_type": "stars",
                "bg_star_count": 300,
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color": RAINBOW_PALETTE,  # Will be converted to palette
                "direction": "right_left",
                "bg_speed": 5.8,  # Increased
                "bg_animation_speed": 1.5,  # Increased
            },
            # 29. Rainbow: Solid background with gradient, radiant center out
            {
                "style": "background_rainbow",
                "bg_type": "solid",
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color_palette": SUNSET_PALETTE,
                "direction": "radiant_center_out",
                "bg_speed": 4.3,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 30. Glitch: Pattern background (ultra dense), high intensity glitch
            {
                "style": "background_glitch",
                "bg_type": "pattern",
                "bg_pattern_char": "▓",
                "bg_pattern_density": 0.4,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color": RAINBOW_PALETTE,  # Will be converted to palette
                "glitch_intensity": 0.2,
                "bg_speed": 5.2,  # Increased
                "bg_animation_speed": 1.4,  # Increased
            },
            # 31. Flower: Flower background with transition, rainbow logo
            {
                "style": "background_rainbow",
                "bg_type": "flower",
                "bg_flower_petals": 6,
                "bg_flower_radius": 0.3,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color_palette": OCEAN_PALETTE,
                "direction": "radiant_center_out",
                "bg_speed": 4.0,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 33. Gradient: Gradient background with color transition
            {
                "style": "color_transition",
                "bg_type": "gradient",
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color_start": OCEAN_PALETTE,
                "logo_color_finish": RAINBOW_PALETTE,
                "bg_speed": 4.5,  # Increased
                "bg_animation_speed": 1.3,  # Increased
            },
            # 34. Background Animated: Waves with animated logo rainbow
            {
                "style": "background_animated",
                "bg_type": "waves",
                "bg_wave_char": "~",
                "bg_wave_lines": 5,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color_palette": RAINBOW_PALETTE,
                "logo_animation_style": "rainbow",
                "bg_speed": 4.3,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 35. Column Swipe: Particles background with column swipe
            {
                "style": "column_swipe",
                "bg_type": "particles",
                "bg_pattern_density": 0.18,
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": SUNSET_PALETTE,
                "logo_color_start": SUNSET_PALETTE,
                "logo_color_finish": OCEAN_PALETTE,
                "direction": "left_to_right",
                "bg_speed": 4.6,  # Increased
                "bg_animation_speed": 1.1,  # Increased
            },
            # 36. Arc Reveal: Pattern background with arc reveal
            {
                "style": "arc_reveal",
                "bg_type": "pattern",
                "bg_pattern_char": "░",
                "bg_pattern_density": 0.22,
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color": OCEAN_PALETTE,  # Will be converted to palette
                "direction": "radiant_center_out",
                "bg_speed": 4.8,  # Increased
                "bg_animation_speed": 1.3,  # Increased
            },
            # 37. Snake Reveal: Stars background with snake reveal
            {
                "style": "snake_reveal",
                "bg_type": "stars",
                "bg_star_count": 160,
                "bg_color_palette": SUNSET_PALETTE,
                "bg_color_start": SUNSET_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color": RAINBOW_PALETTE,  # Will be converted to palette
                "direction": "left_to_right",
                "snake_length": 12,
                "bg_speed": 4.4,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 38. Row Groups Color: Flower background with row groups color animation
            {
                "style": "row_groups_color",
                "bg_type": "flower",
                "bg_flower_petals": 7,
                "bg_flower_radius": 0.35,
                "bg_color_palette": OCEAN_PALETTE,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": RAINBOW_PALETTE,
                "logo_color_palette": RAINBOW_PALETTE,
                "direction": "left_to_right",
                "bg_speed": 4.1,  # Increased
                "bg_animation_speed": 1.1,  # Increased
            },
            # 39. Whitespace Background: Gradient with whitespace pattern
            {
                "style": "whitespace_background",
                "bg_type": "gradient",
                "bg_color_palette": RAINBOW_PALETTE,
                "bg_color_start": RAINBOW_PALETTE,
                "bg_color_finish": OCEAN_PALETTE,
                "logo_color": OCEAN_PALETTE,  # Will be converted to palette
                "whitespace_pattern": "|/—\\",
                "bg_speed": 4.7,  # Increased
                "bg_animation_speed": 1.2,  # Increased
            },
            # 40. Arc reveal with perspective grid for faux 3D entrance
            {
                "style": "arc_reveal",
                "bg_type": "perspective_grid",
                "color_template": "neon_pulse",
                "direction": "radiant_center_out",
                "bg_speed": 3.6,
                "bg_animation_speed": 1.3,
                "bg_pattern_density": 0.12,
                "bg_vanishing_point": 0,
            },
            # 41. Arc disappear with wireframe tunnel sweep
            {
                "style": "arc_disappear",
                "bg_type": "wireframe_tunnel",
                "color_template": "cosmic_depth",
                "direction": "radiant_center_in",
                "bg_speed": 3.2,
                "bg_animation_speed": 1.4,
                "bg_wave_lines": 6,
            },
            # 42. 3D tunnel color transition
            {
                "style": "color_transition",
                "bg_type": "wireframe_tunnel",
                "color_template": "aurora_glass",
                "bg_speed": 3.9,
                "bg_animation_speed": 1.2,
                "logo_color_start": None,
                "logo_color_finish": None,
            },
            # 43. Perspective grid reveal sweep
            {
                "style": "background_reveal",
                "bg_type": "perspective_grid",
                "color_template": "ocean",
                "direction": "left_to_right",
                "bg_pattern_density": 0.18,
                "bg_speed": 3.4,
                "bg_animation_speed": 1.0,
            },
            # 44. Multiple animated flowers with rainbow
            {
                "style": "background_rainbow",
                "bg_type": "flower",
                "bg_flower_count": 6,
                "bg_flower_petals": 8,
                "bg_flower_radius": 0.25,
                "bg_flower_rotation_speed": 1.2,
                "bg_flower_movement_speed": 0.6,
                "bg_color_palette": RAINBOW_PALETTE,
                "logo_color_palette": RAINBOW_PALETTE,
                "direction": "radiant_center_out",
                "bg_speed": 3.8,
                "bg_animation_speed": 1.3,
            },
            # 45. Large single flower with color transition
            {
                "style": "color_transition",
                "bg_type": "flower",
                "bg_flower_count": 1,  # Single large flower
                "bg_flower_petals": 10,
                "bg_flower_radius": 0.8,  # Large size
                "bg_flower_rotation_speed": 0.8,
                "bg_color_start": OCEAN_PALETTE,
                "bg_color_finish": SUNSET_PALETTE,
                "logo_color_start": SUNSET_PALETTE,
                "logo_color_finish": OCEAN_PALETTE,
                "bg_speed": 2.5,
                "bg_animation_speed": 1.0,
            },
            # 46. Multiple rotating flowers with reveal
            {
                "style": "background_reveal",
                "bg_type": "flower",
                "bg_flower_count": 9,
                "bg_flower_petals": 6,
                "bg_flower_radius": 0.2,
                "bg_flower_rotation_speed": 1.5,
                "bg_flower_movement_speed": 0.5,
                "bg_color_palette": SUNSET_PALETTE,
                "logo_color": SUNSET_PALETTE,
                "direction": "radiant_center_out",
                "bg_speed": 4.2,
                "bg_animation_speed": 1.2,
            },
            # 47. Flower field spin with configurable direction and palette
            {
                "style": "background_rainbow",
                "bg_type": "flower",
                "color_template": "meadow_bloom",
                "bg_flower_count": 20,
                "bg_flower_petals": 5,
                "bg_flower_radius": 0.18,
                "bg_flower_rotation_speed": 1.6,
                "bg_flower_movement_speed": 0.95,
                "bg_direction": "diagonal_down",
                "direction": "left_to_right",
                "bg_speed": 4.0,
                "bg_animation_speed": 1.1,
            },
        ]
        
        # Add animations, randomly selecting patterns (programmatic, not deterministic)
        import random
        for i in range(num_segments):
            pattern = random.choice(patterns)
            
            # Create background config
            bg_config = BackgroundConfig(
                bg_type=pattern["bg_type"],
                bg_animate=True,
                bg_speed=pattern["bg_speed"],
                bg_animation_speed=pattern["bg_animation_speed"],
                text_color="bright_white",
            )

            template_palette = self._resolve_template(pattern.get("color_template"))
            
            # Add pattern-specific config
            if pattern["bg_type"] == "stars":
                bg_config.bg_star_count = pattern.get("bg_star_count", 100)
            elif pattern["bg_type"] == "waves":
                bg_config.bg_wave_char = pattern.get("bg_wave_char", "~")
                bg_config.bg_wave_lines = pattern.get("bg_wave_lines", 5)
            elif pattern["bg_type"] == "pattern":
                bg_config.bg_pattern_char = pattern.get("bg_pattern_char", "·")
                bg_config.bg_pattern_density = pattern.get("bg_pattern_density", 0.2)
            elif pattern["bg_type"] == "particles":
                bg_config.bg_pattern_density = pattern.get("bg_pattern_density", 0.15)
            elif pattern["bg_type"] == "flower":
                bg_config.bg_flower_petals = pattern.get("bg_flower_petals", 6)
                bg_config.bg_flower_radius = pattern.get("bg_flower_radius", 0.3)
                # Configure flower count and animation
                # If flower_count not specified, use multiple flowers for animated backgrounds
                bg_config.bg_flower_count = pattern.get("bg_flower_count", 
                    random.randint(4, 8) if bg_config.bg_animate else 1)
                bg_config.bg_flower_rotation_speed = pattern.get("bg_flower_rotation_speed", 
                    random.uniform(0.8, 1.5))
                bg_config.bg_flower_movement_speed = pattern.get("bg_flower_movement_speed", 
                    random.uniform(0.3, 0.7))
                if "bg_direction" in pattern:
                    bg_config.bg_direction = pattern["bg_direction"]
            elif pattern["bg_type"] == "gradient":
                # Gradient background - colors already set above
                # Gradient direction can be set if needed
                if "bg_gradient_direction" in pattern:
                    bg_config.bg_gradient_direction = pattern["bg_gradient_direction"]
            elif pattern["bg_type"] == "perspective_grid":
                bg_config.bg_pattern_density = pattern.get("bg_pattern_density", bg_config.bg_pattern_density)
                if "bg_vanishing_point" in pattern:
                    bg_config.bg_wave_lines = pattern["bg_vanishing_point"]
            elif pattern["bg_type"] == "wireframe_tunnel":
                bg_config.bg_wave_lines = pattern.get("bg_wave_lines", bg_config.bg_wave_lines)
            
            # Set background color palette - ensure all have backgrounds
            if "bg_color_palette" in pattern:
                bg_config.bg_color_palette = pattern["bg_color_palette"]
            if "bg_color_start" in pattern:
                bg_config.bg_color_start = pattern["bg_color_start"]
            if "bg_color_finish" in pattern:
                bg_config.bg_color_finish = pattern["bg_color_finish"]
            if template_palette and not bg_config.bg_color_palette:
                bg_config.bg_color_palette = list(template_palette)
            
            # Ensure ALL animations have a visible background (never "none")
            if bg_config.bg_type == "none":
                bg_config.bg_type = "solid"
                if not bg_config.bg_color_start and not bg_config.bg_color_palette:
                    bg_config.bg_color_start = RAINBOW_PALETTE
                    bg_config.bg_color_palette = RAINBOW_PALETTE
            
            # Double-check: ensure background has colors set
            if not bg_config.bg_color_start and not bg_config.bg_color_palette:
                bg_config.bg_color_start = RAINBOW_PALETTE
                bg_config.bg_color_palette = RAINBOW_PALETTE
            
            # Get animation style (default to color_transition)
            style = pattern.get("style", "color_transition")
            
            # Build animation config based on style
            anim_kwargs = {
                "style": style,
                "logo_text": self.logo_text,
                "background": bg_config,
                "duration": segment_duration,
                "sequence_total_duration": self.duration,
                "name": f"Segment {i+1}/{num_segments}: {style} ({pattern['bg_type']})",
            }
            
            # Add style-specific parameters - prefer palettes over single colors
            if style == "color_transition":
                # Use palettes for color transitions
                logo_start = pattern.get("logo_color_start")
                logo_finish = pattern.get("logo_color_finish")
                if logo_start is None and template_palette:
                    logo_start = list(template_palette)
                if logo_finish is None and template_palette:
                    logo_finish = list(reversed(template_palette))
                logo_start = logo_start or RAINBOW_PALETTE
                logo_finish = logo_finish or OCEAN_PALETTE
                # Ensure both are lists (palettes)
                if isinstance(logo_start, str):
                    logo_start = [logo_start]
                if isinstance(logo_finish, str):
                    logo_finish = [logo_finish]
                anim_kwargs["color_start"] = logo_start
                anim_kwargs["color_finish"] = logo_finish
            elif style in ["background_reveal", "background_disappear", "background_fade_in", "background_fade_out", "background_glitch"]:
                # Use palettes for logo colors
                logo_color = pattern.get("logo_color") or template_palette or RAINBOW_PALETTE
                if isinstance(logo_color, str):
                    logo_color = [logo_color]
                anim_kwargs["color_start"] = logo_color
                anim_kwargs["color_palette"] = logo_color  # Also set as palette
                if "direction" in pattern:
                    anim_kwargs["direction"] = pattern["direction"]
                if "glitch_intensity" in pattern:
                    anim_kwargs["glitch_intensity"] = pattern["glitch_intensity"]
            elif style == "background_rainbow":
                # Use palettes for rainbow
                logo_palette = pattern.get("logo_color_palette") or template_palette or RAINBOW_PALETTE
                if isinstance(logo_palette, str):
                    logo_palette = [logo_palette]
                anim_kwargs["color_palette"] = logo_palette
                if "direction" in pattern:
                    anim_kwargs["direction"] = pattern["direction"]
            elif style == "background_animated":
                # Background animated with logo animation style
                logo_palette = pattern.get("logo_color_palette") or template_palette or RAINBOW_PALETTE
                if isinstance(logo_palette, str):
                    logo_palette = [logo_palette]
                anim_kwargs["color_palette"] = logo_palette
                if "logo_animation_style" in pattern:
                    anim_kwargs["logo_animation_style"] = pattern["logo_animation_style"]
            elif style == "column_swipe":
                # Column swipe with color transition
                logo_start = pattern.get("logo_color_start") or template_palette or RAINBOW_PALETTE
                logo_finish = pattern.get("logo_color_finish") or template_palette or OCEAN_PALETTE
                if isinstance(logo_start, str):
                    logo_start = [logo_start]
                if isinstance(logo_finish, str):
                    logo_finish = [logo_finish]
                anim_kwargs["color_start"] = logo_start
                anim_kwargs["color_finish"] = logo_finish
                if "direction" in pattern:
                    anim_kwargs["direction"] = pattern["direction"]
            elif style == "arc_reveal":
                # Arc reveal with background
                logo_color = pattern.get("logo_color") or template_palette or RAINBOW_PALETTE
                if isinstance(logo_color, str):
                    logo_color = [logo_color]
                anim_kwargs["color_start"] = logo_color
                if "direction" in pattern:
                    anim_kwargs["direction"] = pattern["direction"]
                if "arc_center_x" in pattern:
                    anim_kwargs["arc_center_x"] = pattern["arc_center_x"]
                if "arc_center_y" in pattern:
                    anim_kwargs["arc_center_y"] = pattern["arc_center_y"]
            elif style == "arc_disappear":
                logo_color = pattern.get("logo_color") or template_palette or RAINBOW_PALETTE
                if isinstance(logo_color, str):
                    logo_color = [logo_color]
                anim_kwargs["color_start"] = logo_color
                if "direction" in pattern:
                    anim_kwargs["direction"] = pattern["direction"]
            elif style == "snake_reveal":
                # Snake reveal with background
                logo_color = pattern.get("logo_color") or template_palette or RAINBOW_PALETTE
                if isinstance(logo_color, str):
                    logo_color = [logo_color]
                anim_kwargs["color_start"] = logo_color
                if "direction" in pattern:
                    anim_kwargs["direction"] = pattern["direction"]
                if "snake_length" in pattern:
                    anim_kwargs["snake_length"] = pattern["snake_length"]
            elif style == "row_groups_color":
                # Row groups color with background
                logo_palette = pattern.get("logo_color_palette", RAINBOW_PALETTE)
                if isinstance(logo_palette, str):
                    logo_palette = [logo_palette]
                anim_kwargs["color_palette"] = logo_palette
                if "direction" in pattern:
                    anim_kwargs["direction"] = pattern["direction"]
            elif style == "whitespace_background":
                # Whitespace background
                logo_color = pattern.get("logo_color", RAINBOW_PALETTE)
                if isinstance(logo_color, str):
                    logo_color = [logo_color]
                anim_kwargs["color_start"] = logo_color
                if "whitespace_pattern" in pattern:
                    anim_kwargs["whitespace_pattern"] = pattern["whitespace_pattern"]
            
            # Add animation using the sequence's add_animation method
            anim_config = sequence.add_animation(**anim_kwargs)
            # Adapt speed to duration
            anim_config.adapt_speed_to_duration()
        
        return sequence

    def _resolve_template(self, template_key: str | None) -> list[str] | None:
        """Return a copy of the requested color template, if available."""
        if not template_key:
            return None
        palette = self._color_templates.get(template_key)
        if palette:
            return list(palette)
        return None
    
    async def run(self) -> None:
        """Run the splash screen animation.
        
        Works with both Rich Console and Textual widgets.
        """
        if self.textual_widget:
            # Textual mode: Update widget directly
            await self._run_textual()
        else:
            # Rich Console mode: Use controller's Live context
            await self._run_rich()
    
    async def _run_rich(self) -> None:
        """Run animation with Rich Console."""
        # Don't print to console directly - it interferes with Live contexts
        # Messages will be shown in the overlay instead
        
        for i, anim_config in enumerate(self.sequence.animations):
            # Check if we should stop (if splash_manager has stop_event)
            if hasattr(self, '_splash_manager') and self._splash_manager:
                if hasattr(self._splash_manager, '_stop_event') and self._splash_manager._stop_event.is_set():
                    break
            
            try:
                # Log segment info
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Running segment {i+1}/{len(self.sequence.animations)}: {anim_config.name}")
                await self.executor.execute(anim_config)
            except KeyboardInterrupt:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Animation interrupted by user")
                break
            except asyncio.CancelledError:
                # Task was cancelled - expected when stop_splash is called
                break
            except Exception as e:
                # Log error but continue
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Animation error in segment {i+1}: {e}")
                continue
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Animation sequence completed")
        
        # Ensure final frame always shows complete logo
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.text import Text
            from rich.live import Live
            
            lines = self.logo_text.split("\n")
            logo_lines = []
            for line in lines:
                text_line = Text()
                for char in line:
                    if char == " ":
                        text_line.append(char)
                    else:
                        text_line.append(char, style="white")
                logo_lines.append(text_line)
            
            centered = Align.center(Group(*logo_lines))
            if self.console:
                # Update console with final complete logo
                self.console.print(centered)
        except Exception:
            pass
    
    async def _run_textual(self) -> None:
        """Run animation with Textual widget."""
        if not self.textual_widget:
            return
        
        # For Textual, we need to manually update the widget
        # The animation executor uses Live context which doesn't work with Textual
        # So we'll use the controller directly with a custom update mechanism
        
        for anim_config in self.sequence.animations:
            try:
                # Execute animation with Textual widget update
                await self._execute_with_textual(anim_config)
                # Small delay for Textual to render
                await asyncio.sleep(0.01)
            except KeyboardInterrupt:
                break
            except Exception as e:
                # Log error but continue
                if self.console:
                    self.console.print(f"[red]Animation error: {e}[/red]")
                continue
    async def _execute_with_textual(self, config: AnimationConfig) -> None:
        """Execute animation with Textual widget updates."""
        if not self.textual_widget:
            return
        
        # Create update callback for Textual widget
        def update_widget(renderable: Any) -> None:
            """Update Textual widget with renderable."""
            if self.textual_widget:
                self.textual_widget.update(renderable)
        
        if config.style == "color_transition":
            await self.controller.animate_color_transition(
                config.logo_text,
                bg_config=config.background,
                logo_color_start=config.color_start or "white",
                logo_color_finish=config.color_finish or "white",
                bg_color_start=config.background.bg_color_start or config.background.bg_color_palette,
                bg_color_finish=config.background.bg_color_finish or config.background.bg_color_palette,
                duration=config.duration,
                update_callback=update_widget,
            )
        else:
            # For other styles, use executor but we need to handle Textual updates
            # This is a limitation - other styles may not work perfectly with Textual
            # For now, fallback to Rich mode
            await self.executor.execute(config)
    
    def __rich__(self) -> Any:
        """Rich renderable interface.
        
        Returns:
            Renderable for Rich Console with message overlay
        """
        # Use stored current frame if available, otherwise render default
        frame_content = self._current_frame
        if frame_content is None:
            try:
                from rich.text import Text
                frame_content = Text(self.logo_text, style="white")
            except ImportError:
                return self.logo_text
        
        return frame_content


async def run_splash_screen(
    console: Console | None = None,
    textual_widget: Static | None = None,
    duration: float = 90.0,
) -> None:
    """Run splash screen animation.
    
    Convenience function to create and run a splash screen.
    
    Args:
        console: Rich Console instance (for CLI)
        textual_widget: Textual Static widget (for interface)
        duration: Animation duration in seconds
    """
    splash = SplashScreen(
        console=console,
        textual_widget=textual_widget,
        duration=duration,
    )
    await splash.run()

