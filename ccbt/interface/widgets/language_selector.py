"""Language selector widget for interface internationalization.

Provides a widget for selecting the interface language with flag indicators
and native language names.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccbt.interface.commands.executor import CommandExecutor
    from ccbt.interface.data_provider import DataProvider
else:
    try:
        from ccbt.interface.commands.executor import CommandExecutor
        from ccbt.interface.data_provider import DataProvider
    except ImportError:
        CommandExecutor = None  # type: ignore[assignment, misc]
        DataProvider = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container, Horizontal, Vertical
    from textual.message import Message
    from textual.widgets import Select, Static
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Message:  # type: ignore[no-redef]
        """Fallback Message class when textual is not available."""

        def __init__(self) -> None:
            pass

    class Select:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

from ccbt.i18n import _is_valid_locale, get_locale, set_locale
from ccbt.i18n import _ as translate

logger = logging.getLogger(__name__)

# Language mapping: locale_code -> (flag_emoji, native_name, english_name)
LANGUAGE_MAP = {
    "en": ("🇺🇸", "English", "English"),
    "es": ("🇪🇸", "Español", "Spanish"),
    "fr": ("🇫🇷", "Français", "French"),
    "ja": ("🇯🇵", "日本語", "Japanese"),
    "ko": ("🇰🇷", "한국어", "Korean"),
    "zh": ("🇨🇳", "中文", "Chinese"),
    "hi": ("🇮🇳", "हिन्दी", "Hindi"),
    "fa": ("🇮🇷", "فارسی", "Persian"),
    "ur": ("🇵🇰", "اردو", "Urdu"),
    "th": ("🇹🇭", "ไทย", "Thai"),
    "sw": ("🇹🇿", "Kiswahili", "Swahili"),
    "ha": ("🇳🇬", "Hausa", "Hausa"),
    "yo": ("🇳🇬", "Yorùbá", "Yoruba"),
    "eu": ("🇪🇸", "Euskara", "Basque"),
    "arc": ("🇸🇾", "ܐܪܡܝܐ", "Aramaic"),
}


class LanguageSelectorWidget(Container):  # type: ignore[misc]
    """Widget for selecting interface language with flag indicators."""

    class LanguageChanged(Message):  # type: ignore[misc]
        """Event emitted when language changes."""

        def __init__(self, locale: str) -> None:
            """Initialize language changed event.

            Args:
                locale: New locale code
            """
            super().__init__()
            self.locale = locale

    DEFAULT_CSS = """
    LanguageSelectorWidget {
        height: auto;
        layout: vertical;
        padding: 1;
    }
    
    #language-select-label {
        width: 1fr;
        text-align: center;
    }
    
    #language-select {
        width: 1fr;
    }
    
    #language-info {
        height: auto;
        min-height: 3;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize language selector widget.

        Args:
            data_provider: DataProvider instance (for reading config)
            command_executor: CommandExecutor instance (for updating config)
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._select_widget: Select | None = None
        self._info_widget: Static | None = None
        self._current_locale = get_locale()

    def compose(self) -> Any:  # pragma: no cover
        """Compose the language selector."""
        with Vertical():
            yield Static(
                translate("Interface Language"), id="language-select-label"
            )
            # Create select options with flags and names
            options = self._build_language_options()
            select_widget = Select(
                options,
                value=self._current_locale,
                id="language-select",
                prompt=translate("Select Language"),
            )
            yield select_widget
            yield Static("", id="language-info")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the language selector."""
        try:
            self._select_widget = self.query_one("#language-select", Select)  # type: ignore[attr-defined]
            self._info_widget = self.query_one("#language-info", Static)  # type: ignore[attr-defined]
            
            # Update info with current language
            self._update_language_info()
            
            # Set up event handler for select changes
            if self._select_widget:
                self._select_widget.can_focus = True  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting language selector: %s", e)

    def _build_language_options(self) -> list[tuple[str, str]]:
        """Build language options for Select widget.
        
        Returns:
            List of (display_text, locale_code) tuples
        """
        options: list[tuple[str, str]] = []
        current_locale = get_locale()
        
        for locale_code, (flag, native_name, english_name) in LANGUAGE_MAP.items():
            # Only include languages that have translation files
            if _is_valid_locale(locale_code):
                # Format: "🇺🇸 English" or "🇺🇸 English (English)"
                if native_name == english_name:
                    display = f"{flag} {native_name}"
                else:
                    display = f"{flag} {native_name} ({english_name})"
                options.append((display, locale_code))
        
        # Sort by English name for consistency
        options.sort(key=lambda x: LANGUAGE_MAP.get(x[1], ("", "", x[1]))[2])
        
        return options

    def _update_language_info(self) -> None:  # pragma: no cover
        """Update language info display."""
        if not self._info_widget:
            return
        
        current_locale = get_locale()
        lang_info = LANGUAGE_MAP.get(current_locale, ("", current_locale, current_locale))
        flag, native_name, english_name = lang_info
        
        info_text = translate("Current language: {flag} {name}").format(
            flag=flag, name=native_name
        )
        self._info_widget.update(info_text)

    def on_select_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle language selection change event.
        
        Args:
            event: Select.Changed event from Textual
        """
        if not hasattr(event, "value") or not event.value:
            return
        
        try:
            # event.value is the selected locale code (string)
            new_locale = event.value
            if not new_locale or new_locale == self._current_locale:
                return
            
            # CRITICAL FIX: Create async task properly to avoid hanging
            # We're already in the app's event loop, so just create the task directly
            import asyncio
            asyncio.create_task(self._change_language(new_locale))
        except Exception as e:
            logger.debug("Error handling language change: %s", e)
    
    async def _change_language(self, new_locale: str) -> None:  # pragma: no cover
        """Change language asynchronously.
        
        Args:
            new_locale: Selected locale code
        """
        if not new_locale or new_locale == self._current_locale:
            return
        
        try:
            # Validate locale
            if not _is_valid_locale(new_locale):
                logger.warning("Invalid locale selected: %s", new_locale)
                if self._info_widget:
                    self._info_widget.update(
                        translate("Invalid language: {locale}").format(locale=new_locale)
                    )
                return
            
            # Set locale
            set_locale(new_locale)
            self._current_locale = new_locale
            
            # Update config via executor
            # Note: This requires a config.update command in the executor
            try:
                # Try to update config via executor
                result = await self._command_executor.execute_command(
                    "config.update",
                    section="ui",
                    key="locale",
                    value=new_locale,
                )
                if result and hasattr(result, "success") and result.success:
                    logger.info("Language updated to: %s", new_locale)
                else:
                    # Fallback: update environment variable
                    import os
                    os.environ["CCBT_UI_LOCALE"] = new_locale
                    logger.info("Language updated via environment variable: %s", new_locale)
            except Exception as e:
                # Fallback: update environment variable
                import os
                os.environ["CCBT_UI_LOCALE"] = new_locale
                logger.debug("Could not update config via executor, using environment: %s", e)
            
            # Update info display
            self._update_language_info()
            
            # CRITICAL FIX: Post message to app so it propagates to all widgets
            # Textual messages bubble up through the widget tree, but we need to ensure
            # the app receives it to coordinate the refresh
            try:
                if self.app:
                    # Post to app first to ensure it's received
                    self.app.post_message(self.LanguageChanged(new_locale))  # type: ignore[attr-defined]
                # Also post from this widget (will bubble up)
                self.post_message(self.LanguageChanged(new_locale))  # type: ignore[attr-defined]
                logger.info("LanguageChanged message posted for locale: %s", new_locale)
            except Exception as e:
                logger.error("Error posting LanguageChanged message: %s", e, exc_info=True)
            
            # Notify user that interface is updating
            if self._info_widget:
                self._info_widget.update(
                    translate("Language changed to {locale}. Interface updating...")
                    .format(locale=new_locale)
                )
        except Exception as e:
            logger.error("Error changing language: %s", e)
            if self._info_widget:
                self._info_widget.update(
                    translate("Error changing language: {error}").format(error=str(e))
                )

