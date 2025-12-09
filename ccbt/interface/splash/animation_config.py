"""Animation configuration system for composable animations.

Provides a unified interface for creating start, middle, and finish animations
that can be chained together with transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BackgroundConfig:
    """Configuration for background animation."""

    # Background type
    bg_type: str = "none"  # none, solid, gradient, pattern, stars, waves, particles, flower

    # Color configuration
    bg_color_start: str | list[str] | None = None  # Single color or gradient start
    bg_color_finish: str | list[str] | None = None  # Single color or gradient end
    bg_color_palette: list[str] | None = None  # Full color palette for animated backgrounds
    
    # Text color (separate from background)
    text_color: str | list[str] | None = None  # Text color (overrides main color_start for text)

    # Animation
    bg_animate: bool = False  # Whether background should animate
    bg_direction: str = "left_to_right"  # Animation direction
    bg_speed: float = 2.0  # Background animation speed (for pattern movement)
    bg_animation_speed: float = 1.0  # Background color animation speed (for palette cycling)
    bg_duration: float | None = None  # Background animation duration (None = match logo)

    # Pattern-specific options
    bg_pattern_char: str = "·"  # Character for pattern backgrounds
    bg_pattern_density: float = 0.1  # Density of pattern elements
    bg_star_count: int = 50  # Number of stars for star background
    bg_wave_char: str = "~"  # Character for wave background
    bg_wave_lines: int = 3  # Number of wave lines
    bg_flower_petals: int = 6  # Number of petals for flower background
    bg_flower_radius: float = 0.3  # Radius of flower pattern (0.0-1.0)
    bg_flower_count: int = 1  # Number of flowers to render (1 = single large, >1 = multiple animated)
    bg_flower_rotation_speed: float = 1.0  # Rotation speed multiplier for flowers
    bg_flower_movement_speed: float = 0.5  # Movement speed for multiple flowers

    # Gradient options
    bg_gradient_direction: str = "vertical"  # vertical, horizontal, radial, diagonal

    def __post_init__(self) -> None:
        """Validate and set defaults."""
        # Ensure background always has colors if type is not "none"
        if self.bg_type != "none":
            if self.bg_type == "solid" and self.bg_color_start is None and self.bg_color_palette is None:
                # Default to a subtle dark background if nothing is set
                self.bg_color_start = "black"
                self.bg_color_palette = ["black", "dim white"]
            elif self.bg_type == "gradient" and self.bg_color_start is None:
                self.bg_color_start = "black"
                self.bg_color_finish = "blue"
            elif self.bg_color_start is None and self.bg_color_palette is None:
                # For any other background type, ensure at least a default palette
                self.bg_color_palette = ["black", "dim white"]


@dataclass
class AnimationConfig:
    """Configuration for a single animation segment."""

    # Animation type
    style: str = "rainbow"  # rainbow, reveal, letters, fade, flag, particles, glitch,
                            # rainbow_to_color, column_swipe, arc_reveal, arc_disappear,
                            # snake_reveal, snake_disappear, letter_slide_in, letter_reveal_by_position,
                            # whitespace_background, row_transition

    # Content
    logo_text: str = ""

    # Color configuration
    color_start: str | list[str] | None = None  # Single color or palette start
    color_finish: str | list[str] | None = None  # Single color or palette end
    color_palette: list[str] | None = None  # Full color palette

    # Direction/flow
    direction: str = "left_to_right"  # left_to_right, right_to_left, top_to_bottom, 
                                      # bottom_to_top, radiant_center_out, radiant_center_in

    # Timing
    duration: float = 3.0
    speed: float = 8.0
    steps: int = 30
    sequence_total_duration: float | None = None  # Total duration of entire sequence for adaptive timing

    # Style-specific options
    reveal_char: str = "█"
    delay_per_letter: float = 0.02
    wave_speed: float = 2.0
    wave_amplitude: float = 2.0
    particle_density: float = 0.1
    glitch_intensity: float = 0.1
    
    # New animation options
    snake_length: int = 10
    snake_thickness: int = 1  # Thickness of snake perpendicular to direction
    arc_center_x: int | None = None
    arc_center_y: int | None = None
    whitespace_pattern: str = "|/—\\"
    slide_direction: str = "left"  # For letter_slide_in

    # Background configuration
    background: BackgroundConfig = field(default_factory=BackgroundConfig)
    
    # Logo animation style when using background animations
    logo_animation_style: str = "rainbow"  # Style for logo when background is animated

    # Transition
    transition_type: str = "none"  # none, fade, crossfade, slide
    transition_duration: float = 0.5
    transition_min_duration: float = 1.5  # Minimum transition duration (for random)
    transition_max_duration: float = 2.5  # Maximum transition duration (for random)
    ensure_smooth_transition: bool = True  # Ensure smooth color matching between transitions

    # Metadata
    name: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        """Validate and set defaults."""
        if not self.name:
            self.name = f"{self.style}_{self.direction}"
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate animation configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        if self.duration <= 0:
            raise ValueError(f"Animation duration must be positive, got {self.duration}")
        
        if self.speed <= 0:
            raise ValueError(f"Animation speed must be positive, got {self.speed}")
        
        if self.steps <= 0:
            raise ValueError(f"Animation steps must be positive, got {self.steps}")
        
        # Validate style-specific options
        if self.style == "reveal" and not self.reveal_char:
            raise ValueError("Reveal animation requires reveal_char")
        
        if self.style in ["snake_reveal", "snake_disappear"]:
            if self.snake_length <= 0:
                raise ValueError(f"Snake length must be positive, got {self.snake_length}")
            if self.snake_thickness <= 0:
                raise ValueError(f"Snake thickness must be positive, got {self.snake_thickness}")
        
        if self.style == "glitch" and not (0.0 <= self.glitch_intensity <= 1.0):
            raise ValueError(f"Glitch intensity must be between 0.0 and 1.0, got {self.glitch_intensity}")
    
    def adapt_speed_to_duration(self) -> None:
        """Adapt speed and steps based on sequence total duration.
        
        If sequence_total_duration is set, adjusts speed and steps
        to ensure animations complete properly within the allocated time.
        """
        if self.sequence_total_duration is None:
            return
        
        # Calculate adaptive speed based on sequence length
        # Longer sequences should have slower speeds to maintain visual consistency
        duration_ratio = self.duration / self.sequence_total_duration if self.sequence_total_duration > 0 else 1.0
        
        # Adapt speed: longer sequences need slower speeds
        # Base speed of 8.0 for 3.0s duration, scale inversely with duration ratio
        if duration_ratio < 0.1:
            # Very short segments: faster speed
            self.speed = 8.0 * (0.1 / max(duration_ratio, 0.01))
        elif duration_ratio > 0.5:
            # Long segments: slower speed
            self.speed = 8.0 * (0.5 / duration_ratio)
        else:
            # Normal segments: keep base speed
            self.speed = 8.0
        
        # Adapt steps: ensure smooth animation regardless of duration
        # Base steps of 30 for 3.0s, scale with duration
        self.steps = max(10, int(30 * (self.duration / 3.0)))
        
        # Adapt background speeds if background is configured
        if self.background:
            # Background speed should scale with segment duration
            if self.background.bg_speed > 0:
                self.background.bg_speed = self.background.bg_speed * (3.0 / max(self.duration, 0.1))
            if self.background.bg_animation_speed > 0:
                self.background.bg_animation_speed = self.background.bg_animation_speed * (3.0 / max(self.duration, 0.1))


@dataclass
class AnimationSequence:
    """A sequence of animations with transitions."""

    animations: list[AnimationConfig] = field(default_factory=list)
    loop: bool = False
    loop_count: int = 1  # -1 for infinite

    def add_animation(
        self,
        style: str,
        logo_text: str,
        **kwargs: Any,
    ) -> AnimationConfig:
        """Add an animation to the sequence.
        
        Args:
            style: Animation style
            logo_text: Logo text to animate
            **kwargs: Additional configuration options
            
        Returns:
            The created AnimationConfig
        """
        config = AnimationConfig(style=style, logo_text=logo_text, **kwargs)
        self.animations.append(config)
        return config

    def add_start_animation(
        self,
        logo_text: str,
        style: str = "reveal",
        direction: str = "top_down",
        **kwargs: Any,
    ) -> AnimationConfig:
        """Add a start animation (typically reveal).
        
        Args:
            logo_text: Logo text
            style: Animation style (default: reveal)
            direction: Reveal direction
            **kwargs: Additional options
            
        Returns:
            The created AnimationConfig
        """
        return self.add_animation(
            style=style,
            logo_text=logo_text,
            direction=direction,
            name="start",
            **kwargs,
        )

    def add_middle_animation(
        self,
        logo_text: str,
        style: str = "rainbow",
        direction: str = "left_to_right",
        **kwargs: Any,
    ) -> AnimationConfig:
        """Add a middle animation (typically rainbow/color).
        
        Args:
            logo_text: Logo text
            style: Animation style (default: rainbow)
            direction: Color flow direction
            **kwargs: Additional options
            
        Returns:
            The created AnimationConfig
        """
        return self.add_animation(
            style=style,
            logo_text=logo_text,
            direction=direction,
            name="middle",
            **kwargs,
        )

    def add_finish_animation(
        self,
        logo_text: str,
        style: str = "fade",
        **kwargs: Any,
    ) -> AnimationConfig:
        """Add a finish animation (typically fade out).
        
        Args:
            logo_text: Logo text
            style: Animation style (default: fade)
            **kwargs: Additional options
            
        Returns:
            The created AnimationConfig
        """
        return self.add_animation(
            style=style,
            logo_text=logo_text,
            name="finish",
            **kwargs,
        )


# Predefined color palettes
RAINBOW_PALETTE = [
    "red", "red dim", "red", "orange_red1", "dark_orange", "orange1", "yellow", "yellow dim",
    "chartreuse1", "green", "green dim", "spring_green1", "cyan", "cyan dim",
    "deep_sky_blue1", "blue", "blue dim", "blue_violet", "purple", "purple dim",
    "magenta", "magenta dim", "hot_pink",
]

OCEAN_PALETTE = [
    "bright_blue", "blue", "cyan", "deep_sky_blue1", "turquoise",
]

SUNSET_PALETTE = [
    "red", "orange_red1", "dark_orange", "orange1", "yellow",
]

HOLIDAY_PALETTE = [
    "bright_red", "bright_green", "bright_blue", "yellow",
]

