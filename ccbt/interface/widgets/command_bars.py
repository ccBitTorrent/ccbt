"""Command bars widget for displaying key bindings in organized groups."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ccbt.i18n import _

if TYPE_CHECKING:
    from textual.widgets import Static
else:
    try:
        from textual.widgets import Static
    except ImportError:
        class Static:  # type: ignore[no-redef]
            pass

try:
    from textual.containers import Container, Horizontal, Vertical
except ImportError:
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass


class CommandBars(Container):  # type: ignore[misc]
    """Widget to display command key bindings in organized horizontal bars."""

    DEFAULT_CSS = """
    CommandBars {
        height: auto;
        min-height: 2;
        max-height: 6;
        layout: vertical;
        border-top: solid $primary;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0 1;
        display: block;
    }
    .command-row {
        height: 1;
        layout: horizontal;
        margin: 0;
        padding: 0;
    }
    .command-group {
        margin: 0 1;
        border-right: solid $surface;
        padding-right: 1;
        height: 1;
        layout: horizontal;
        align-vertical: middle;
    }
    .command-item {
        margin: 0 1;
        width: auto;
        height: 1;
    }
    """

    def __init__(self, bindings: list[tuple[str, str, str]] | None = None, *args: Any, **kwargs: Any) -> None:
        """Initialize command bars widget.
        
        Args:
            bindings: List of (key, action, description) tuples
        """
        super().__init__(*args, **kwargs)
        self._bindings = bindings or []

    def compose(self) -> Any:  # pragma: no cover
        """Compose the command bars with grouped commands in maximally filled rows."""
        if not self._bindings:
            yield Static("No commands available", classes="command-item")
            return
        
        # Calculate optimal commands per row to maximize row usage
        # Try to fit all commands in as few rows as possible
        total_commands = len(self._bindings)
        
        # Try to fit in 1 row first, then 2, then 3, etc.
        for num_rows in range(1, 4):
            commands_per_row = (total_commands + num_rows - 1) // num_rows  # Ceiling division
            if commands_per_row <= 10:  # Max 10 commands per row for readability
                break
        else:
            # Fallback: use 8 commands per row
            commands_per_row = 8
            num_rows = (total_commands + commands_per_row - 1) // commands_per_row
        
        # Split bindings into rows
        rows = []
        current_row = []
        
        for key, action, description in self._bindings:
            current_row.append((key, action, description))
            if len(current_row) >= commands_per_row:
                rows.append(current_row)
                current_row = []
        
        # Add remaining row
        if current_row:
            rows.append(current_row)
        
        # Create horizontal rows using context managers
        for row in rows:
            with Horizontal(classes="command-row"):
                for key, action, description in row:
                    yield Static(
                        f"[cyan]{key}[/cyan] {description}",
                        classes="command-item"
                    )

