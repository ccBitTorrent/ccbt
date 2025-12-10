"""Color matching system for smooth transitions.

Provides algorithms for matching colors and generating smooth color transitions.
"""

from __future__ import annotations

import random
from typing import Any

from ccbt.interface.splash.animation_config import (
    OCEAN_PALETTE,
    RAINBOW_PALETTE,
    SUNSET_PALETTE,
)


def color_similarity(color1: str, color2: str) -> float:
    """Calculate similarity between two Rich color names.
    
    This is a heuristic-based similarity since we don't have RGB values.
    Colors are considered similar if they share common prefixes or are in the same family.
    
    Args:
        color1: First color name
        color2: Second color name
        
    Returns:
        Similarity score between 0.0 (different) and 1.0 (identical)
    """
    if color1 == color2:
        return 1.0
    
    # Normalize colors (remove 'bright_', 'dim ', etc.)
    def normalize_color(color: str) -> str:
        color = color.lower().strip()
        if color.startswith("bright_"):
            return color[7:]
        if color.startswith("dim "):
            return color[4:]
        return color
    
    norm1 = normalize_color(color1)
    norm2 = normalize_color(color2)
    
    if norm1 == norm2:
        return 0.8  # Same base color, different intensity
    
    # Check for color families
    color_families = {
        "blue": ["blue", "cyan", "turquoise", "deep_sky_blue", "blue_violet"],
        "red": ["red", "orange_red", "dark_orange", "orange", "hot_pink", "magenta"],
        "green": ["green", "chartreuse", "spring_green"],
        "yellow": ["yellow", "gold"],
        "purple": ["purple", "magenta", "blue_violet"],
        "white": ["white", "silver", "bone_white"],
    }
    
    for family, members in color_families.items():
        if norm1 in members and norm2 in members:
            return 0.6  # Same color family
    
    # Check for complementary colors (opposite on color wheel)
    complementary_pairs = [
        ("red", "cyan"),
        ("green", "magenta"),
        ("blue", "yellow"),
        ("orange", "blue"),
    ]
    
    for pair in complementary_pairs:
        if (norm1 in pair and norm2 in pair) or (norm2 in pair and norm1 in pair):
            return 0.3  # Complementary colors (somewhat similar)
    
    return 0.1  # Different colors


def find_matching_color(
    target_color: str,
    palette: list[str],
    min_similarity: float = 0.5,
) -> str | None:
    """Find a color in a palette that matches the target color.
    
    Args:
        target_color: Target color to match
        palette: List of colors to search
        min_similarity: Minimum similarity threshold
        
    Returns:
        Matching color or None if no match found
    """
    best_match = None
    best_score = 0.0
    
    for color in palette:
        score = color_similarity(target_color, color)
        if score > best_score:
            best_score = score
            best_match = color
    
    if best_score >= min_similarity:
        return best_match
    
    return None


def generate_smooth_transition_palette(
    start_palette: list[str],
    end_palette: list[str],
    ensure_match: bool = True,
) -> tuple[list[str], list[str]]:
    """Generate palettes that transition smoothly.
    
    Ensures the end color of start_palette matches the start color of end_palette.
    
    Args:
        start_palette: Starting color palette
        end_palette: Ending color palette
        ensure_match: Whether to ensure smooth transition
        
    Returns:
        Tuple of (adjusted_start_palette, adjusted_end_palette)
    """
    if not ensure_match or not start_palette or not end_palette:
        return start_palette, end_palette
    
    # Get the last color of start palette
    start_end = start_palette[-1]
    
    # Find matching color in end palette
    matching_color = find_matching_color(start_end, end_palette, min_similarity=0.4)
    
    if matching_color:
        # Reorder end_palette to start with matching color
        if matching_color != end_palette[0]:
            idx = end_palette.index(matching_color)
            end_palette = [matching_color] + [
                c for c in end_palette if c != matching_color
            ]
    
    return start_palette, end_palette


def interpolate_color(
    color1: str,
    color2: str,
    progress: float,
) -> str:
    """Interpolate between two colors.
    
    Args:
        color1: Starting color
        color2: Ending color
        progress: Progress from 0.0 (color1) to 1.0 (color2)
        
    Returns:
        Interpolated color name
    """
    if progress <= 0.0:
        return color1
    if progress >= 1.0:
        return color2
    
    # Simple interpolation: choose color based on progress
    # For better results, we'd need RGB values, but this works for Rich colors
    if progress < 0.5:
        # Closer to color1
        if "bright_" in color1:
            return color1
        return color1
    else:
        # Closer to color2
        if "bright_" in color2:
            return color2
        return color2


def interpolate_palette(
    palette1: list[str],
    palette2: list[str],
    progress: float,
) -> list[str]:
    """Interpolate between two palettes.
    
    Args:
        palette1: Starting palette
        palette2: Ending palette
        progress: Progress from 0.0 (palette1) to 1.0 (palette2)
        
    Returns:
        Interpolated palette
    """
    if progress <= 0.0:
        return palette1
    if progress >= 1.0:
        return palette2
    
    # Interpolate by mixing colors from both palettes
    result = []
    max_len = max(len(palette1), len(palette2))
    
    for i in range(max_len):
        color1 = palette1[i % len(palette1)] if palette1 else "white"
        color2 = palette2[i % len(palette2)] if palette2 else "white"
        result.append(interpolate_color(color1, color2, progress))
    
    return result


def get_palette_by_name(name: str) -> list[str]:
    """Get a predefined palette by name.
    
    Args:
        name: Palette name (ocean, rainbow, sunset, holiday)
        
    Returns:
        Color palette list
    """
    palettes = {
        "ocean": OCEAN_PALETTE,
        "rainbow": RAINBOW_PALETTE,
        "sunset": SUNSET_PALETTE,
    }
    
    return palettes.get(name.lower(), RAINBOW_PALETTE)


def generate_random_duration(min_duration: float = 1.5, max_duration: float = 2.5) -> float:
    """Generate a random duration between min and max.
    
    Args:
        min_duration: Minimum duration in seconds
        max_duration: Maximum duration in seconds
        
    Returns:
        Random duration
    """
    return random.uniform(min_duration, max_duration)


def select_matching_palettes(
    current_palette: list[str] | None = None,
    available_palettes: list[list[str]] | None = None,
) -> tuple[list[str], list[str]]:
    """Select two palettes that transition smoothly.
    
    Args:
        current_palette: Current palette (end color will be matched)
        available_palettes: List of available palettes to choose from
        
    Returns:
        Tuple of (start_palette, end_palette)
    """
    if available_palettes is None:
        available_palettes = [OCEAN_PALETTE, RAINBOW_PALETTE, SUNSET_PALETTE]
    
    if current_palette is None:
        # Start fresh - pick random palette
        start_palette = random.choice(available_palettes)
    else:
        start_palette = current_palette
    
    # Find end palette that matches start palette's end color
    start_end = start_palette[-1]
    best_match = None
    best_score = 0.0
    
    for palette in available_palettes:
        # Check first color of palette
        score = color_similarity(start_end, palette[0])
        if score > best_score:
            best_score = score
            best_match = palette
    
    if best_match and best_score >= 0.4:
        end_palette = best_match
    else:
        # No good match, pick random but ensure smooth transition
        end_palette = random.choice(available_palettes)
        end_palette = generate_smooth_transition_palette(
            start_palette, end_palette, ensure_match=True
        )[1]
    
    return start_palette, end_palette














