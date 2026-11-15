"""SSRF gate for remote .tonic fetch."""

from __future__ import annotations

import pytest

from ccbt.utils.ssrf import assert_safe_remote_url, is_public_url


def test_ssrf_blocks_localhost() -> None:
    assert not is_public_url("http://127.0.0.1/x.tonic")
    assert not is_public_url("http://localhost/x.tonic")
    with pytest.raises(RuntimeError):
        assert_safe_remote_url("http://[::1]/file.tonic")
