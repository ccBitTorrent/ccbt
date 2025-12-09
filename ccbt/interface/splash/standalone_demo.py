"""
Standalone splash screen demo - no dependencies on main ccbt package.
"""

import asyncio
import sys
import os

# Handle Unicode encoding for Windows
if os.name == 'nt':  # Windows
    try:
        # Try to set console to UTF-8
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass  # Fallback to default encoding

# Add the splash module to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from animations import AnimationSegments
from animation_helpers import AnimationController
from ascii_art.logo_1 import LOGO_1
from rich.align import Align
from rich.console import Group
from rich.live import Live
from rich.text import Text


async def custom_rainbow_animation(controller: AnimationController, logo_text: str, duration: float = 5.0) -> None:
    """Custom rainbow animation without normalization/corrections that interfere with alignment."""

    # Rainbow colors for Rich styling
    rainbow_styles = [
        "red", "red dim", "red", "orange_red1", "dark_orange", "orange1", "yellow", "yellow dim",
        "chartreuse1", "green", "green dim", "spring_green1", "cyan", "cyan dim",
        "deep_sky_blue1", "blue", "blue dim", "blue_violet", "purple", "purple dim",
        "magenta", "magenta dim", "hot_pink",
    ]

    # Split into lines and keep original alignment
    lines = []
    for line in logo_text.split('\n'):
        if line.strip():  # Keep lines that have any content
            lines.append(line.rstrip())  # Only strip trailing whitespace

    num_colors = len(rainbow_styles)
    start_time = asyncio.get_event_loop().time()
    end_time = start_time + duration

    # Create a Live display for smooth in-place animation
    with Live(console=controller.renderer.console, refresh_per_second=12, transient=False) as live:
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
                        color_index = (i + time_offset) % num_colors
                        style = rainbow_styles[color_index]
                        text_line.append(char, style=style)
                logo_lines.append(text_line)

            # Center the entire logo block
            centered_logo = Align.center(Group(*logo_lines))
            live.update(centered_logo)

            await asyncio.sleep(0.083)  # ~12 FPS for smooth animation


async def main() -> None:
    """Run standalone rainbow logo demo."""
    print("Starting standalone rainbow logo demo...")
    print("Showing LOGO_1 with iridescent rainbow effects (custom alignment adjustments)")
    print("Press Ctrl+C to exit early\n")

    # Create animation controller
    controller = AnimationController()

    # Modify LOGO_1 alignment adjustments
    logo_lines = LOGO_1.split('\n')

    # Apply row-specific alignment adjustments
    for i, line in enumerate(logo_lines):
        if i == 0:
            # First row: move 2 spaces left (remove 2 leading spaces)
            logo_lines[i] = line[2:] if len(line) >= 2 else line
        elif i == 1:
            # Second row: move 2 spaces left (remove 2 leading spaces)
            logo_lines[i] = line[2:] if len(line) >= 2 else line
        elif i == 4:
            # Fifth row: move 2 spaces left (remove 2 leading spaces)
            logo_lines[i] = line[2:] if len(line) >= 2 else line

    modified_logo = '\n'.join(logo_lines)

    # Run the custom rainbow animation with modified logo (no interfering normalization)
    await custom_rainbow_animation(controller, modified_logo, 5.0)

    print("\nStandalone demo completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)
