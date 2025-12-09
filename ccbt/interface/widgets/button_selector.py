"""Button-based selector widget to replace Tabs for better visibility control."""

from typing import TYPE_CHECKING, Any

from textual.containers import Container
from textual.message import Message
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

logger = __import__("logging").getLogger(__name__)


class ButtonSelector(Container):  # type: ignore[misc]
    """Button-based selector that replaces Tabs widget for better visibility control.
    
    This widget uses buttons instead of tabs to avoid Textual's tab visibility issues.
    All content is always mounted and visible, with manual visibility management.
    """

    DEFAULT_CSS = """
    ButtonSelector {
        height: auto;
        min-height: 3;
        layout: horizontal;
        border-bottom: solid $primary;
    }
    
    ButtonSelector Button {
        margin: 0 1;
        min-width: 10;
    }
    
    ButtonSelector Button.-active {
        background: $primary;
        color: $text;
        text-style: bold;
    }
    """

    def __init__(
        self,
        options: list[tuple[str, str]],  # [(id, label), ...]
        initial_selection: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize button selector.
        
        Args:
            options: List of (id, label) tuples for each button
            initial_selection: ID of initially selected button
        """
        super().__init__(*args, **kwargs)
        self._options = options
        self._buttons: dict[str, Button] = {}
        self._active_id: str | None = initial_selection or (options[0][0] if options else None)

    def compose(self) -> "ComposeResult":  # pragma: no cover
        """Compose the button selector."""
        for option_id, label in self._options:
            button = Button(
                label,
                id=f"btn-{option_id}",
                variant="default" if option_id != self._active_id else "primary",
            )
            self._buttons[option_id] = button
            yield button

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the button selector."""
        # Set initial active button
        if self._active_id:
            self._set_active(self._active_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:  # pragma: no cover
        """Handle button press."""
        button_id = event.button.id  # type: ignore[attr-defined]
        if button_id and button_id.startswith("btn-"):
            option_id = button_id[4:]  # Remove "btn-" prefix
            self._set_active(option_id)
            # Post message for parent to handle - include selector reference
            message = self.SelectionChanged(option_id)  # type: ignore[attr-defined]
            message.selector = self  # type: ignore[attr-defined]
            self.post_message(message)  # type: ignore[attr-defined]

    def _set_active(self, option_id: str) -> None:  # pragma: no cover
        """Set active button."""
        if option_id == self._active_id:
            return
        
        # Update button styles
        for opt_id, button in self._buttons.items():
            if opt_id == option_id:
                button.variant = "primary"  # type: ignore[attr-defined]
                button.add_class("-active")  # type: ignore[attr-defined]
            else:
                button.variant = "default"  # type: ignore[attr-defined]
                button.remove_class("-active")  # type: ignore[attr-defined]
        
        self._active_id = option_id

    @property
    def active(self) -> str | None:  # pragma: no cover
        """Get active selection ID."""
        return self._active_id

    @active.setter
    def active(self, value: str) -> None:  # pragma: no cover
        """Set active selection ID."""
        self._set_active(value)

    class SelectionChanged(Message):  # type: ignore[misc]
        """Message posted when selection changes."""
        
        def __init__(self, selection_id: str) -> None:
            super().__init__()
            self.selection_id = selection_id

