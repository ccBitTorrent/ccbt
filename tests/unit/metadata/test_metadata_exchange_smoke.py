from __future__ import annotations

import builtins
from typing import Any

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.metadata]


@pytest.mark.unit
def test_metadata_exchange_importable_and_functions_exist():
    """Smoke-test that metadata exchange module imports and key symbols exist.

    This does not perform network I/O; it asserts the surface is present so
    subsequent targeted tests can patch internals and drive behavior.
    """
    mod = __import__("ccbt.piece.metadata_exchange", fromlist=["*"])  # type: ignore[arg-type]

    assert hasattr(mod, "fetch_metadata_from_peers")
    fn = getattr(mod, "fetch_metadata_from_peers")
    assert callable(fn)


