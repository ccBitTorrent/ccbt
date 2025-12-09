"""Sequence generator for creating random animation sequences.

Generates random sequences up to 90 seconds with smooth transitions.
"""

from __future__ import annotations

import random
from typing import Any

from ccbt.interface.splash.animation_config import (
    AnimationConfig,
    AnimationSequence,
    BackgroundConfig,
    OCEAN_PALETTE,
    RAINBOW_PALETTE,
    SUNSET_PALETTE,
)
from ccbt.interface.splash.animation_registry import (
    get_registry,
    select_random_animation,
)
from ccbt.interface.splash.color_matching import (
    generate_random_duration,
    select_matching_palettes,
)


class SequenceGenerator:
    """Generates random animation sequences with smooth transitions."""
    
    def __init__(
        self,
        target_duration: float = 90.0,
        min_segment_duration: float = 1.5,
        max_segment_duration: float = 2.5,
    ) -> None:
        """Initialize sequence generator.
        
        Args:
            target_duration: Target total duration in seconds
            min_segment_duration: Minimum segment duration
            max_segment_duration: Maximum segment duration
        """
        self.target_duration = target_duration
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
        self.registry = get_registry()
    
    def generate(
        self,
        logo_text: str,
        ensure_smooth: bool = True,
    ) -> AnimationSequence:
        """Generate a random animation sequence.
        
        Args:
            logo_text: Logo text to animate
            ensure_smooth: Whether to ensure smooth color transitions
            
        Returns:
            AnimationSequence with random animations
        """
        sequence = AnimationSequence()
        current_duration = 0.0
        current_palette: list[str] | None = None
        used_animations: list[str] = []
        
        # Generate segments until we reach target duration
        while current_duration < self.target_duration:
            # Select random animation
            animation_meta = select_random_animation(
                exclude=used_animations if len(used_animations) > 5 else None
            )
            
            if animation_meta is None:
                break
            
            # Generate random duration for this segment
            segment_duration = generate_random_duration(
                self.min_segment_duration,
                self.max_segment_duration,
            )
            
            # Check if adding this segment would exceed target
            if current_duration + segment_duration > self.target_duration:
                # Adjust duration to fit
                segment_duration = self.target_duration - current_duration
                if segment_duration < self.min_segment_duration:
                    break
            
            # Select color palettes with smooth transitions
            if ensure_smooth and current_palette is not None:
                # Ensure smooth transition from previous palette
                available_palettes = [
                    OCEAN_PALETTE,
                    RAINBOW_PALETTE,
                    SUNSET_PALETTE,
                ]
                start_palette, end_palette = select_matching_palettes(
                    current_palette=current_palette,
                    available_palettes=available_palettes,
                )
            else:
                # First segment or smooth transitions disabled
                if animation_meta.color_palettes:
                    start_palette = random.choice(animation_meta.color_palettes)
                    # Select end palette that matches
                    available = [
                        p for p in animation_meta.color_palettes if p != start_palette
                    ]
                    if available:
                        end_palette = random.choice(available)
                    else:
                        end_palette = random.choice([OCEAN_PALETTE, RAINBOW_PALETTE, SUNSET_PALETTE])
                else:
                    start_palette = random.choice([OCEAN_PALETTE, RAINBOW_PALETTE, SUNSET_PALETTE])
                    end_palette = random.choice([OCEAN_PALETTE, RAINBOW_PALETTE, SUNSET_PALETTE])
            
            # Update current palette for next segment
            current_palette = end_palette
            
            # Select background type
            if animation_meta.background_types:
                bg_type = random.choice(animation_meta.background_types)
            else:
                bg_type = random.choice(["solid", "stars", "waves", "pattern", "particles", "flower", "gradient"])
            
            # Create background config
            bg_config = BackgroundConfig(
                bg_type=bg_type,
                bg_animate=True,
                bg_speed=random.uniform(3.0, 5.0),
                bg_animation_speed=random.uniform(1.0, 1.5),
                bg_color_start=start_palette,
                bg_color_finish=end_palette,
                bg_color_palette=start_palette,
            )
            
            # Set background-specific options
            if bg_type == "stars":
                bg_config.bg_star_count = random.randint(50, 200)
            elif bg_type == "waves":
                bg_config.bg_wave_char = random.choice(["~", "═", "─", "."])
                bg_config.bg_wave_lines = random.randint(3, 8)
            elif bg_type == "pattern":
                bg_config.bg_pattern_char = random.choice(["·", "░", "▒", "▓"])
                bg_config.bg_pattern_density = random.uniform(0.1, 0.3)
            elif bg_type == "particles":
                bg_config.bg_pattern_density = random.uniform(0.1, 0.3)
            elif bg_type == "flower":
                bg_config.bg_flower_petals = random.randint(5, 8)
                bg_config.bg_flower_radius = random.uniform(0.2, 0.4)
            elif bg_type == "gradient":
                # Gradient background - colors already set above
                bg_config.bg_gradient_direction = random.choice(["vertical", "horizontal", "radial", "diagonal"])
            
            # Select direction if applicable
            direction_choices = [
                "left_right",
                "right_left",
                "top_down",
                "down_up",
                "radiant_center_out",
                "radiant_center_in",
            ]
            direction = random.choice(direction_choices)
            if animation_meta.directions:
                direction = random.choice(animation_meta.directions)
            
            # Create animation config
            anim_kwargs: dict[str, Any] = {
                "style": animation_meta.style,
                "logo_text": logo_text,
                "background": bg_config,
                "duration": segment_duration,
                "sequence_total_duration": self.target_duration,
                "name": f"{animation_meta.name} ({segment_duration:.1f}s)",
            }
            
            # Add style-specific parameters
            if animation_meta.style == "color_transition":
                anim_kwargs["color_start"] = start_palette
                anim_kwargs["color_finish"] = end_palette
            elif animation_meta.style in [
                "background_reveal",
                "background_disappear",
                "background_fade_in",
                "background_fade_out",
                "background_glitch",
            ]:
                anim_kwargs["color_start"] = start_palette
                anim_kwargs["color_palette"] = start_palette
                if animation_meta.style in ["background_reveal", "background_disappear"]:
                    anim_kwargs["direction"] = direction
                if animation_meta.style == "background_glitch":
                    anim_kwargs["glitch_intensity"] = random.uniform(0.1, 0.2)
            elif animation_meta.style == "background_rainbow":
                anim_kwargs["color_palette"] = start_palette
                anim_kwargs["direction"] = direction
            
            # Create config and adapt speed to duration
            config = sequence.add_animation(**anim_kwargs)
            config.adapt_speed_to_duration()
            
            # Update duration and tracking
            current_duration += segment_duration
            used_animations.append(animation_meta.name)
            
            # Reset used animations list periodically to allow repeats
            if len(used_animations) > 10:
                used_animations = used_animations[-5:]
        
        return sequence
    
    def generate_with_template(
        self,
        template_name: str = "logo_1",
        ensure_smooth: bool = True,
    ) -> AnimationSequence:
        """Generate sequence using a template.
        
        Args:
            template_name: Template name
            ensure_smooth: Whether to ensure smooth transitions
            
        Returns:
            AnimationSequence
        """
        from ccbt.interface.splash.templates import get_template, load_default_templates
        
        # Load templates if needed
        template = get_template(template_name)
        if template is None:
            load_default_templates()
            template = get_template(template_name)
        
        if template is None:
            raise ValueError(f"Template '{template_name}' not found")
        
        return self.generate(template.content, ensure_smooth=ensure_smooth)


def generate_random_sequence(
    logo_text: str,
    duration: float = 90.0,
    ensure_smooth: bool = True,
) -> AnimationSequence:
    """Generate a random animation sequence.
    
    Convenience function for generating random sequences.
    
    Args:
        logo_text: Logo text to animate
        duration: Target duration in seconds
        ensure_smooth: Whether to ensure smooth transitions
        
    Returns:
        AnimationSequence
    """
    generator = SequenceGenerator(target_duration=duration)
    return generator.generate(logo_text, ensure_smooth=ensure_smooth)










