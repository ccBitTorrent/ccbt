"""Comprehensive animation demo script.

This script demonstrates all available animation types in the splash screen system.
Run this to test and preview animations before using them in the CLI/interface.
"""

from __future__ import annotations

import asyncio
import sys
import os

# Handle Unicode encoding for Windows
if os.name == 'nt':  # Windows
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from ccbt.interface.splash.animation_helpers import AnimationController
from ccbt.interface.splash.animations import AnimationSegments
from ccbt.interface.splash.ascii_art import LOGO_1, CCBT_TITLE


async def run_animation_demo() -> None:
    """Run comprehensive animation demo."""
    print("=" * 80)
    print("ccBitTorrent Animation System Demo")
    print("=" * 80)
    print("\nThis demo showcases all available animation types.")
    print("Each animation will run for a few seconds.")
    print("Press Ctrl+C to skip to next animation or exit.\n")

    controller = AnimationController()
    animations = AnimationSegments(controller)

    demo_animations = [
        # Rainbow animations
        ("Rainbow Left to Right", lambda: animations.logo_1_rainbow_left()),
        ("Rainbow Right to Left", lambda: animations.logo_1_rainbow_right()),
        ("Rainbow Radiant (Center Out)", lambda: animations.logo_1_rainbow_radiant()),
        ("Rainbow Top to Bottom", lambda: animations.rainbow_top_to_bottom(LOGO_1, 4.0)),
        ("Rainbow Bottom to Top", lambda: animations.rainbow_bottom_to_top(LOGO_1, 4.0)),

        # Reveal animations
        ("Reveal Top Down", lambda: animations.logo_1_reveal_top_down()),
        ("Reveal Down Up", lambda: animations.reveal_down_up(LOGO_1, "cyan", 3.0)),
        ("Reveal Left Right", lambda: animations.reveal_left_right(LOGO_1, "green", 3.0)),
        ("Reveal Right Left", lambda: animations.reveal_right_left(LOGO_1, "blue", 3.0)),
        ("Reveal Radiant", lambda: animations.logo_1_reveal_radiant()),

        # Letter-by-letter animations
        ("Letters Top Down", lambda: animations.logo_1_letters_top_down()),
        ("Letters Down Up", lambda: animations.letters_down_up(LOGO_1, "white", 4.0)),
        ("Letters Left Right", lambda: animations.letters_left_right(LOGO_1, "cyan", 4.0)),
        ("Letters Right Left", lambda: animations.letters_right_left(LOGO_1, "yellow", 4.0)),

        # Special effects
        ("Flag Effect", lambda: animations.logo_1_flag_effect()),
        ("Particle Effects", lambda: animations.logo_1_particles()),
        ("Glitch Effect", lambda: animations.logo_1_glitch()),

        # Fade animations
        ("Fade In Slow", lambda: animations.fade_in_slow(CCBT_TITLE, "cyan")),
        ("Fade Out Slow", lambda: animations.fade_out_slow(CCBT_TITLE, "cyan")),
        ("Fade In/Out", lambda: animations.fade_in_out(CCBT_TITLE, "blue", 1.0)),

        # Custom color animations
        ("Custom Ocean Colors", lambda: animations.custom_color_animation(
            LOGO_1,
            ["bright_blue", "cyan", "deep_sky_blue1", "blue", "turquoise"],
            direction="left",
            duration=4.0,
        )),
        ("Custom Sunset Colors", lambda: animations.custom_color_animation(
            LOGO_1,
            ["red", "orange_red1", "dark_orange", "orange1", "yellow"],
            direction="radiant",
            duration=4.0,
        )),
        ("Custom Holiday Colors", lambda: animations.custom_color_animation(
            LOGO_1,
            ["bright_red", "bright_green", "bright_blue", "yellow"],
            direction="top",
            duration=4.0,
        )),
    ]

    print(f"Total animations: {len(demo_animations)}\n")
    print("Starting demo in 2 seconds...\n")
    await asyncio.sleep(2)

    for idx, (name, anim_func) in enumerate(demo_animations, 1):
        try:
            print(f"\n[{idx}/{len(demo_animations)}] {name}")
            print("-" * 80)
            await anim_func()
            await asyncio.sleep(0.5)  # Brief pause between animations
        except KeyboardInterrupt:
            print(f"\n\nSkipped: {name}")
            response = input("\nContinue with next animation? (y/n): ").lower()
            if response != 'y':
                print("\nDemo cancelled by user.")
                return
        except Exception as e:
            print(f"\nError in {name}: {e}")
            continue

    print("\n" + "=" * 80)
    print("Animation demo completed!")
    print("=" * 80)


async def run_single_animation(animation_name: str) -> None:
    """Run a single animation by name.
    
    Args:
        animation_name: Name of animation to run
    """
    controller = AnimationController()
    animations = AnimationSegments(controller)

    # Map animation names to functions
    animation_map = {
        "rainbow_left": lambda: animations.logo_1_rainbow_left(),
        "rainbow_right": lambda: animations.logo_1_rainbow_right(),
        "rainbow_radiant": lambda: animations.logo_1_rainbow_radiant(),
        "reveal_top": lambda: animations.logo_1_reveal_top_down(),
        "reveal_radiant": lambda: animations.logo_1_reveal_radiant(),
        "letters_top": lambda: animations.logo_1_letters_top_down(),
        "flag": lambda: animations.logo_1_flag_effect(),
        "particles": lambda: animations.logo_1_particles(),
        "glitch": lambda: animations.logo_1_glitch(),
    }

    if animation_name in animation_map:
        await animation_map[animation_name]()
    else:
        print(f"Unknown animation: {animation_name}")
        print(f"Available: {', '.join(animation_map.keys())}")


def list_animations() -> None:
    """List all available animations."""
    print("Available Animations:")
    print("=" * 80)
    print("\nRainbow Animations:")
    print("  - rainbow_left: Rainbow left to right")
    print("  - rainbow_right: Rainbow right to left")
    print("  - rainbow_radiant: Rainbow radiating from center")
    print("\nReveal Animations:")
    print("  - reveal_top: Reveal top to bottom")
    print("  - reveal_radiant: Reveal from center")
    print("\nLetter Animations:")
    print("  - letters_top: Letters appearing top to bottom")
    print("\nSpecial Effects:")
    print("  - flag: Flag/wave effect")
    print("  - particles: Particle effects")
    print("  - glitch: Glitch effect")
    print("\nUsage:")
    print("  python -m ccbt.interface.splash.animation_demo [animation_name]")
    print("  python -m ccbt.interface.splash.animation_demo  # Run full demo")


async def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ["-h", "--help", "help", "list"]:
            list_animations()
        else:
            await run_single_animation(arg)
    else:
        await run_animation_demo()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)


