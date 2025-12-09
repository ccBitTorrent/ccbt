"""Background system for splash screen animations.

Provides separated background rendering and animation logic.
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from typing import Any

from ccbt.interface.splash.animation_config import BackgroundConfig


class Background(ABC):
    """Base class for all background types."""
    
    def __init__(self, config: BackgroundConfig) -> None:
        """Initialize background.
        
        Args:
            config: Background configuration
        """
        self.config = config
    
    @abstractmethod
    def generate(
        self,
        width: int,
        height: int,
        time_offset: float = 0.0,
    ) -> list[str]:
        """Generate background lines.
        
        Args:
            width: Terminal width
            height: Terminal height
            time_offset: Time offset for animation
            
        Returns:
            List of background lines
        """
        pass


class SolidBackground(Background):
    """Solid color background."""
    
    def generate(
        self,
        width: int,
        height: int,
        time_offset: float = 0.0,
    ) -> list[str]:
        """Generate solid background.
        
        Args:
            width: Terminal width
            height: Terminal height
            time_offset: Ignored for solid backgrounds
            
        Returns:
            List of empty lines (color applied separately)
        """
        return [" " * width for _ in range(height)]


class PatternBackground(Background):
    """Pattern background (dots/stars)."""
    
    def generate(
        self,
        width: int,
        height: int,
        time_offset: float = 0.0,
    ) -> list[str]:
        """Generate pattern background.
        
        Args:
            width: Terminal width
            height: Terminal height
            time_offset: Time offset for animated patterns
            
        Returns:
            List of pattern lines
        """
        lines = []
        pattern_char = self.config.bg_pattern_char
        density = self.config.bg_pattern_density
        
        for _ in range(height):
            line = ""
            for _ in range(width):
                if random.random() < density:
                    line += pattern_char
                else:
                    line += " "
            lines.append(line)
        
        return lines


class StarsBackground(Background):
    """Star field background."""
    
    def __init__(self, config: BackgroundConfig) -> None:
        """Initialize stars background.
        
        Args:
            config: Background configuration
        """
        super().__init__(config)
        self._stars: list[dict[str, Any]] | None = None
    
    def _generate_stars(self, width: int, height: int) -> list[dict[str, Any]]:
        """Generate star positions.
        
        Args:
            width: Terminal width
            height: Terminal height
            
        Returns:
            List of star dictionaries
        """
        if self._stars is None:
            self._stars = []
            for _ in range(self.config.bg_star_count):
                self._stars.append({
                    'x': random.randint(0, width - 1),
                    'y': random.randint(0, height - 1),
                    'char': random.choice(['·', '*', '+', '.']),
                })
        return self._stars
    
    def generate(
        self,
        width: int,
        height: int,
        time_offset: float = 0.0,
    ) -> list[str]:
        """Generate stars background.
        
        Args:
            width: Terminal width
            height: Terminal height
            time_offset: Time offset for animated stars
            
        Returns:
            List of star field lines
        """
        stars = self._generate_stars(width, height)
        lines = []
        
        for y in range(height):
            line = [" "] * width
            for star in stars:
                if star['y'] == y:
                    line[star['x']] = star['char']
            lines.append("".join(line))
        
        return lines


class WavesBackground(Background):
    """Animated wave background."""
    
    def generate(
        self,
        width: int,
        height: int,
        time_offset: float = 0.0,
    ) -> list[str]:
        """Generate waves background.
        
        Args:
            width: Terminal width
            height: Terminal height
            time_offset: Time offset for wave animation
            
        Returns:
            List of wave lines
        """
        lines = []
        wave_char = self.config.bg_wave_char
        wave_lines = self.config.bg_wave_lines
        
        for y in range(height):
            line = ""
            wave_offset = int(time_offset * 2) % width
            
            for x in range(width):
                # Create wave pattern
                wave_period = width / max(wave_lines, 1) if wave_lines > 0 else width
                wave_x = (x + wave_offset) % width
                wave_phase = (wave_x / wave_period) * 2 * math.pi if wave_period > 0 else 0
                
                # Create multiple wave lines across the height
                wave_y_phase = (y / height) * wave_lines * 2 * math.pi if height > 0 else 0
                combined_phase = wave_phase + wave_y_phase + time_offset
                wave_value = math.sin(combined_phase)
                
                # Draw wave character when wave value is positive
                if wave_value > 0:
                    line += wave_char
                else:
                    line += " "
            
            lines.append(line)
        
        return lines


class ParticlesBackground(Background):
    """Particle background."""
    
    def generate(
        self,
        width: int,
        height: int,
        time_offset: float = 0.0,
    ) -> list[str]:
        """Generate particles background.
        
        Args:
            width: Terminal width
            height: Terminal height
            time_offset: Time offset for animated particles
            
        Returns:
            List of particle lines
        """
        lines = []
        density = self.config.bg_pattern_density
        
        for _ in range(height):
            line = ""
            for _ in range(width):
                if random.random() < density:
                    line += random.choice(['·', '*', '+', '×'])
                else:
                    line += " "
            lines.append(line)
        
        return lines


class GradientBackground(Background):
    """Gradient background."""
    
    def generate(
        self,
        width: int,
        height: int,
        time_offset: float = 0.0,
    ) -> list[str]:
        """Generate gradient background.
        
        Args:
            width: Terminal width
            height: Terminal height
            time_offset: Time offset for animated gradients
            
        Returns:
            List of gradient lines (color applied separately)
        """
        # Gradient color is applied separately, just return empty lines
        return [" " * width for _ in range(height)]


class BackgroundFactory:
    """Factory for creating background instances."""
    
    @staticmethod
    def create(config: BackgroundConfig) -> Background:
        """Create a background instance from config.
        
        Args:
            config: Background configuration
            
        Returns:
            Background instance
        """
        bg_type = config.bg_type
        
        if bg_type == "none":
            return SolidBackground(config)
        elif bg_type == "solid":
            return SolidBackground(config)
        elif bg_type == "gradient":
            return GradientBackground(config)
        elif bg_type == "pattern":
            return PatternBackground(config)
        elif bg_type == "stars":
            return StarsBackground(config)
        elif bg_type == "waves":
            return WavesBackground(config)
        elif bg_type == "particles":
            return ParticlesBackground(config)
        else:
            # Default to solid
            return SolidBackground(config)


class BackgroundAnimator:
    """Handles background animation logic."""
    
    def __init__(self, background: Background) -> None:
        """Initialize background animator.
        
        Args:
            background: Background instance to animate
        """
        self.background = background
        self.config = background.config
    
    def get_color_at(
        self,
        position: tuple[int, int],
        time_offset: float,
    ) -> str:
        """Get background color at a specific position and time.
        
        Args:
            position: (x, y) position
            time_offset: Time offset for animation
            
        Returns:
            Color style string
        """
        bg_color = (
            self.config.bg_color_start
            or self.config.bg_color_palette
            or "dim white"
        )
        
        if isinstance(bg_color, list):
            # Animated palette - cycle through colors
            x, y = position
            bg_anim_speed = self.config.bg_animation_speed
            color_index = int((x + y + time_offset * bg_anim_speed * 10) % len(bg_color))
            return bg_color[color_index]
        else:
            return bg_color
    
    def should_animate(self) -> bool:
        """Check if background should animate.
        
        Returns:
            True if background should animate
        """
        return self.config.bg_animate
    
    def get_animation_speed(self) -> float:
        """Get background animation speed.
        
        Returns:
            Animation speed multiplier
        """
        return self.config.bg_speed














