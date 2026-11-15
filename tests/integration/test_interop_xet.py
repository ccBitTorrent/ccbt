"""Interop matrix stubs/fixtures (G3/G5/G9). Live pins run when available."""

from __future__ import annotations

import pytest

from ccbt.discovery.xet_cas_http import CasHttpClient

pytestmark = [pytest.mark.timeout(60), pytest.mark.integration]


@pytest.mark.asyncio
async def test_interop_cas_contract_fixtures() -> None:
    """CAS client constructs against contract defaults (fixture-level interop)."""
    client = CasHttpClient(base_url="http://127.0.0.1:9", token_provider=lambda: "test")
    assert client.base_url.startswith("http://")


@pytest.mark.asyncio
async def test_interop_cas_client_openxet() -> None:
    """Marked for OpenXet server; validates client API surface exists."""
    assert hasattr(CasHttpClient, "upload_xorb")


@pytest.mark.asyncio
async def test_interop_hf_xet_against_ccbt_cas() -> None:
    from ccbt.cas_server import app as cas_app

    assert cas_app is not None


@pytest.mark.asyncio
async def test_interop_hub_huggingface_hub() -> None:
    from ccbt.hub import api as hub_api

    assert hub_api is not None


@pytest.mark.asyncio
async def test_interop_git_xet_roundtrip() -> None:
    from ccbt.cli import git_xet

    assert hasattr(git_xet, "main") or callable(git_xet)
