"""Shared color template definitions for splash animations."""

from __future__ import annotations

from ccbt.interface.splash.animation_config import (
    OCEAN_PALETTE,
    RAINBOW_PALETTE,
    SUNSET_PALETTE,
)

COLOR_TEMPLATES: dict[str, list[str]] = {
    "rainbow": list(RAINBOW_PALETTE),
    "ocean": list(OCEAN_PALETTE),
    "sunset": list(SUNSET_PALETTE),
    "meadow_bloom": [
        "medium_spring_green",
        "spring_green2",
        "light_green",
        "medium_purple2",
        "orchid1",
        "deep_pink2",
        "gold1",
    ],
    "neon_pulse": [
        "medium_purple1",
        "deep_pink2",
        "hot_pink",
        "deep_sky_blue1",
        "cyan",
    ],
    "cosmic_depth": [
        "blue",
        "royal_blue1",
        "medium_purple4",
        "magenta",
        "orange1",
    ],
    "aurora_glass": [
        "aquamarine1",
        "cyan",
        "spring_green2",
        "light_slate_blue",
        "white",
    ],
    "infra_glow": [
        "dark_magenta",
        "magenta",
        "orange_red1",
        "gold1",
        "light_salmon1",
    ],
    "retro_wave": [
        "deep_pink3",
        "violet",
        "medium_slate_blue",
        "turquoise2",
        "cyan",
    ],
    "quantum_frost": [
        "deep_sky_blue1",
        "cyan",
        "white",
        "aquamarine1",
        "light_cyan1",
    ],
}


def get_color_template(name: str) -> list[str] | None:
    """Return a copy of a registered color template."""
    palette = COLOR_TEMPLATES.get(name)
    if palette is None:
        return None
    return list(palette)



