"""Internationalization (i18n) support for ccBitTorrent.

Provides translation functions and locale management.
"""

from __future__ import annotations

import gettext
import locale
import logging
import os
from pathlib import Path

# Default locale
DEFAULT_LOCALE = "en"

# Translation instance (lazy-loaded)
_translation: gettext.NullTranslations | None = None

logger = logging.getLogger(__name__)


def _is_valid_locale(locale_code: str) -> bool:
    """Check if locale code is valid and available.

    Args:
        locale_code: Locale code to validate

    Returns:
        True if locale is available, False otherwise

    """
    if not locale_code or not isinstance(locale_code, str):
        return False

    # Extract language code (e.g., 'en_US' -> 'en')
    lang_code = locale_code.split("_")[0].lower()

    # Check if locale directory exists
    locale_dir = Path(__file__).parent / "locales"
    po_file = locale_dir / lang_code / "LC_MESSAGES" / "ccbt.po"

    return po_file.exists()


def get_locale() -> str:
    """Get current locale from config, environment, or system.

    Precedence order:
    1. CCBT_UI_LOCALE environment variable (highest priority)
    2. CCBT_LOCALE environment variable
    3. LANG environment variable
    4. System locale
    5. Default locale ('en')

    Returns:
        Locale code (e.g., 'en', 'es', 'fr')

    """
    # Check environment variables (CCBT_UI_LOCALE takes precedence)
    env_locale = (
        os.environ.get("CCBT_UI_LOCALE")
        or os.environ.get("CCBT_LOCALE")
        or os.environ.get("LANG", "").split(".")[0]
    )

    if env_locale:
        locale_code = env_locale.split("_")[0].lower()
        if _is_valid_locale(locale_code):
            return locale_code
        # Log warning but continue with fallback
        logger.warning(
            f"Invalid locale '{locale_code}' from environment, falling back to system/default"
        )

    # Fall back to system locale
    try:
        system_locale, _ = locale.getdefaultlocale()
        if system_locale:
            locale_code = system_locale.split("_")[0].lower()
            if _is_valid_locale(locale_code):
                return locale_code
    except Exception:
        pass

    return DEFAULT_LOCALE


def set_locale(locale_code: str) -> None:
    """Set the locale for translations.

    Args:
        locale_code: Language code (e.g., 'en', 'es', 'fr')

    Raises:
        ValueError: If locale code is invalid or not available

    """
    global _translation

    # Normalize locale code
    if not locale_code or not isinstance(locale_code, str):
        raise ValueError(f"Invalid locale code: {locale_code}")

    locale_code = locale_code.split("_")[0].lower()

    # Validate locale availability
    if not _is_valid_locale(locale_code):
        logger.warning(
            f"Locale '{locale_code}' is not available, falling back to '{DEFAULT_LOCALE}'"
        )
        locale_code = DEFAULT_LOCALE

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

        # Validate locale before attempting to load
        if not _is_valid_locale(locale_code):
            logger.warning(
                f"Locale '{locale_code}' is not available, using fallback translations"
            )
            locale_code = DEFAULT_LOCALE

        try:
            translation = gettext.translation(
                "ccbt",
                localedir=str(locale_dir),
                languages=[locale_code],
                fallback=True,
            )
            _translation = translation
        except Exception as e:
            # Fallback to NullTranslations (returns original strings)
            logger.warning(
                f"Failed to load translations for locale '{locale_code}': {e}. "
                "Using fallback translations."
            )
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
