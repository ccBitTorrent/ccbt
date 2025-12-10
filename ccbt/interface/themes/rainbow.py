"""Rainbow theme for Textual interface.

Provides a vibrant rainbow theme with sequential border colors.
"""

from __future__ import annotations

from typing import Any

try:
    from textual.theme import Theme
except ImportError:
    # Fallback for when textual is not available
    class Theme:  # type: ignore[no-redef, misc]
        """Fallback Theme class when textual is not available."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize theme (stub)."""
            pass


# Rainbow color palette (ROYGBIV)
RAINBOW_COLORS = {
    "red": "#FF0000",
    "orange": "#FF7F00",
    "yellow": "#FFFF00",
    "green": "#00FF00",
    "blue": "#0000FF",
    "indigo": "#4B0082",
    "violet": "#8B00FF",
}

# Rainbow color sequence for borders
RAINBOW_SEQUENCE = [
    RAINBOW_COLORS["red"],      # rainbow-1
    RAINBOW_COLORS["orange"],   # rainbow-2
    RAINBOW_COLORS["yellow"],   # rainbow-3
    RAINBOW_COLORS["green"],     # rainbow-4
    RAINBOW_COLORS["blue"],      # rainbow-5
    RAINBOW_COLORS["indigo"],    # rainbow-6
    RAINBOW_COLORS["violet"],     # rainbow-7
]


def create_rainbow_theme() -> Theme:
    """Create a rainbow theme with sequential border colors.
    
    Returns:
        Theme object configured with rainbow colors
    """
    # Build colors dictionary for Theme
    # Map semantic colors to rainbow colors
    colors: dict[str, str] = {
        # Semantic color mappings
        "primary": RAINBOW_COLORS["red"],
        "secondary": RAINBOW_COLORS["orange"],
        "accent": RAINBOW_COLORS["yellow"],
        "success": RAINBOW_COLORS["green"],
        "warning": RAINBOW_COLORS["blue"],
        "error": RAINBOW_COLORS["indigo"],
        "info": RAINBOW_COLORS["violet"],
        # Background colors
        "background": "#000000",  # Very dark background
        "surface": "#1A1A1A",      # Dark gray surface
        "panel": "#2A2A2A",        # Slightly lighter panel
        "surface-darken-1": "#0F0F0F",  # Even darker surface
        "surface-darken-2": "#050505",  # Darkest surface
        # Text colors for readability
        "text": "#E0E0E0",         # Light gray text
        "text-primary": "#FFFFFF", # White primary text
        "text-secondary": "#C0C0C0",  # Light gray secondary text
        "text-muted": "#808080",   # Muted text
        # Add rainbow sequence variables for borders
        # Note: Textual may not support custom variables directly,
        # but we'll add them in case they're supported
        "rainbow-1": RAINBOW_SEQUENCE[0],  # Red
        "rainbow-2": RAINBOW_SEQUENCE[1],  # Orange
        "rainbow-3": RAINBOW_SEQUENCE[2],  # Yellow
        "rainbow-4": RAINBOW_SEQUENCE[3],  # Green
        "rainbow-5": RAINBOW_SEQUENCE[4],  # Blue
        "rainbow-6": RAINBOW_SEQUENCE[5],  # Indigo
        "rainbow-7": RAINBOW_SEQUENCE[6],  # Violet
    }
    
    return Theme(
        name="rainbow",
        dark=True,
        **colors,
    )


def apply_rainbow_border_class(widget: Any, index: int) -> Any:
    """Apply rainbow border class to a widget based on its index.
    
    Args:
        widget: Textual widget to apply class to
        index: Widget index/position in sequence
        
    Returns:
        Widget with rainbow border class applied
    """
    if not hasattr(widget, "add_class"):
        return widget
    
    # Calculate which rainbow color to use (0-6, cycling)
    color_index = index % 7
    rainbow_class = f"rainbow-{color_index + 1}"
    
    # Remove any existing rainbow classes
    for i in range(1, 8):
        existing_class = f"rainbow-{i}"
        if hasattr(widget, "remove_class"):
            try:
                widget.remove_class(existing_class)  # type: ignore[attr-defined]
            except Exception:
                pass
    
    # Add the appropriate rainbow class
    try:
        widget.add_class(rainbow_class)  # type: ignore[attr-defined]
    except Exception:
        pass
    
    return widget


def get_rainbow_color(index: int) -> str:
    """Get rainbow color for a given index.
    
    Args:
        index: Color index (0-6, will be modulo'd)
        
    Returns:
        Hex color string
    """
    return RAINBOW_SEQUENCE[index % 7]





