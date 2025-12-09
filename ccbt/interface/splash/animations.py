"""Individual animation segments for splash screen.

Each animation segment is 3-5 seconds and can be combined into a full sequence.
"""

from __future__ import annotations

import asyncio

from ccbt.interface.splash.animation_config import (
    OCEAN_PALETTE,
    RAINBOW_PALETTE,
    SUNSET_PALETTE,
)
from ccbt.interface.splash.animation_helpers import AnimationController, ColorPalette
from ccbt.interface.splash.ascii_art import (
    CCBT_TITLE,
    CCBT_TITLE_BACKSLASH,
    CCBT_TITLE_BLOCK,
    CCBT_TITLE_DASH,
    CCBT_TITLE_PIPE,
    CCBT_TITLE_SLASH,
    LOGO_1,
    NAUTICAL_SHIP,
    ROW_BOAT,
    SAILING_SHIP_TRINIDAD,
    SUBTITLE,
)
from ccbt.interface.splash.color_themes import COLOR_TEMPLATES


class AnimationSegments:
    """Collection of animation segment functions."""

    def __init__(self, controller: AnimationController) -> None:
        """Initialize animation segments.

        Args:
            controller: AnimationController instance

        """
        self.controller = controller
        self.colors = ColorPalette()

    async def title_fade_in(self) -> None:
        """Title fade-in animation with different styles (5 seconds)."""
        # Cycle through different title styles for visual variety
        title_styles = [
            (CCBT_TITLE_BLOCK, self.colors.OCEAN_BLUE),
            (CCBT_TITLE_PIPE, self.colors.DEEP_BLUE),
            (CCBT_TITLE_SLASH, self.colors.TURQUOISE),
            (CCBT_TITLE_DASH, self.colors.SUNSET_ORANGE),
            (CCBT_TITLE_BACKSLASH, self.colors.WAVE_WHITE),
        ]

        for title_text, color in title_styles:
            await self.controller.fade_in(title_text, steps=8, color=color)
            await asyncio.sleep(0.3)  # Brief pause between styles

        # Show subtitle
        await self.controller.play_frames(
            [SUBTITLE],
            frame_duration=1.5,
            color=self.colors.TROPICAL_GREEN,
            clear_between=False,
        )

    async def title_style_transition(self) -> None:
        """Title style transition animation (3 seconds)."""
        # Show different title styles with color transitions
        await self.controller.fade_in(CCBT_TITLE_PIPE, steps=6, color=self.colors.DEEP_BLUE)
        await asyncio.sleep(0.3)
        await self.controller.fade_in(CCBT_TITLE_SLASH, steps=6, color=self.colors.TURQUOISE)
        await asyncio.sleep(0.3)
        await self.controller.fade_in(CCBT_TITLE_DASH, steps=6, color=self.colors.SUNSET_ORANGE)

    async def sailboat_animation(self) -> None:
        """Row boat animation using high-quality ASCII art (4 seconds)."""
        # Use the beautiful row boat with wave effects
        await self.controller.fade_in(ROW_BOAT, steps=10, color=self.colors.OCEAN_BLUE)
        await asyncio.sleep(1.0)  # Let it display

        # Add some wave motion effect by scrolling
        wave_boat = ROW_BOAT
        await self.controller.play_frames(
            [wave_boat] * 5,  # Hold the boat steady
            frame_duration=0.2,
            color=self.colors.OCEAN_BLUE,
        )

    async def ship_of_line_animation(self) -> None:
        """Nautical ship animation using high-quality rigging (5 seconds)."""
        # Use the beautiful nautical ship with detailed rigging
        await self.controller.fade_in(NAUTICAL_SHIP, steps=12, color=self.colors.DEEP_BLUE)
        await asyncio.sleep(2.0)  # Let viewers admire the detail

        # Add subtle wave motion by holding the ship
        await self.controller.play_frames(
            [NAUTICAL_SHIP] * 8,
            frame_duration=0.15,
            color=self.colors.OCEAN_BLUE,
        )

    async def battleship_animation(self) -> None:
        """Trinidad ship animation (Magellan's ship) (5 seconds)."""
        # Use the beautiful Trinidad ship
        await self.controller.fade_in(SAILING_SHIP_TRINIDAD, steps=12, color=self.colors.DEEP_BLUE)
        await asyncio.sleep(2.0)  # Let viewers admire the detail

        # Add subtle motion effect
        await self.controller.play_frames(
            [SAILING_SHIP_TRINIDAD] * 8,
            frame_duration=0.15,
            color=self.colors.OCEAN_BLUE,
        )

    async def ship_comparison_animation(self) -> None:
        """Compare different ship designs (6 seconds)."""
        # Show each ship type with brief display
        await self.controller.fade_in(ROW_BOAT, steps=8, color=self.colors.OCEAN_BLUE)
        await asyncio.sleep(1.5)

        await self.controller.fade_in(NAUTICAL_SHIP, steps=8, color=self.colors.DEEP_BLUE)
        await asyncio.sleep(2.0)

        await self.controller.fade_in(SAILING_SHIP_TRINIDAD, steps=8, color=self.colors.DEEP_BLUE)
        await asyncio.sleep(2.5)

    async def rainbow_logo_animation(self, logo_text: str, duration: float = 5.0) -> None:
        """Rainbow/iridescent logo animation with colors moving left to right."""
        from rich.align import Align
        from rich.console import Group
        from rich.live import Live
        from rich.text import Text

        # Rainbow colors for Rich styling
        rainbow_styles = [
            "red", "red dim", "red", "orange_red1", "dark_orange", "orange1", "yellow", "yellow dim",
            "chartreuse1", "green", "green dim", "spring_green1", "cyan", "cyan dim",
            "deep_sky_blue1", "blue", "blue dim", "blue_violet", "purple", "purple dim",
            "magenta", "magenta dim", "hot_pink",
        ]

        # Use normalized lines for proper alignment (same as other animations)
        lines = self.controller.normalize_logo_lines(logo_text)

        num_colors = len(rainbow_styles)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration

        # Create a Live display for smooth in-place animation
        with Live(console=self.controller.renderer.console, refresh_per_second=12, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                # Calculate color shift based on time for animation
                time_offset = int((asyncio.get_event_loop().time() - start_time) * 8) % num_colors

                # Build the animated logo as Rich Text objects
                logo_lines = []
                for line in lines:
                    text_line = Text()
                    for i, char in enumerate(line):
                        if char == " ":
                            text_line.append(char)
                        else:
                            # Apply rainbow color based on position and time
                            # For left-to-right flow: use (i - time_offset) so colors flow left to right
                            color_index = (i - time_offset) % num_colors
                            style = rainbow_styles[color_index]
                            text_line.append(char, style=style)
                    logo_lines.append(text_line)

                # Center the entire logo block
                centered_logo = Align.center(Group(*logo_lines))
                live.update(centered_logo)

                await asyncio.sleep(0.083)  # ~12 FPS for smooth animation

    async def logo_1_rainbow(self) -> None:
        """Rainbow animation for Logo 1 (5 seconds)."""
        await self.rainbow_logo_animation(LOGO_1, 5.0)

    async def title_fade_out(self) -> None:
        """Title fade-out animation (2 seconds)."""
        await self.controller.fade_out(CCBT_TITLE, steps=10, color=self.colors.OCEAN_BLUE)

    # ============================================================================
    # Color Animation Functions
    # ============================================================================

    async def rainbow_left_to_right(self, logo_text: str, duration: float = 5.0) -> None:
        """Rainbow animation moving left to right."""
        await self.controller.animate_color_per_direction(
            logo_text, direction="left_to_right", duration=duration
        )

    async def rainbow_right_to_left(self, logo_text: str, duration: float = 5.0) -> None:
        """Rainbow animation moving right to left."""
        await self.controller.animate_color_per_direction(
            logo_text, direction="right_to_left", duration=duration
        )

    async def rainbow_top_to_bottom(self, logo_text: str, duration: float = 5.0) -> None:
        """Rainbow animation moving top to bottom."""
        await self.controller.animate_color_per_direction(
            logo_text, direction="top_to_bottom", duration=duration
        )

    async def rainbow_bottom_to_top(self, logo_text: str, duration: float = 5.0) -> None:
        """Rainbow animation moving bottom to top."""
        await self.controller.animate_color_per_direction(
            logo_text, direction="bottom_to_top", duration=duration
        )

    async def rainbow_radiant_center_out(self, logo_text: str, duration: float = 5.0) -> None:
        """Rainbow animation radiating from center outward."""
        await self.controller.animate_color_per_direction(
            logo_text, direction="radiant_center_out", duration=duration
        )

    async def rainbow_radiant_center_in(self, logo_text: str, duration: float = 5.0) -> None:
        """Rainbow animation radiating from outside inward."""
        await self.controller.animate_color_per_direction(
            logo_text, direction="radiant_center_in", duration=duration
        )

    async def rainbow_radiant(self, logo_text: str, duration: float = 5.0) -> None:
        """Rainbow animation radiating from center (alias for center_out)."""
        await self.rainbow_radiant_center_out(logo_text, duration)

    async def custom_color_animation(
        self,
        logo_text: str,
        color_palette: list[str],
        direction: str = "left",
        duration: float = 5.0,
    ) -> None:
        """Custom color animation with specified palette and direction.
        
        Args:
            logo_text: Logo text to animate
            color_palette: List of Rich color style names
            direction: Animation direction ('left', 'right', 'top', 'bottom', 'radiant')
            duration: Animation duration
        """
        await self.controller.animate_color_per_direction(
            logo_text,
            direction=direction,
            color_palette=color_palette,
            duration=duration,
        )

    # ============================================================================
    # Reveal Animation Functions
    # ============================================================================

    async def reveal_top_down(self, logo_text: str, color: str = "cyan", duration: float = 3.0) -> None:
        """Reveal logo from top to bottom."""
        steps = int(duration * 20)
        await self.controller.reveal_animation(
            logo_text, direction="top_down", color=color, steps=steps
        )

    async def reveal_down_up(self, logo_text: str, color: str = "cyan", duration: float = 3.0) -> None:
        """Reveal logo from bottom to top."""
        steps = int(duration * 20)
        await self.controller.reveal_animation(
            logo_text, direction="down_up", color=color, steps=steps
        )

    async def reveal_left_right(self, logo_text: str, color: str = "cyan", duration: float = 3.0) -> None:
        """Reveal logo from left to right."""
        steps = int(duration * 20)
        await self.controller.reveal_animation(
            logo_text, direction="left_right", color=color, steps=steps
        )

    async def reveal_right_left(self, logo_text: str, color: str = "cyan", duration: float = 3.0) -> None:
        """Reveal logo from right to left."""
        steps = int(duration * 20)
        await self.controller.reveal_animation(
            logo_text, direction="right_left", color=color, steps=steps
        )

    async def reveal_radiant(self, logo_text: str, color: str = "cyan", duration: float = 3.0) -> None:
        """Reveal logo radiating from center."""
        steps = int(duration * 20)
        await self.controller.reveal_animation(
            logo_text, direction="radiant", color=color, steps=steps
        )

    async def arc_reveal(
        self,
        logo_text: str,
        color: str = "white",
        direction: str = "radiant_center_out",
        duration: float = 3.5,
    ) -> None:
        """Reveal logo following an arc trajectory."""
        steps = max(30, int(duration * 45))
        await self.controller.arc_reveal(
            logo_text,
            direction=direction,
            color=color,
            steps=steps,
        )

    async def arc_disappear(
        self,
        logo_text: str,
        color: str = "white",
        direction: str = "radiant_center_in",
        duration: float = 3.5,
    ) -> None:
        """Disappear logo following an arc trajectory."""
        steps = max(30, int(duration * 45))
        await self.controller.arc_disappear(
            logo_text,
            direction=direction,
            color=color,
            steps=steps,
        )

    # ============================================================================
    # Letter-by-Letter Animation Functions
    # ============================================================================

    async def letters_top_down(self, logo_text: str, color: str = "white", duration: float = 4.0) -> None:
        """Animate letters appearing top to bottom."""
        total_chars = sum(len(line) for line in logo_text.split("\n") if line.strip())
        delay = duration / total_chars if total_chars > 0 else 0.02
        await self.controller.letter_by_letter_animation(
            logo_text, direction="top_down", color=color, delay_per_letter=delay
        )

    async def letters_down_up(self, logo_text: str, color: str = "white", duration: float = 4.0) -> None:
        """Animate letters appearing bottom to top."""
        total_chars = sum(len(line) for line in logo_text.split("\n") if line.strip())
        delay = duration / total_chars if total_chars > 0 else 0.02
        await self.controller.letter_by_letter_animation(
            logo_text, direction="down_up", color=color, delay_per_letter=delay
        )

    async def letters_left_right(self, logo_text: str, color: str = "white", duration: float = 4.0) -> None:
        """Animate letters appearing left to right."""
        total_chars = sum(len(line) for line in logo_text.split("\n") if line.strip())
        delay = duration / total_chars if total_chars > 0 else 0.02
        await self.controller.letter_by_letter_animation(
            logo_text, direction="left_right", color=color, delay_per_letter=delay
        )

    async def letters_right_left(self, logo_text: str, color: str = "white", duration: float = 4.0) -> None:
        """Animate letters appearing right to left."""
        total_chars = sum(len(line) for line in logo_text.split("\n") if line.strip())
        delay = duration / total_chars if total_chars > 0 else 0.02
        await self.controller.letter_by_letter_animation(
            logo_text, direction="right_left", color=color, delay_per_letter=delay
        )

    # ============================================================================
    # Special Effect Functions
    # ============================================================================

    async def flag_effect_animation(self, logo_text: str, duration: float = 3.0) -> None:
        """Apply flag/wave effect to logo."""
        await self.controller.flag_effect(
            logo_text,
            color_palette=[self.colors.OCEAN_BLUE, self.colors.WAVE_WHITE, self.colors.DEEP_BLUE],
            duration=duration,
        )

    async def particle_effect_animation(
        self,
        logo_text: str,
        base_color: str = "cyan",
        duration: float = 3.0,
    ) -> None:
        """Add particle effects around logo."""
        await self.controller.particle_effect(
            logo_text, base_color=base_color, duration=duration
        )

    async def glitch_effect_animation(
        self,
        logo_text: str,
        base_color: str = "white",
        duration: float = 2.0,
    ) -> None:
        """Apply glitch effect to logo."""
        await self.controller.glitch_effect(
            logo_text, base_color=base_color, duration=duration
        )

    # ============================================================================
    # Fade Variations
    # ============================================================================

    async def fade_in_slow(self, text: str, color: str = "white") -> None:
        """Slow fade in (20 steps)."""
        await self.controller.fade_in(text, steps=20, color=color)

    async def fade_in_fast(self, text: str, color: str = "white") -> None:
        """Fast fade in (5 steps)."""
        await self.controller.fade_in(text, steps=5, color=color)

    async def fade_out_slow(self, text: str, color: str = "white") -> None:
        """Slow fade out (20 steps)."""
        await self.controller.fade_out(text, steps=20, color=color)

    async def fade_out_fast(self, text: str, color: str = "white") -> None:
        """Fast fade out (5 steps)."""
        await self.controller.fade_out(text, steps=5, color=color)

    async def fade_in_out(self, text: str, color: str = "white", hold_duration: float = 1.0) -> None:
        """Fade in, hold, then fade out."""
        await self.controller.fade_in(text, steps=10, color=color)
        await asyncio.sleep(hold_duration)
        await self.controller.fade_out(text, steps=10, color=color)

    # ============================================================================
    # Logo-Specific Convenience Functions
    # ============================================================================

    async def logo_1_rainbow_left(self) -> None:
        """Logo 1 with rainbow left to right."""
        await self.rainbow_left_to_right(LOGO_1, 5.0)

    async def logo_1_rainbow_right(self) -> None:
        """Logo 1 with rainbow right to left."""
        await self.rainbow_right_to_left(LOGO_1, 5.0)

    async def logo_1_rainbow_radiant(self) -> None:
        """Logo 1 with rainbow radiating."""
        await self.rainbow_radiant(LOGO_1, 5.0)

    async def logo_1_reveal_top_down(self) -> None:
        """Logo 1 revealed top to bottom."""
        await self.reveal_top_down(LOGO_1, self.colors.OCEAN_BLUE, 3.0)

    async def logo_1_reveal_radiant(self) -> None:
        """Logo 1 revealed from center."""
        await self.reveal_radiant(LOGO_1, self.colors.TURQUOISE, 3.0)

    async def logo_1_arc_reveal(self) -> None:
        """Logo 1 arc-based reveal for 3D sequences."""
        await self.arc_reveal(
            LOGO_1,
            color=self.colors.WAVE_WHITE,
            direction="radiant_center_out",
            duration=3.2,
        )

    async def logo_1_arc_disappear(self) -> None:
        """Logo 1 arc-based disappear for 3D sequences."""
        await self.arc_disappear(
            LOGO_1,
            color=self.colors.OCEAN_BLUE,
            direction="radiant_center_in",
            duration=3.0,
        )

    async def logo_1_letters_top_down(self) -> None:
        """Logo 1 letters appearing top to bottom."""
        await self.letters_top_down(LOGO_1, self.colors.WAVE_WHITE, 4.0)

    async def logo_1_flag_effect(self) -> None:
        """Logo 1 with flag effect."""
        await self.flag_effect_animation(LOGO_1, 3.0)

    async def logo_1_particles(self) -> None:
        """Logo 1 with particle effects."""
        await self.particle_effect_animation(LOGO_1, self.colors.OCEAN_BLUE, 3.0)

    async def logo_1_glitch(self) -> None:
        """Logo 1 with glitch effect."""
        await self.glitch_effect_animation(LOGO_1, self.colors.WAVE_WHITE, 2.0)

# ============================================================================
# Full Animation Sequence
# ============================================================================

ANIMATION_SEQUENCE = [
    ("logo_1_rainbow", 5.0),          # Rainbow Logo 1 from logo_1.py
]

# Simple demo sequence with rainbow-animated logo
# Total duration: ~5 seconds per loop


