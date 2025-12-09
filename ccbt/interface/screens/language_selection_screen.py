"""Language selection modal screen.

Provides a modal screen for selecting the interface language using the
existing LanguageSelectorWidget.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from ccbt.i18n import _

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
    from textual.screen import ModalScreen
    from textual.widgets import Button, Static
except ImportError:
    # Fallback for when textual is not available
    class ModalScreen:  # type: ignore[no-redef]
        pass

    class Container:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class Button:  # type: ignore[no-redef]
        pass

logger = logging.getLogger(__name__)


class LanguageSelectionScreen(ModalScreen):  # type: ignore[misc]
    """Modal screen for selecting interface language."""

    DEFAULT_CSS = """
    LanguageSelectionScreen {
        align: center middle;
    }
    #dialog {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    #title {
        height: 1;
        text-align: center;
        text-style: bold;
        margin: 1;
    }
    #language-selector-container {
        height: auto;
        margin: 1;
    }
    #buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider | None = None,
        command_executor: CommandExecutor | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize language selection screen.

        Args:
            data_provider: Optional DataProvider instance
            command_executor: Optional CommandExecutor instance
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._language_selector: Any | None = None
        self._selected_locale: str | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the language selection screen."""
        if not self._data_provider or not self._command_executor:
            # Fallback if data provider or executor not available
            with Container(id="dialog"):
                yield Static(_("Select Language"), id="title")
                yield Static(_("Data provider or command executor not available"), id="error")
                with Horizontal(id="buttons"):
                    yield Button(_("Close"), id="close", variant="default")
            return

        # Use existing LanguageSelectorWidget
        from ccbt.interface.widgets.language_selector import LanguageSelectorWidget

        with Container(id="dialog"):
            yield Static(_("Select Language"), id="title")
            
            with Container(id="language-selector-container"):
                self._language_selector = LanguageSelectorWidget(
                    self._data_provider,
                    self._command_executor,
                    id="language-selector"
                )
                yield self._language_selector
            
            with Horizontal(id="buttons"):
                yield Button(_("Close"), id="close", variant="default")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the language selection screen."""
        try:
            # Focus the language selector widget if available
            if self._language_selector:
                try:
                    select_widget = self._language_selector.query_one("#language-select")  # type: ignore[attr-defined]
                    select_widget.focus()  # type: ignore[attr-defined]
                except Exception:
                    pass  # Select widget may not be available yet
        except Exception as e:
            logger.debug("Error mounting language selection screen: %s", e)

    def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "close":
            self.dismiss(True)  # type: ignore[attr-defined]

    def on_language_changed(self, message: Any) -> None:  # pragma: no cover
        """Handle language change event from LanguageSelectorWidget.
        
        Args:
            message: LanguageChanged message with new locale
        """
        try:
            from ccbt.interface.widgets.language_selector import (
                LanguageSelectorWidget,
            )

            # Verify this is a LanguageChanged message
            if not hasattr(message, "locale"):
                return

            new_locale = message.locale
            self._selected_locale = new_locale
            logger.info("Language changed to: %s in modal screen", new_locale)

            # The LanguageSelectorWidget already handles the language change,
            # so we just need to propagate the message to the parent app
            # and dismiss the modal after a short delay to allow the change to propagate
            if self.app:  # type: ignore[attr-defined]
                # Post message to app so it can handle propagation
                self.app.post_message(message)  # type: ignore[attr-defined]
                
                # Dismiss after a short delay to allow propagation
                self.call_later(self._dismiss_after_change)  # type: ignore[attr-defined]

        except Exception as e:
            logger.debug("Error handling language change in modal: %s", e)

    def _dismiss_after_change(self) -> None:  # pragma: no cover
        """Dismiss the modal after language change has propagated."""
        try:
            self.dismiss(True)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error dismissing language selection screen: %s", e)

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "close", _("Close")),
    ]

    async def action_close(self) -> None:  # pragma: no cover
        """Close the language selection screen."""
        self.dismiss(True)  # type: ignore[attr-defined]

