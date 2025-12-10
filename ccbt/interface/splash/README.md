# Splash Screen Animation System

Ocean-themed ASCII animation splash screen for ccBitTorrent using Rich and Textual frameworks.

## Overview

This module provides a **stunning rainbow logo animation system** that displays **iridescent ASCII art** with colors moving from left to right. The animations feature only the finest professional-quality ASCII art:

- 🌈 **Rainbow Logo Animations**: Two logos with 22-color iridescent effects
- 🎨 **Moving Color Gradients**: Colors shift continuously creating mesmerizing visuals
- ⭐ **Professional ASCII Art**: High-quality logos from asciiart.website collections
- ⚡ **Smooth Animations**: 0.1 second intervals for fluid rainbow motion

## Architecture

### Module Structure

```
ccbt/interface/splash/
├── __init__.py              # Module exports
├── animation_helpers.py      # Core animation utilities
├── ascii_art.py             # ASCII art assets
├── animations.py            # Animation segment implementations
├── splash_screen.py         # Textual-based splash screen
└── README.md                # This file
```

### Components

#### 1. Animation Helpers (`animation_helpers.py`)

- **ColorPalette**: Ocean-themed color constants
- **FrameRenderer**: Renders ASCII art with Rich styling
- **AnimationController**: Controls timing and frame sequencing

#### 2. ASCII Art Assets (`ascii_art.py`)

**Only Professional-Quality ASCII Art** - All assets sourced from asciiart.website collections:

### Ship Collection (High-Quality Professional Art)
- `ROW_BOAT` - Detailed row boat with realistic water effects, wake patterns, and proportions
- `NAUTICAL_SHIP` - Beautiful sailing ship with intricate rigging, multiple masts, and hull detail
- `SAILING_SHIP_TRINIDAD` - Magellan's Trinidad with historical accuracy and complex ship structure

### Title Variations (Clean ASCII Characters)
- `CCBT_TITLE_BLOCK` - Standard ASCII characters for maximum compatibility
- `CCBT_TITLE_PIPE` - Pipe characters for visual variety
- `CCBT_TITLE_SLASH` - Forward slash pattern
- `CCBT_TITLE_DASH` - Dash character styling
- `CCBT_TITLE_BACKSLASH` - Backslash character styling

### Quality Standards
- ✅ **No Unicode characters** - Ensures compatibility across all terminals
- ✅ **Professional artwork** - Sourced from established ASCII art collections
- ✅ **Consistent proportions** - Proper aspect ratios and visual balance
- ✅ **Detailed craftsmanship** - Fine attention to artistic detail

### Color Animation Guide

#### Title Animations
- **Block characters (█)**: Ocean blue gradients (bright_blue → blue → cyan)
- **Letters**: Cycle through oceanic color schemes
- **Punctuation**: Highlight with bright tropical colors

