"""Allowlist encryption roundtrip (C14)."""

from __future__ import annotations

import pytest

from ccbt.security.xet_allowlist import XetAllowlist

pytestmark = [pytest.mark.timeout(15), pytest.mark.security]


@pytest.mark.asyncio
async def test_xet_allowlist_encrypted_roundtrip(tmp_path) -> None:
    path = tmp_path / "allowlist.bin"
    key = b"\x42" * 32
    al = XetAllowlist(allowlist_path=path, encryption_key=key)
    await al.load()
    al.add_peer("peer1", b"\x01" * 32)
    await al.save()
    assert path.exists()
    al2 = XetAllowlist(allowlist_path=path, encryption_key=key)
    await al2.load()
    assert al2.is_allowed("peer1")
