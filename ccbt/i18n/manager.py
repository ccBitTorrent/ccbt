"""Translation manager with configuration integration."""

from __future__ import annotations

from typing import Any

from ccbt.i18n import get_locale, set_locale


class TranslationManager:
    """Manages translations with config integration."""

    def __init__(self, config: Any | None = None) -> None:
        """Initialize translation manager.

        Args:
            config: Optional config to read locale from

        """
        self.config = config
        self._initialize_locale()

    def _initialize_locale(self) -> None:
        """Initialize locale from config or environment."""
        if (
            self.config
            and hasattr(self.config, "ui")
            and hasattr(self.config.ui, "locale")
        ):
            locale_code = self.config.ui.locale
            if locale_code:
                set_locale(locale_code)
        else:
            # Use system/environment locale
            get_locale()  # This will set up the default

    def reload(self) -> None:
        """Reload translations (e.g., after config change)."""
        self._initialize_locale()
