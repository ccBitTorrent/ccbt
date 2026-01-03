"""Translation manager with configuration integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ccbt.i18n import _is_valid_locale, get_locale, set_locale

logger = logging.getLogger(__name__)


class TranslationManager:
    """Manages translations with config integration."""

    def __init__(self, config: Optional[Any] = None) -> None:
        """Initialize translation manager.

        Args:
            config: Optional config to read locale from

        """
        self.config = config
        self._initialize_locale()

    def _initialize_locale(self) -> None:
        """Initialize locale from config or environment.

        Precedence order:
        1. Config file (config.ui.locale)
        2. Environment variables (CCBT_UI_LOCALE, CCBT_LOCALE)
        3. System locale
        4. Default locale ('en')

        """
        locale_code = None

        # Try to get locale from config first
        if (
            self.config
            and hasattr(self.config, "ui")
            and hasattr(self.config.ui, "locale")
        ):
            locale_code = self.config.ui.locale
            if locale_code:
                # Validate locale from config
                if _is_valid_locale(locale_code):
                    try:
                        set_locale(locale_code)
                        logger.debug("Locale set from config: %s", locale_code)
                        return
                    except ValueError as e:
                        logger.warning(
                            "Invalid locale '%s' in config: %s. Falling back to environment/system locale.",
                            locale_code,
                            e,
                        )
                else:
                    logger.warning(
                        "Locale '%s' from config is not available. Falling back to environment/system locale.",
                        locale_code,
                    )

        # Fall back to environment/system locale
        # get_locale() will handle the fallback chain
        final_locale = get_locale()
        logger.debug("Using locale: %s", final_locale)

    def reload(self) -> None:
        """Reload translations from current locale.

        This method resets the translation cache and forces
        a reload of translations on the next translation call.
        """
        # Reset translation cache by calling set_locale with current locale
        # This ensures the cache is cleared and reloaded on next use
        current_locale = get_locale()
        set_locale(current_locale)

        # Re-initialize locale to ensure it's up to date
        self._initialize_locale()

        logger.debug("Translation manager reloaded")
