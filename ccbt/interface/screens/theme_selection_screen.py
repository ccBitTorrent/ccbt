"""Theme selection modal screen.

Provides a modal screen for selecting the Textual theme.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from ccbt.i18n import _

if TYPE_CHECKING:
    pass
else:
    pass

try:
    from textual.containers import Container, Horizontal
    from textual.screen import ModalScreen
    from textual.widgets import Button, Select, Static
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

    class Select:  # type: ignore[no-redef]
        pass

logger = logging.getLogger(__name__)

# Available Textual themes
AVAILABLE_THEMES: list[tuple[str, str]] = [
    ("default", _("Default (Light)")),
    ("textual-dark", _("Textual Dark")),
    ("vscode_dark", _("VS Code Dark")),
    ("monokai", _("Monokai")),
    ("dracula", _("Dracula")),
    ("github_dark", _("GitHub Dark")),
    ("nord", _("Nord")),
    ("one_dark", _("One Dark")),
    ("solarized_dark", _("Solarized Dark")),
    ("solarized_light", _("Solarized Light")),
    ("catppuccin", _("Catppuccin")),
    ("gruvbox", _("Gruvbox")),
    ("tokyo_night", _("Tokyo Night")),
    ("rainbow", _("Rainbow")),
]


class ThemeSelectionScreen(ModalScreen):  # type: ignore[misc]
    """Modal screen for selecting Textual theme."""

    DEFAULT_CSS = """
    ThemeSelectionScreen {
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
    #theme-selector-container {
        height: auto;
        margin: 1;
    }
    #theme-select {
        width: 1fr;
        height: 3;
    }
    #buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize theme selection screen."""
        super().__init__(*args, **kwargs)
        self._selected_theme: str | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the theme selection screen."""
        # Get current theme from app
        current_theme = "default"
        if self.app:  # type: ignore[attr-defined]
            try:
                current_theme = getattr(self.app, "theme", "default")  # type: ignore[attr-defined]
                if not current_theme or current_theme == "None":
                    current_theme = "default"
            except Exception:
                current_theme = "default"

        # Create Select widget with available themes
        theme_options = [
            (description, theme_name)
            for theme_name, description in AVAILABLE_THEMES
        ]
        
        # Validate current_theme is in available options
        # If not, default to "default" to avoid InvalidSelectValueError
        available_theme_names = [theme_name for theme_name, _ in AVAILABLE_THEMES]
        if current_theme not in available_theme_names:
            logger.warning(
                "Current theme '%s' not in available themes, defaulting to 'default'",
                current_theme
            )
            current_theme = "default"

        with Container(id="dialog"):
            yield Static(_("Select Theme"), id="title")
            
            with Container(id="theme-selector-container"):
                yield Select(
                    theme_options,
                    value=current_theme,
                    prompt=_("Choose a theme"),
                    id="theme-select"
                )
            
            with Horizontal(id="buttons"):
                yield Button(_("Apply"), id="apply", variant="primary")
                yield Button(_("Close"), id="close", variant="default")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the theme selection screen."""
        try:
            # Focus the theme selector
            select_widget = self.query_one("#theme-select", Select)  # type: ignore[attr-defined]
            select_widget.focus()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting theme selection screen: %s", e)

    def on_select_changed(self, event: Select.Changed) -> None:  # pragma: no cover
        """Handle theme selection change."""
        if event.select.id == "theme-select":  # type: ignore[attr-defined]
            self._selected_theme = event.select.value  # type: ignore[attr-defined]

    def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "apply":
            # Apply selected theme
            if self._selected_theme:
                try:
                    if self.app:  # type: ignore[attr-defined]
                        self.app.theme = self._selected_theme  # type: ignore[attr-defined]
                        logger.info("Theme changed to: %s", self._selected_theme)
                except Exception as e:
                    logger.error("Error applying theme: %s", e)
            # Also check current select value
            try:
                select_widget = self.query_one("#theme-select", Select)  # type: ignore[attr-defined]
                selected_value = select_widget.value  # type: ignore[attr-defined]
                if selected_value and self.app:  # type: ignore[attr-defined]
                    self.app.theme = selected_value  # type: ignore[attr-defined]
                    logger.info("Theme changed to: %s", selected_value)
            except Exception as e:
                logger.debug("Error applying theme from select: %s", e)
            self.dismiss(True)  # type: ignore[attr-defined]
        elif event.button.id == "close":
            self.dismiss(True)  # type: ignore[attr-defined]

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "close", _("Close")),
        ("enter", "apply", _("Apply")),
    ]

    async def action_close(self) -> None:  # pragma: no cover
        """Close the theme selection screen."""
        self.dismiss(True)  # type: ignore[attr-defined]

    async def action_apply(self) -> None:  # pragma: no cover
        """Apply the selected theme."""
        try:
            select_widget = self.query_one("#theme-select", Select)  # type: ignore[attr-defined]
            selected_value = select_widget.value  # type: ignore[attr-defined]
            if selected_value and self.app:  # type: ignore[attr-defined]
                self.app.theme = selected_value  # type: ignore[attr-defined]
                logger.info("Theme changed to: %s", selected_value)
        except Exception as e:
            logger.debug("Error applying theme: %s", e)
        self.dismiss(True)  # type: ignore[attr-defined]



