"""Tests for optional .env loading (CCBT_LOAD_DOTENV)."""

from __future__ import annotations

import os

import pytest

from ccbt.config.env_bootstrap import load_dotenv_file, maybe_load_dotenv_from_env


@pytest.mark.unit
def test_load_dotenv_file_sets_unset_keys_only(tmp_path) -> None:
    """load_dotenv_file imports keys that are not already in os.environ."""
    p = tmp_path / ".env"
    p.write_text(
        "CCBT_ENABLE_ENCRYPTION=true\n"
        "# comment\n"
        "CCBT_FOO=bar\n"
        'CCBT_QUOTED="baz"\n',
        encoding="utf-8",
    )
    prior = os.environ.get("CCBT_ENABLE_ENCRYPTION")
    expected_set_count = 3
    try:
        os.environ.pop("CCBT_ENABLE_ENCRYPTION", None)
        n = load_dotenv_file(p)
        assert n == expected_set_count
        assert os.environ["CCBT_ENABLE_ENCRYPTION"] == "true"
        assert os.environ["CCBT_FOO"] == "bar"
        assert os.environ["CCBT_QUOTED"] == "baz"
    finally:
        for k in ("CCBT_ENABLE_ENCRYPTION", "CCBT_FOO", "CCBT_QUOTED"):
            os.environ.pop(k, None)
        if prior is not None:
            os.environ["CCBT_ENABLE_ENCRYPTION"] = prior


@pytest.mark.unit
def test_load_dotenv_does_not_override_existing(tmp_path) -> None:
    """Existing process env wins over .env file values."""
    p = tmp_path / ".env"
    p.write_text("CCBT_ENABLE_ENCRYPTION=false\n", encoding="utf-8")
    try:
        os.environ["CCBT_ENABLE_ENCRYPTION"] = "true"
        n = load_dotenv_file(p)
        assert n == 0
        assert os.environ["CCBT_ENABLE_ENCRYPTION"] == "true"
    finally:
        os.environ.pop("CCBT_ENABLE_ENCRYPTION", None)


@pytest.mark.unit
def test_maybe_load_dotenv_from_env_respects_flag(tmp_path, monkeypatch) -> None:
    """maybe_load_dotenv_from_env is a no-op unless CCBT_LOAD_DOTENV is truthy."""
    p = tmp_path / ".env"
    p.write_text("CCBT_ENABLE_ENCRYPTION=true\n", encoding="utf-8")
    monkeypatch.delenv("CCBT_ENABLE_ENCRYPTION", raising=False)
    monkeypatch.delenv("CCBT_LOAD_DOTENV", raising=False)
    monkeypatch.delenv("CCBT_DOTENV_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    maybe_load_dotenv_from_env()
    assert "CCBT_ENABLE_ENCRYPTION" not in os.environ

    monkeypatch.setenv("CCBT_LOAD_DOTENV", "1")
    maybe_load_dotenv_from_env()
    assert os.environ.get("CCBT_ENABLE_ENCRYPTION") == "true"
    os.environ.pop("CCBT_ENABLE_ENCRYPTION", None)


@pytest.mark.unit
def test_load_dotenv_strips_inline_comments_env_example_style(tmp_path) -> None:
    """``KEY=value  # doc`` must not put the comment into os.environ (matches env.example)."""
    p = tmp_path / ".env"
    p.write_text(
        "CCBT_BLOCK_SIZE_KIB=64  # Block size in KiB (1-64)\n"
        "CCBT_CIRCUIT_BREAKER_ENABLED=true  # Enable circuit breaker\n"
        'CCBT_QUOTED="yes"  # trailing comment\n'
        "CCBT_URL=http://h#frag  # fragment is not `` # ``\n"
        "CCBT_EMPTY=  # only comment\n",
        encoding="utf-8",
    )
    keys = (
        "CCBT_BLOCK_SIZE_KIB",
        "CCBT_CIRCUIT_BREAKER_ENABLED",
        "CCBT_QUOTED",
        "CCBT_URL",
        "CCBT_EMPTY",
    )
    try:
        for k in keys:
            os.environ.pop(k, None)
        n = load_dotenv_file(p)
        assert n == len(keys)
        assert os.environ["CCBT_BLOCK_SIZE_KIB"] == "64"
        assert os.environ["CCBT_CIRCUIT_BREAKER_ENABLED"] == "true"
        assert os.environ["CCBT_QUOTED"] == "yes"
        assert os.environ["CCBT_URL"] == "http://h#frag"
        assert os.environ["CCBT_EMPTY"] == ""
    finally:
        for k in keys:
            os.environ.pop(k, None)
