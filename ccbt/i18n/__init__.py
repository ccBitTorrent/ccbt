"""Internationalization (i18n) support for ccBitTorrent.

Provides translation functions and locale management.
"""

from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path
from typing import Any

# Default locale
DEFAULT_LOCALE = "en"

# Translation instance (lazy-loaded)
_translation: gettext.NullTranslations | None = None


def get_locale() -> str:
    """Get current locale from environment or system.

    Returns:
        Locale code (e.g., 'en', 'es', 'fr')

    """
    # Check environment variable first
    env_locale = (
        os.environ.get("CCBT_LOCALE") or os.environ.get("LANG", "").split(".")[0]
    )
    if env_locale:
        return env_locale.split("_")[0]  # Extract language code

    # Fall back to system locale
    try:
        system_locale, _ = locale.getdefaultlocale()
        if system_locale:
            return system_locale.split("_")[0]
    except Exception:
        pass

    return DEFAULT_LOCALE


def set_locale(locale_code: str) -> None:
    """Set the locale for translations.

    Args:
        locale_code: Language code (e.g., 'en', 'es', 'fr')

    """
    global _translation
    _translation = None  # Reset to force reload

    # Set environment variable for persistence
    os.environ["CCBT_LOCALE"] = locale_code


def _get_translation() -> gettext.NullTranslations:
    """Get or create translation instance.

    Returns:
        Translation object

    """
    global _translation

    if _translation is None:
        locale_code = get_locale()
        locale_dir = Path(__file__).parent / "locales"

        try:
            translation = gettext.translation(
                "ccbt",
                localedir=str(locale_dir),
                languages=[locale_code],
                fallback=True,
            )
            _translation = translation
        except Exception:
            # Fallback to NullTranslations (returns original strings)
            _translation = gettext.NullTranslations()

    return _translation


def _(message: str) -> str:
    """Translate a message.

    Args:
        message: Message to translate

    Returns:
        Translated message (or original if translation not found)

    """
    return _get_translation().gettext(message)


def _n(singular: str, plural: str, n: int) -> str:
    """Translate a message with pluralization.

    Args:
        singular: Singular form
        plural: Plural form
        n: Number to determine which form to use

    Returns:
        Translated message with correct plural form

    """
    return _get_translation().ngettext(singular, plural, n)


def _p(context: str, message: str) -> str:
    """Translate a message with context.

    Args:
        context: Context prefix (e.g., 'error', 'status')
        message: Message to translate

    Returns:
        Translated message

    """
    # Use context|message format for gettext
    full_key = f"{context}|{message}"
    translation = _get_translation().gettext(full_key)

    # If no translation found, return original message
    if translation == full_key:
        return message

    return translation
