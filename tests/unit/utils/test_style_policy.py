"""Unit tests for shared style policy helpers."""

from __future__ import annotations

import pytest

from ccbt.utils import style_policy


@pytest.mark.unit
def test_markup_wraps_text_with_style() -> None:
    """Test markup() wraps text with the requested style tag."""
    assert style_policy.markup("hello", "cyan") == "[cyan]hello[/cyan]"
    assert style_policy.markup("hello", "") == "hello"


@pytest.mark.unit
def test_log_level_colors_include_trace() -> None:
    """Test log-level color mapping includes TRACE and unknown fallback."""
    assert style_policy.color_for_log_level("TRACE") == "dim"
    assert style_policy.format_log_level_label("trace") == "[dim]trace[/dim]"
    assert style_policy.color_for_log_level("mystery") == "white"


@pytest.mark.unit
def test_format_log_method_name() -> None:
    """Test method name formatting uses the shared method color."""
    assert style_policy.format_log_method_name("download_piece") == (
        "[#ff69b4]download_piece[/#ff69b4]"
    )


@pytest.mark.unit
def test_colorize_action_text_applies_known_styles() -> None:
    """Test action text highlighting follows configured patterns."""
    text = "PIECE_MESSAGE: Sent 8 REQUEST message(s) to peer."
    rendered = style_policy.colorize_action_text(text)
    assert "[bright_cyan]PIECE_MESSAGE:[/bright_cyan]" in rendered
    assert "[bright_cyan]Sent 8 REQUEST message(s)[/bright_cyan]" in rendered


@pytest.mark.unit
def test_quality_style_for_percentage_scale() -> None:
    """Test quality bucket mapping remains stable."""
    assert style_policy.quality_style_for_percentage(92) == "green"
    assert style_policy.quality_style_for_percentage(65) == "yellow"
    assert style_policy.quality_style_for_percentage(45) == "orange1"
    assert style_policy.quality_style_for_percentage(10) == "red"
