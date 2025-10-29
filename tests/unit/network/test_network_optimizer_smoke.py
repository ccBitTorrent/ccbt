from __future__ import annotations

import importlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.network]


def test_network_optimizer_importable_has_public_api():
    mod = importlib.import_module("ccbt.network_optimizer")
    # Basic sanity: module loads and exposes at least one attribute
    assert any(not name.startswith("_") for name in dir(mod))


