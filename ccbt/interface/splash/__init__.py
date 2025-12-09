"""Splash screen animation system for ccBitTorrent.

Provides ocean-themed ASCII animations using Rich and Textual frameworks.
"""

from __future__ import annotations

from ccbt.interface.splash.animation_helpers import (
    AnimationController,
    ColorPalette,
    FrameRenderer,
)

# Optional import for SplashScreen (may not exist)
try:
    from ccbt.interface.splash.splash_screen import SplashScreen, run_splash_screen
    from ccbt.interface.splash.splash_manager import SplashManager
    from ccbt.interface.splash.sequence_generator import SequenceGenerator, generate_random_sequence
    from ccbt.interface.splash.animation_adapter import AnimationAdapter
    from ccbt.interface.splash.message_overlay import MessageOverlay
    from ccbt.interface.splash.transitions import (
        Transition,
        ColorTransition,
        FadeTransition,
        SlideTransition,
        CrossfadeTransition,
    )
    from ccbt.interface.splash.templates import Template, TemplateRegistry, get_template, load_default_templates
except ImportError:
    SplashScreen = None  # type: ignore[assignment, misc]
    run_splash_screen = None  # type: ignore[assignment, misc]
    SplashManager = None  # type: ignore[assignment, misc]
    SequenceGenerator = None  # type: ignore[assignment, misc]
    generate_random_sequence = None  # type: ignore[assignment, misc]
    AnimationAdapter = None  # type: ignore[assignment, misc]
    MessageOverlay = None  # type: ignore[assignment, misc]
    Transition = None  # type: ignore[assignment, misc]
    ColorTransition = None  # type: ignore[assignment, misc]
    FadeTransition = None  # type: ignore[assignment, misc]
    SlideTransition = None  # type: ignore[assignment, misc]
    CrossfadeTransition = None  # type: ignore[assignment, misc]
    Template = None  # type: ignore[assignment, misc]
    TemplateRegistry = None  # type: ignore[assignment, misc]
    get_template = None  # type: ignore[assignment, misc]
    load_default_templates = None  # type: ignore[assignment, misc]

__all__ = [
    "AnimationController",
    "ColorPalette",
    "FrameRenderer",
]

if SplashScreen is not None:
    __all__.extend([
        "SplashScreen",
        "run_splash_screen",
        "SplashManager",
        "SequenceGenerator",
        "generate_random_sequence",
        "AnimationAdapter",
        "MessageOverlay",
        "Transition",
        "ColorTransition",
        "FadeTransition",
        "SlideTransition",
        "CrossfadeTransition",
        "Template",
        "TemplateRegistry",
        "get_template",
        "load_default_templates",
    ])





