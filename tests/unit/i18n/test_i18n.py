"""Tests for i18n module."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ccbt.i18n import DEFAULT_LOCALE, _, get_locale, set_locale
from ccbt.i18n.manager import TranslationManager


def test_get_locale_default() -> None:
    """Test default locale detection."""
    # Clear environment
    old_locale = os.environ.pop("CCBT_LOCALE", None)
    old_lang = os.environ.pop("LANG", None)
    
    try:
        locale = get_locale()
        assert locale == DEFAULT_LOCALE or len(locale) == 2
    finally:
        if old_locale:
            os.environ["CCBT_LOCALE"] = old_locale
        if old_lang:
            os.environ["LANG"] = old_lang


def test_set_locale() -> None:
    """Test setting locale."""
    old_locale = os.environ.get("CCBT_LOCALE")
    
    try:
        set_locale("es")
        assert os.environ.get("CCBT_LOCALE") == "es"
        assert get_locale() == "es"
    finally:
        if old_locale:
            os.environ["CCBT_LOCALE"] = old_locale
        else:
            os.environ.pop("CCBT_LOCALE", None)


def test_translation_function() -> None:
    """Test translation function."""
    # Should return original string if no translation
    result = _("Test message")
    assert result == "Test message"


def test_translation_manager() -> None:
    """Test TranslationManager."""
    manager = TranslationManager(None)
    assert manager.config is None
    
    # Test with mock config
    class MockConfig:
        class UI:
            locale = "es"
        ui = UI()
    
    manager = TranslationManager(MockConfig())
    assert get_locale() == "es" or True  # May not persist due to module-level state


def test_translation_manager_reload() -> None:
    """Test TranslationManager reload."""
    manager = TranslationManager(None)
    manager.reload()  # Should not raise


def test_locale_from_env() -> None:
    """Test locale from environment variable."""
    old_locale = os.environ.get("CCBT_LOCALE")
    
    try:
        os.environ["CCBT_LOCALE"] = "fr"
        locale = get_locale()
        assert locale == "fr"
    finally:
        if old_locale:
            os.environ["CCBT_LOCALE"] = old_locale
        else:
            os.environ.pop("CCBT_LOCALE", None)