#### Ship Animations
- **Water/Waves (~~~, `, -, .)**: Animated blue/cyan color gradients
- **Ship hulls**: Deep blue/navy with shadow effects
- **Sails and rigging**: White/bright_white with subtle motion
- **Details and accents**: Gold highlights for special elements
- **Water wake**: Animated trailing effects behind boats

#### Pirate Animations
- **Skulls (💀 ☠️)**: Bone white with red eye highlights
- **Hats and flags**: Black with gold trim and animation
- **Crossbones**: White with gray shadows
- **Treasure elements**: Gold with sparkle effects

#### Island/Beach Animations
- **Sand and beaches**: Yellow/beige gradient tones
- **Palm trees**: Bright green fronds, brown trunks
- **Ocean water**: Blue gradient from shallow to deep
- **Sun**: Yellow/orange with ray effects
- **Mountains**: Gray/blue silhouette tones

#### Wave Animations
- **Wave characters (~~~)**: Animated blue-to-white gradients
- **Foam and spray**: Bright white with motion blur
- **Depth effects**: Darker blues for deeper water levels

#### 3. Rainbow Logo Animations (`animations.py`)

**Iridescent rainbow animations** using only professional-quality ASCII art:
- `rainbow_logo_animation()` - Core rainbow effect with moving colors (configurable duration)
- `logo_1_rainbow()` - ccBitTorrent logo with iridescent rainbow colors (5s)
- `logo_2_rainbow()` - Alternative logo with moving rainbow spectrum (5s)

**Rainbow Effect Features:**
- **22 Colors**: Full spectrum from red through violet
- **Moving Gradient**: Colors shift continuously from left to right
- **Smooth Animation**: 0.1 second intervals for fluid motion
- **Rich Markup**: Uses Rich library for proper color rendering

**Total sequence duration**: ~5 seconds per loop (can be looped ~12 times to reach 1 minute)

#### 4. Splash Screen (`splash_screen.py`)

- **SplashScreen**: Textual-based full-screen splash screen
- **TextualFrameRenderer**: Renders frames to Textual widgets
- **run_splash_console()**: Standalone Rich Console version

## Usage

### Textual Integration

```python
from ccbt.interface.splash import SplashScreen

# In your Textual app
await app.push_screen(SplashScreen(duration=120.0, loop=False))
```

### Rich Console (Standalone)

```python
from ccbt.interface.splash.splash_screen import run_splash_console
import asyncio

# Run splash screen
asyncio.run(run_splash_console(duration=120.0, loop=False))
```

### Custom Animation Sequence

```python
from ccbt.interface.splash import AnimationController, AnimationSegments
from rich.console import Console

console = Console()
renderer = FrameRenderer(console)
controller = AnimationController(renderer)
segments = AnimationSegments(controller)

# Run specific animations
await segments.pirate_hat_animation()
await segments.surfing_animation()
await segments.beach_animation()
```

## Animation Sequence

The default sequence (`ANIMATION_SEQUENCE`) includes:

1. Title fade-in (3s)
2. Pirate hat animation (4s)
3. Sailboat animation (4s)
4. Ship of the line (3s)
5. Battleship (3s)
6. Island animation (5s)
7. Surfing animation (4s)
8. Pirate bay (4s)
9. Cove (3s)
10. Beach scene (4s)
11. Holiday beach (4s)
12. Waves (3s)
13. Title fade-out (2s)

**Total**: ~44 seconds per loop

To reach 2 minutes, the sequence loops approximately 2-3 times.

## Color Palette

The `ColorPalette` class provides ocean-themed colors:

- **Ocean**: `OCEAN_BLUE`, `DEEP_BLUE`, `TURQUOISE`, `WAVE_WHITE`
- **Tropical**: `SUNSET_ORANGE`, `SUNSET_YELLOW`, `TROPICAL_GREEN`, `PALM_GREEN`
- **Pirate**: `PIRATE_BLACK`, `GOLD`, `SILVER`, `BONE_WHITE`
- **Beach**: `SAND`, `BEACH_TAN`, `CORAL`, `SHELL_PINK`
- **Holiday**: `HOLIDAY_RED`, `HOLIDAY_GREEN`, `HOLIDAY_BLUE`, `HOLIDAY_GOLD`

## Controls

When using `SplashScreen`:

- **Escape** or **Space**: Skip splash screen
- **Q**: Quit application

## Banner Dimensions

Animations are designed for full terminal width with:
- Standard height: ~15-20 lines
- Full-width banner fill
- Centered alignment
- Colorful styling with Rich markup

## Extending Animations

To add new animation segments:

1. Add ASCII art to `ascii_art.py`
2. Create animation method in `AnimationSegments` class
3. Add to `ANIMATION_SEQUENCE` in `animations.py`

Example:

```python
# In ascii_art.py
NEW_ANIMATION_FRAMES = [
    """
    Your ASCII art here
    """,
]

# In animations.py
async def new_animation(self) -> None:
    """New animation (3 seconds)."""
    await self.controller.play_frames(
        NEW_ANIMATION_FRAMES * 2,
        frame_duration=0.3,
        color=self.colors.OCEAN_BLUE,
    )

# Add to sequence
ANIMATION_SEQUENCE.append(("new_animation", 3.0))
```

## Dependencies

- **Rich**: For console rendering and styling
- **Textual**: For full-screen splash screen (optional)

## Testing

The splash screen can be tested independently:

```bash
python -m ccbt.interface.splash.splash_screen
```

Or integrated into the main application for startup animations.

## Performance

- Frame duration: ~0.15 seconds (configurable)
- Smooth 60 FPS equivalent for terminal animations
- Efficient frame rendering with Rich
- Async/await for non-blocking animations

## Future Enhancements

- [ ] Add sound effects (optional)
- [ ] Interactive elements
- [ ] Progress indicators
- [ ] Customizable themes
- [ ] More animation segments
- [ ] Particle effects
- [ ] Transition effects between segments


