"""Unified animation demo using the AnimationConfig system.

Demonstrates start, middle, and finish animations with full configuration.
"""

from __future__ import annotations

import asyncio
import sys
import os

# Handle Unicode encoding for Windows
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Import directly from splash module to avoid interface.__init__.py issues
# This works when run as: python -m ccbt.interface.splash.unified_demo
# or directly: python ccbt/interface/splash/unified_demo.py
try:
    # Try relative imports first (when run as module)
    from . import animation_config
    from . import animation_executor
    from . import animation_helpers
    from . import ascii_art
    
    AnimationConfig = animation_config.AnimationConfig
    AnimationSequence = animation_config.AnimationSequence
    BackgroundConfig = animation_config.BackgroundConfig
    HOLIDAY_PALETTE = animation_config.HOLIDAY_PALETTE
    OCEAN_PALETTE = animation_config.OCEAN_PALETTE
    RAINBOW_PALETTE = animation_config.RAINBOW_PALETTE
    SUNSET_PALETTE = animation_config.SUNSET_PALETTE
    AnimationExecutor = animation_executor.AnimationExecutor
    AnimationController = animation_helpers.AnimationController
    LOGO_1 = ascii_art.LOGO_1
    CCBT_TITLE = ascii_art.CCBT_TITLE
except (ImportError, AttributeError):
    # Fallback: import directly (when run as script)
    import sys
    from pathlib import Path
    
    splash_dir = Path(__file__).parent
    if str(splash_dir) not in sys.path:
        sys.path.insert(0, str(splash_dir))
    
    from animation_config import (
        AnimationConfig,
        AnimationSequence,
        BackgroundConfig,
        HOLIDAY_PALETTE,
        OCEAN_PALETTE,
        RAINBOW_PALETTE,
        SUNSET_PALETTE,
    )
    from animation_executor import AnimationExecutor
    from animation_helpers import AnimationController
    from ascii_art import LOGO_1, CCBT_TITLE


async def demo_sequence(sequence: AnimationSequence) -> None:
    """Run an animation sequence.
    
    Args:
        sequence: AnimationSequence to execute
    """
    executor = AnimationExecutor()
    
    for i, anim_config in enumerate(sequence.animations):
        print(f"\n[{i+1}/{len(sequence.animations)}] {anim_config.name or anim_config.style}")
        print("-" * 80)
        
        try:
            await executor.execute(anim_config)
            await asyncio.sleep(0.3)  # Brief pause between animations
        except KeyboardInterrupt:
            print(f"\nSkipped: {anim_config.name}")
            response = input("\nContinue? (y/n): ").lower()
            if response != 'y':
                return
        except Exception as e:
            print(f"\nError: {e}")
            continue


async def demo_start_middle_finish() -> None:
    """Demo: Start, Middle, Finish animation sequence."""
    print("=" * 80)
    print("Start → Middle → Finish Animation Sequence")
    print("=" * 80)
    
    sequence = AnimationSequence()
    
    # Start: Reveal from top
    sequence.add_start_animation(
        LOGO_1,
        style="reveal",
        direction="top_down",
        color_start="cyan",
        duration=2.0,
        steps=20,
    )
    
    # Middle: Rainbow left to right
    sequence.add_middle_animation(
        LOGO_1,
        style="rainbow",
        direction="left_to_right",
        color_palette=RAINBOW_PALETTE,
        duration=4.0,
        speed=8.0,
    )
    
    # Finish: Fade out
    sequence.add_finish_animation(
        LOGO_1,
        style="fade",
        direction="fade_out",
        color_start="white",
        steps=20,
    )
    
    await demo_sequence(sequence)


async def demo_rainbow_directions() -> None:
    """Demo: All rainbow directions (fixed)."""
    print("=" * 80)
    print("Rainbow Direction Animations (Fixed Directions)")
    print("=" * 80)
    
    sequence = AnimationSequence()
    
    directions = [
        ("left_to_right", "Left to Right"),
        ("right_to_left", "Right to Left"),
        ("top_to_bottom", "Top to Bottom"),
        ("bottom_to_top", "Bottom to Top"),
        ("radiant_center_out", "Radiant Center Out"),
        ("radiant_center_in", "Radiant Center In"),
    ]
    
    for direction, name in directions:
        sequence.add_animation(
            style="rainbow",
            logo_text=LOGO_1,
            direction=direction,
            color_palette=RAINBOW_PALETTE,
            duration=3.0,
            name=f"Rainbow {name}",
        )
    
    await demo_sequence(sequence)


async def demo_color_palettes() -> None:
    """Demo: Different color palettes."""
    print("=" * 80)
    print("Color Palette Animations")
    print("=" * 80)
    
    sequence = AnimationSequence()
    
    palettes = [
        (RAINBOW_PALETTE, "Rainbow"),
        (OCEAN_PALETTE, "Ocean"),
        (SUNSET_PALETTE, "Sunset"),
        (HOLIDAY_PALETTE, "Holiday"),
    ]
    
    for palette, name in palettes:
        sequence.add_animation(
            style="rainbow",
            logo_text=LOGO_1,
            direction="left_to_right",
            color_palette=palette,
            duration=3.0,
            name=f"{name} Palette",
        )
    
    await demo_sequence(sequence)


