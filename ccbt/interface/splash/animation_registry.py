"""Animation registry for managing available animation types.

Provides registration and weighted selection of animations for random sequences.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ccbt.interface.splash.animation_config import (
    BackgroundConfig,
    OCEAN_PALETTE,
    RAINBOW_PALETTE,
    SUNSET_PALETTE,
)


@dataclass
class AnimationMetadata:
    """Metadata for an animation type."""
    
    name: str
    style: str
    default_duration: float
    min_duration: float = 1.5
    max_duration: float = 2.5
    weight: float = 1.0  # Weight for random selection
    description: str = ""
    color_palettes: list[list[str]] | None = None
    background_types: list[str] | None = None
    directions: list[str] | None = None


class AnimationRegistry:
    """Registry for animation types with metadata and weighted selection."""
    
    def __init__(self) -> None:
        """Initialize animation registry."""
        self._animations: dict[str, AnimationMetadata] = {}
        self._register_defaults()
    
    def register(
        self,
        metadata: AnimationMetadata,
    ) -> None:
        """Register an animation type.
        
        Args:
            metadata: Animation metadata
        """
        self._animations[metadata.name] = metadata
    
    def get(self, name: str) -> AnimationMetadata | None:
        """Get animation metadata by name.
        
        Args:
            name: Animation name
            
        Returns:
            AnimationMetadata or None if not found
        """
        return self._animations.get(name)
    
    def list(self) -> list[str]:
        """List all registered animation names.
        
        Returns:
            List of animation names
        """
        return list(self._animations.keys())
    
    def select_random(self, exclude: list[str] | None = None) -> AnimationMetadata | None:
        """Select a random animation based on weights.
        
        Args:
            exclude: List of animation names to exclude
            
        Returns:
            Random AnimationMetadata or None if no animations available
        """
        if exclude is None:
            exclude = []
        
        available = [
            (name, meta)
            for name, meta in self._animations.items()
            if name not in exclude
        ]
        
        if not available:
            return None
        
        # Weighted random selection
        import random
        
        total_weight = sum(meta.weight for _, meta in available)
        if total_weight == 0:
            return random.choice(available)[1]
        
        r = random.uniform(0, total_weight)
        cumulative = 0.0
        
        for name, meta in available:
            cumulative += meta.weight
            if r <= cumulative:
                return meta
        
        # Fallback to last
        return available[-1][1]
    
    def _register_defaults(self) -> None:
        """Register default animation types."""
        # Color transition animations
        self.register(AnimationMetadata(
            name="color_transition_rainbow_ocean",
            style="color_transition",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.5,
            description="Color transition: Rainbow to Ocean",
            color_palettes=[RAINBOW_PALETTE, OCEAN_PALETTE],
            background_types=["solid", "stars", "waves"],
        ))
        
        self.register(AnimationMetadata(
            name="color_transition_ocean_sunset",
            style="color_transition",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.5,
            description="Color transition: Ocean to Sunset",
            color_palettes=[OCEAN_PALETTE, SUNSET_PALETTE],
            background_types=["solid", "pattern", "particles"],
        ))
        
        self.register(AnimationMetadata(
            name="color_transition_sunset_rainbow",
            style="color_transition",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.5,
            description="Color transition: Sunset to Rainbow",
            color_palettes=[SUNSET_PALETTE, RAINBOW_PALETTE],
            background_types=["solid", "stars", "waves"],
        ))
        
        # Background reveal animations
        self.register(AnimationMetadata(
            name="background_reveal_top_down",
            style="background_reveal",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.2,
            description="Background reveal: Top to bottom",
            color_palettes=[RAINBOW_PALETTE, OCEAN_PALETTE, SUNSET_PALETTE],
            background_types=["stars", "waves", "pattern"],
            directions=["top_down"],
        ))
        
        self.register(AnimationMetadata(
            name="background_reveal_left_right",
            style="background_reveal",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.2,
            description="Background reveal: Left to right",
            color_palettes=[OCEAN_PALETTE, RAINBOW_PALETTE],
            background_types=["waves", "pattern", "particles"],
            directions=["left_right"],
        ))
        
        self.register(AnimationMetadata(
            name="background_reveal_radiant",
            style="background_reveal",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.0,
            description="Background reveal: Radiant from center",
            color_palettes=[RAINBOW_PALETTE, SUNSET_PALETTE],
            background_types=["stars", "particles"],
            directions=["radiant"],
        ))
        
        self.register(AnimationMetadata(
            name="background_reveal_flower_radiant",
            style="background_reveal",
            default_duration=2.2,
            min_duration=1.5,
            max_duration=2.7,
            weight=0.9,
            description="Background reveal: Flower bloom radiant center animations",
            color_palettes=[RAINBOW_PALETTE, OCEAN_PALETTE, SUNSET_PALETTE],
            background_types=["flower"],
            directions=["radiant_center_out", "radiant_center_in"],
        ))
        
        # Background rainbow animations
        self.register(AnimationMetadata(
            name="background_rainbow_left_right",
            style="background_rainbow",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.3,
            description="Background rainbow: Left to right",
            color_palettes=[RAINBOW_PALETTE],
            background_types=["waves", "stars", "pattern"],
            directions=["left_to_right"],
        ))
        
        self.register(AnimationMetadata(
            name="background_rainbow_radiant_out",
            style="background_rainbow",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.0,
            description="Background rainbow: Radiant from center outward",
            color_palettes=[RAINBOW_PALETTE, OCEAN_PALETTE],
            background_types=["stars", "particles"],
            directions=["radiant_center_out"],
        ))
        
        self.register(AnimationMetadata(
            name="background_rainbow_radiant_in",
            style="background_rainbow",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=0.8,
            description="Background rainbow: Radiant from outside inward",
            color_palettes=[RAINBOW_PALETTE, OCEAN_PALETTE],
            background_types=["stars", "particles"],
            directions=["radiant_center_in"],
        ))
        
        self.register(AnimationMetadata(
            name="background_rainbow_gradient",
            style="background_rainbow",
            default_duration=2.2,
            min_duration=1.6,
            max_duration=2.8,
            weight=0.9,
            description="Background rainbow: Gradient wash with center radiance",
            color_palettes=[RAINBOW_PALETTE],
            background_types=["gradient"],
            directions=["left_to_right", "radiant_center_out"],
        ))
        
        # Background fade animations
        self.register(AnimationMetadata(
            name="background_fade_in",
            style="background_fade_in",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.1,
            description="Background fade in",
            color_palettes=[OCEAN_PALETTE, SUNSET_PALETTE],
            background_types=["solid", "pattern", "particles"],
        ))
        
        self.register(AnimationMetadata(
            name="background_fade_out",
            style="background_fade_out",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.1,
            description="Background fade out",
            color_palettes=[SUNSET_PALETTE, OCEAN_PALETTE],
            background_types=["solid", "stars"],
        ))
        
        # Background disappear animations
        self.register(AnimationMetadata(
            name="background_disappear_radiant",
            style="background_disappear",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=1.0,
            description="Background disappear: Radiant",
            color_palettes=[RAINBOW_PALETTE, OCEAN_PALETTE],
            background_types=["pattern", "particles"],
            directions=["radiant"],
        ))
        
        self.register(AnimationMetadata(
            name="background_disappear_flower",
            style="background_disappear",
            default_duration=2.2,
            min_duration=1.6,
            max_duration=2.8,
            weight=0.8,
            description="Background disappear: Flower bloom closing toward center",
            color_palettes=[SUNSET_PALETTE, OCEAN_PALETTE],
            background_types=["flower"],
            directions=["radiant_center_in"],
        ))
        
        # Background glitch animations
        self.register(AnimationMetadata(
            name="background_glitch",
            style="background_glitch",
            default_duration=2.0,
            min_duration=1.5,
            max_duration=2.5,
            weight=0.8,
            description="Background glitch effect",
            color_palettes=[RAINBOW_PALETTE, SUNSET_PALETTE],
            background_types=["pattern", "stars", "waves"],
        ))


# Global registry instance
_registry = AnimationRegistry()


def get_registry() -> AnimationRegistry:
    """Get the global animation registry.
    
    Returns:
        AnimationRegistry instance
    """
    return _registry


def register_animation(metadata: AnimationMetadata) -> None:
    """Register an animation in the global registry.
    
    Args:
        metadata: Animation metadata
    """
    _registry.register(metadata)


def get_animation(name: str) -> AnimationMetadata | None:
    """Get animation metadata from the global registry.
    
    Args:
        name: Animation name
        
    Returns:
        AnimationMetadata or None if not found
    """
    return _registry.get(name)


def select_random_animation(exclude: list[str] | None = None) -> AnimationMetadata | None:
    """Select a random animation from the global registry.
    
    Args:
        exclude: List of animation names to exclude
        
    Returns:
        Random AnimationMetadata or None
    """
    return _registry.select_random(exclude)










