"""Unified animation executor for composable animations.

Provides a single interface to execute animations with full configuration support.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ccbt.interface.splash.animation_config import AnimationConfig, BackgroundConfig
from ccbt.interface.splash.animation_helpers import AnimationController
from typing import Any


class AnimationExecutor:
    """Executes animations from AnimationConfig objects."""

    def __init__(self, controller: AnimationController | None = None) -> None:
        """Initialize animation executor.
        
        Args:
            controller: Optional AnimationController instance
        """
        self.controller = controller or AnimationController()

    async def execute(self, config: AnimationConfig) -> None:
        """Execute an animation from configuration.
        
        Args:
            config: AnimationConfig instance
        """
        # Map style to execution method
        style_map = {
            "rainbow": self._execute_rainbow,
            "reveal": self._execute_reveal,
            "letters": self._execute_letters,
            "fade": self._execute_fade,
            "flag": self._execute_flag,
            "particles": self._execute_particles,
            "glitch": self._execute_glitch,
            "columns_reveal": self._execute_columns_reveal,
            "columns_color": self._execute_columns_color,
            "columns_wave": self._execute_columns_wave,
            "row_groups_reveal": self._execute_row_groups_reveal,
            "row_groups_color": self._execute_row_groups_color,
            "row_groups_wave": self._execute_row_groups_wave,
            "row_groups_fade": self._execute_row_groups_fade,
            "rainbow_to_color": self._execute_rainbow_to_color,
            "column_swipe": self._execute_column_swipe,
            "arc_reveal": self._execute_arc_reveal,
            "arc_disappear": self._execute_arc_disappear,
            "snake_reveal": self._execute_snake_reveal,
            "snake_disappear": self._execute_snake_disappear,
            "letter_slide_in": self._execute_letter_slide_in,
            "letter_reveal_by_position": self._execute_letter_reveal_by_position,
            "whitespace_background": self._execute_whitespace_background,
            "background_animated": self._execute_background_animated,
            "color_transition": self._execute_color_transition,
            "background_reveal": self._execute_background_reveal,
            "background_disappear": self._execute_background_disappear,
            "background_fade_in": self._execute_background_fade_in,
            "background_fade_out": self._execute_background_fade_out,
            "background_glitch": self._execute_background_glitch,
            "background_rainbow": self._execute_background_rainbow,
        }

        executor = style_map.get(config.style)
        if executor:
            await executor(config)
        else:
            raise ValueError(f"Unknown animation style: {config.style}")

    async def _execute_rainbow(self, config: AnimationConfig) -> None:
        """Execute rainbow animation."""
        # Map direction names to internal names (now fixed in animate_color_per_direction)
        direction_map = {
            "left_to_right": "left_to_right",
            "right_to_left": "right_to_left",
            "top_to_bottom": "top_to_bottom",
            "bottom_to_top": "bottom_to_top",
            "radiant_center_out": "radiant_center_out",
            "radiant_center_in": "radiant_center_in",
        }
        
        internal_direction = direction_map.get(config.direction, config.direction)
        color_palette = config.color_palette or config.color_start or None
        
        await self.controller.animate_color_per_direction(
            config.logo_text,
            direction=internal_direction,
            color_palette=color_palette,
            speed=config.speed,
            duration=config.duration,
        )

    async def _execute_reveal(self, config: AnimationConfig) -> None:
        """Execute reveal animation."""
        await self.controller.reveal_animation(
            config.logo_text,
            direction=config.direction,
            color=config.color_start or "white",
            steps=config.steps,
            reveal_char=config.reveal_char,
            duration=config.duration,
        )

    async def _execute_letters(self, config: AnimationConfig) -> None:
        """Execute letter-by-letter animation."""
        await self.controller.letter_by_letter_animation(
            config.logo_text,
            direction=config.direction,
            color=config.color_start or "white",
            delay_per_letter=config.delay_per_letter,
        )

    async def _execute_fade(self, config: AnimationConfig) -> None:
        """Execute fade animation."""
        if "in" in config.direction.lower() or config.direction == "fade_in":
            await self.controller.fade_in(
                config.logo_text,
                steps=config.steps,
                color=config.color_start or "white",
            )
        elif "out" in config.direction.lower() or config.direction == "fade_out":
            await self.controller.fade_out(
                config.logo_text,
                steps=config.steps,
                color=config.color_start or "white",
            )
        else:
            # Default to fade in
            await self.controller.fade_in(
                config.logo_text,
                steps=config.steps,
                color=config.color_start or "white",
            )

    async def _execute_flag(self, config: AnimationConfig) -> None:
        """Execute flag effect animation."""
        color_palette = config.color_palette or [config.color_start or "blue", "white", "red"]
        await self.controller.flag_effect(
            config.logo_text,
            color_palette=color_palette,
            wave_speed=config.wave_speed,
            wave_amplitude=config.wave_amplitude,
            duration=config.duration,
        )

    async def _execute_particles(self, config: AnimationConfig) -> None:
        """Execute particle effect animation."""
        await self.controller.particle_effect(
            config.logo_text,
            base_color=config.color_start or "cyan",
            density=config.particle_density,
            duration=config.duration,
        )

    async def _execute_glitch(self, config: AnimationConfig) -> None:
        """Execute glitch effect animation."""
        await self.controller.glitch_effect(
            config.logo_text,
            base_color=config.color_start or "white",
            intensity=config.glitch_intensity,
            duration=config.duration,
        )

    async def _execute_columns_reveal(self, config: AnimationConfig) -> None:
        """Execute column reveal animation."""
        await self.controller.animate_columns_reveal(
            config.logo_text,
            direction=config.direction,
            color=config.color_start or "white",
            steps=config.steps,
        )

    async def _execute_columns_color(self, config: AnimationConfig) -> None:
        """Execute column color animation."""
        color_palette = config.color_palette or config.color_start or None
        await self.controller.animate_columns_color(
            config.logo_text,
            direction=config.direction,
            color_palette=color_palette,
            speed=config.speed,
            duration=config.duration,
        )

    async def _execute_columns_wave(self, config: AnimationConfig) -> None:
        """Execute column wave animation."""
        await self.controller.animate_columns_wave(
            config.logo_text,
            color=config.color_start or "white",
            wave_speed=config.wave_speed,
            wave_amplitude=config.wave_amplitude,
            duration=config.duration,
        )

    async def _execute_row_groups_reveal(self, config: AnimationConfig) -> None:
        """Execute row groups reveal animation."""
        await self.controller.animate_row_groups_reveal(
            config.logo_text,
            direction=config.direction,
            color=config.color_start or "white",
            steps=config.steps,
        )

    async def _execute_row_groups_color(self, config: AnimationConfig) -> None:
        """Execute row groups color animation with background support."""
        # If background is configured, use background_animated wrapper
        if config.background and config.background.bg_type != "none":
            await self._execute_background_animated(config)
        else:
            color_palette = config.color_palette or config.color_start or None
            await self.controller.animate_row_groups_color(
                config.logo_text,
                direction=config.direction,
                color_palette=color_palette,
                speed=config.speed,
                duration=config.duration,
            )

    async def _execute_row_groups_wave(self, config: AnimationConfig) -> None:
        """Execute row groups wave animation."""
        await self.controller.animate_row_groups_wave(
            config.logo_text,
            color=config.color_start or "white",
            wave_speed=config.wave_speed,
            wave_amplitude=config.wave_amplitude,
            duration=config.duration,
        )

    async def _execute_row_groups_fade(self, config: AnimationConfig) -> None:
        """Execute row groups fade animation."""
        await self.controller.animate_row_groups_fade(
            config.logo_text,
            direction=config.direction,
            color=config.color_start or "white",
            steps=config.steps,
        )

    async def _execute_rainbow_to_color(self, config: AnimationConfig) -> None:
        """Execute rainbow to color transition."""
        target_color = config.color_finish or config.color_start or "white"
        await self.controller.rainbow_to_color(
            config.logo_text,
            target_color=target_color,
            color_palette=config.color_palette,
            duration=config.duration,
        )

    async def _execute_column_swipe(self, config: AnimationConfig) -> None:
        """Execute column swipe animation with background support."""
        # If background is configured, use background_animated wrapper
        if config.background and config.background.bg_type != "none":
            await self._execute_background_animated(config)
        else:
            await self.controller.column_swipe(
                config.logo_text,
                direction=config.direction,
                color_start=config.color_start or "white",
                color_finish=config.color_finish or "cyan",
                duration=config.duration,
            )

    async def _execute_arc_reveal(self, config: AnimationConfig) -> None:
        """Execute arc reveal animation with background support."""
        # If background is configured, use background_animated wrapper
        if config.background and config.background.bg_type != "none":
            await self._execute_background_animated(config)
        else:
            await self.controller.arc_reveal(
                config.logo_text,
                direction=config.direction,
                color=config.color_start or "white",
                steps=config.steps,
                arc_center_x=config.arc_center_x,
                arc_center_y=config.arc_center_y,
            )

    async def _execute_arc_disappear(self, config: AnimationConfig) -> None:
        """Execute arc disappear animation."""
        await self.controller.arc_disappear(
            config.logo_text,
            direction=config.direction,
            color=config.color_start or "white",
            steps=config.steps,
        )

    async def _execute_snake_reveal(self, config: AnimationConfig) -> None:
        """Execute snake reveal animation with background support."""
        # If background is configured, use background_animated wrapper
        if config.background and config.background.bg_type != "none":
            await self._execute_background_animated(config)
        else:
            await self.controller.snake_reveal(
                config.logo_text,
                direction=config.direction,
                color=config.color_start or "white",
                snake_length=config.snake_length,
                snake_thickness=config.snake_thickness,
                speed=config.speed,
                duration=config.duration,
            )

    async def _execute_snake_disappear(self, config: AnimationConfig) -> None:
        """Execute snake disappear animation."""
        await self.controller.snake_disappear(
            config.logo_text,
            direction=config.direction,
            color=config.color_start or "white",
            snake_length=config.snake_length,
            snake_thickness=config.snake_thickness,
            speed=config.speed,
            duration=config.duration,
        )

    async def _execute_letter_slide_in(self, config: AnimationConfig) -> None:
        """Execute letter slide-in animation."""
        await self.controller.letter_slide_in(
            config.logo_text,
            direction=config.slide_direction,
            color=config.color_start or "white",
            delay_per_letter=config.delay_per_letter,
        )

    async def _execute_letter_reveal_by_position(self, config: AnimationConfig) -> None:
        """Execute letter reveal by position animation."""
        await self.controller.letter_reveal_by_position(
            config.logo_text,
            direction=config.direction,
            color=config.color_start or "white",
            steps=config.steps,
        )

    async def _execute_whitespace_background(self, config: AnimationConfig) -> None:
        """Execute whitespace background animation."""
        # Use separate text color if specified, otherwise use color_start
        text_color = config.background.text_color or config.color_start or "white"
        bg_color = config.background.bg_color_start or config.background.bg_color_palette or "dim white"
        # Use separate background animation speed for color cycling
        bg_animation_speed = config.background.bg_animation_speed if config.background.bg_animate else 1.0
        
        await self.controller.whitespace_background_animation(
            config.logo_text,
            pattern=config.whitespace_pattern,
            bg_color=bg_color,
            text_color=text_color,
            duration=config.duration,
            animation_speed=bg_animation_speed,
        )

    async def _execute_background_animated(self, config: AnimationConfig) -> None:
        """Execute background animation with logo."""
        await self.controller.animate_background_with_logo(
            config.logo_text,
            bg_config=config.background,
            logo_animation_style=config.logo_animation_style,
            logo_color_start=config.color_start,
            logo_color_finish=config.color_finish,
            duration=config.duration,
        )

    async def _execute_color_transition(self, config: AnimationConfig) -> None:
        """Execute color transition animation."""
        await self.controller.animate_color_transition(
            config.logo_text,
            bg_config=config.background,
            logo_color_start=config.color_start or "white",
            logo_color_finish=config.color_finish or "white",
            bg_color_start=config.background.bg_color_start or config.background.bg_color_palette,
            bg_color_finish=config.background.bg_color_finish or config.background.bg_color_palette,
            duration=config.duration,
        )

    async def _execute_background_reveal(self, config: AnimationConfig) -> None:
        """Execute background with reveal animation."""
        await self.controller.animate_background_with_reveal(
            config.logo_text,
            bg_config=config.background,
            logo_color=config.color_start or config.color_palette or "white",
            direction=config.direction,
            reveal_type="reveal",
            duration=config.duration,
        )

    async def _execute_background_disappear(self, config: AnimationConfig) -> None:
        """Execute background with disappear animation."""
        await self.controller.animate_background_with_reveal(
            config.logo_text,
            bg_config=config.background,
            logo_color=config.color_start or config.color_palette or "white",
            direction=config.direction,
            reveal_type="disappear",
            duration=config.duration,
        )

    async def _execute_background_fade_in(self, config: AnimationConfig) -> None:
        """Execute background with fade in animation."""
        await self.controller.animate_background_with_fade(
            config.logo_text,
            bg_config=config.background,
            logo_color=config.color_start or config.color_palette or "white",
            fade_type="fade_in",
            duration=config.duration,
        )

    async def _execute_background_fade_out(self, config: AnimationConfig) -> None:
        """Execute background with fade out animation."""
        await self.controller.animate_background_with_fade(
            config.logo_text,
            bg_config=config.background,
            logo_color=config.color_start or config.color_palette or "white",
            fade_type="fade_out",
            duration=config.duration,
        )

    async def _execute_background_glitch(self, config: AnimationConfig) -> None:
        """Execute background with glitch animation."""
        await self.controller.animate_background_with_glitch(
            config.logo_text,
            bg_config=config.background,
            logo_color=config.color_start or config.color_palette or "white",
            glitch_intensity=config.glitch_intensity,
            duration=config.duration,
        )

    async def _execute_background_rainbow(self, config: AnimationConfig) -> None:
        """Execute background with rainbow animation."""
        logo_palette = config.color_palette or config.color_start
        if isinstance(logo_palette, str):
            logo_palette = [logo_palette]
        elif not isinstance(logo_palette, list):
            logo_palette = ["white"]
        
        bg_palette = config.background.bg_color_palette
        await self.controller.animate_background_with_rainbow(
            config.logo_text,
            bg_config=config.background,
            logo_color_palette=logo_palette,
            bg_color_palette=bg_palette,
            direction=config.direction,
            duration=config.duration,
        )

    async def _execute_row_transition(self, config: AnimationConfig) -> None:
        """Execute row transition animation."""
        await self.controller.animate_row_transition(
            config.logo_text,
            direction=config.direction,
            color=config.color_start or "white",
            duration=config.duration,
        )