async def demo_animation_styles() -> None:
    """Demo: Different animation styles."""
    print("=" * 80)
    print("Animation Style Showcase")
    print("=" * 80)
    
    sequence = AnimationSequence()
    
    # Reveal
    sequence.add_animation(
        style="reveal",
        logo_text=LOGO_1,
        direction="radiant",
        color_start="cyan",
        duration=2.5,
        name="Reveal Radiant",
    )
    
    # Letters
    sequence.add_animation(
        style="letters",
        logo_text=LOGO_1,
        direction="top_down",
        color_start="white",
        duration=3.0,
        name="Letters Top Down",
    )
    
    # Flag
    sequence.add_animation(
        style="flag",
        logo_text=LOGO_1,
        color_palette=["blue", "white", "red"],
        duration=3.0,
        name="Flag Effect",
    )
    
    # Particles
    sequence.add_animation(
        style="particles",
        logo_text=LOGO_1,
        color_start="cyan",
        particle_density=0.1,
        duration=3.0,
        name="Particle Effect",
    )
    
    # Columns
    sequence.add_animation(
        style="columns_color",
        logo_text=LOGO_1,
        direction="left_to_right",
        color_palette=RAINBOW_PALETTE,
        duration=3.0,
        name="Column Color",
    )
    
    # Row Groups
    sequence.add_animation(
        style="row_groups_color",
        logo_text=LOGO_1,
        direction="left_to_right",
        color_palette=RAINBOW_PALETTE,
        duration=3.0,
        name="Row Groups Color",
    )
    
    await demo_sequence(sequence)


async def demo_with_backgrounds() -> None:
    """Demo: Animations with backgrounds."""
    print("=" * 80)
    print("Animations with Backgrounds")
    print("=" * 80)
    
    sequence = AnimationSequence()
    
    # Rainbow with star background
    bg_stars = BackgroundConfig(
        bg_type="stars",
        bg_color_start="dim white",
        bg_star_count=100,
        bg_animate=True,
    )
    
    sequence.add_animation(
        style="rainbow",
        logo_text=LOGO_1,
        direction="left_to_right",
        color_palette=RAINBOW_PALETTE,
        duration=4.0,
        background=bg_stars,
        name="Rainbow with Stars",
    )
    
    # Reveal with wave background
    bg_waves = BackgroundConfig(
        bg_type="waves",
        bg_color_start="blue",
        bg_wave_char="~",
        bg_wave_lines=3,
        bg_animate=True,
        bg_speed=2.0,
    )
    
    sequence.add_animation(
        style="reveal",
        logo_text=LOGO_1,
        direction="top_down",
        color_start="cyan",
        duration=3.0,
        background=bg_waves,
        name="Reveal with Waves",
    )
    
    await demo_sequence(sequence)


async def demo_complete_sequence() -> None:
    """Demo: Complete start-middle-finish sequence with transitions."""
    print("=" * 80)
    print("Complete Animation Sequence")
    print("=" * 80)
    
    sequence = AnimationSequence()
    
    # Start: Reveal from center
    sequence.add_start_animation(
        LOGO_1,
        style="reveal",
        direction="radiant",
        color_start="bright_blue",
        duration=2.0,
        transition_type="fade",
    )
    
    # Middle 1: Rainbow left to right
    sequence.add_middle_animation(
        LOGO_1,
        style="rainbow",
        direction="left_to_right",
        color_palette=RAINBOW_PALETTE,
        duration=3.0,
        transition_type="fade",
    )
    
    # Middle 2: Rainbow center out
    sequence.add_middle_animation(
        LOGO_1,
        style="rainbow",
        direction="radiant_center_out",
        color_palette=OCEAN_PALETTE,
        duration=3.0,
        transition_type="fade",
    )
    
    # Finish: Fade out slow
    sequence.add_finish_animation(
        LOGO_1,
        style="fade",
        direction="fade_out",
        color_start="white",
        steps=20,
        transition_type="none",
    )
    
    await demo_sequence(sequence)


async def main() -> None:
    """Main demo entry point."""
    demos = [
        ("1", "Start-Middle-Finish Sequence", demo_start_middle_finish),
        ("2", "Rainbow Directions (Fixed)", demo_rainbow_directions),
        ("3", "Color Palettes", demo_color_palettes),
        ("4", "Animation Styles", demo_animation_styles),
        ("5", "With Backgrounds", demo_with_backgrounds),
        ("6", "Complete Sequence", demo_complete_sequence),
    ]
    
    print("=" * 80)
    print("ccBitTorrent Unified Animation System Demo")
    print("=" * 80)
    print("\nAvailable demos:")
    for num, name, _ in demos:
        print(f"  {num}. {name}")
    print("  a. All demos")
    print("  q. Quit")
    
    choice = input("\nSelect demo: ").lower()
    
    if choice == "q":
        return
    elif choice == "a":
        for _, name, demo_func in demos:
            try:
                await demo_func()
                await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n\nDemo interrupted.")
                return
    else:
        for num, name, demo_func in demos:
            if choice == num:
                try:
                    await demo_func()
                except KeyboardInterrupt:
                    print("\n\nDemo interrupted.")
                return
        
        print(f"Unknown choice: {choice}")


def _main() -> None:
    """Entry point that can be called directly."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)


if __name__ == "__main__":
    _main()

