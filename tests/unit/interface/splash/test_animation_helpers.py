"""Tests for splash animation helper math."""

from __future__ import annotations

import pytest

from ccbt.interface.splash.animation_helpers import AnimationController


@pytest.fixture
def controller() -> AnimationController:
    """Create a controller instance for tests."""
    return AnimationController()


def test_left_right_reveal_reaches_final_column(controller: AnimationController) -> None:
    """Ensure left-to-right reveal eventually uncovers the last column."""
    assert not controller._should_reveal_position("left_right", 0.0, 9, 0, 10, 4)
    assert controller._should_reveal_position("left_right", 0.99, 9, 0, 10, 4)


def test_radiant_center_out_reveal_grows_outwards(controller: AnimationController) -> None:
    """Radiant center-out reveal should cover outer points as progress approaches 1."""
    assert not controller._should_reveal_position("radiant_center_out", 0.1, 0, 0, 20, 8)
    assert controller._should_reveal_position("radiant_center_out", 1.0, 0, 0, 20, 8)


def test_radiant_center_in_reveals_edges_first(controller: AnimationController) -> None:
    """Radiant center-in reveal should expose edges early and center later."""
    edge_visible = controller._should_reveal_position("radiant_center_in", 0.05, 0, 0, 20, 8)
    center_visible = controller._should_reveal_position("radiant_center_in", 0.05, 10, 4, 20, 8)
    assert edge_visible
    assert not center_visible
    # Once progress completes, center should be visible
    assert controller._should_reveal_position("radiant_center_in", 1.0, 10, 4, 20, 8)


























