"""Reusable table widget base class for the tabbed interface.

Provides a common base for all table widgets with consistent behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.widgets import DataTable
else:
    try:
        from textual.widgets import DataTable
    except ImportError:
        class DataTable:  # type: ignore[no-redef]
            pass


class ReusableDataTable(DataTable):  # type: ignore[misc]
    """Base class for reusable data tables with common functionality.

    Provides:
    - Consistent column setup
    - Row formatting utilities
    - Selection handling
    - Refresh patterns
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize reusable data table."""
        super().__init__(*args, **kwargs)
        self.zebra_stripes = True
        self.cursor_type = "row"

    def format_size(self, size: int) -> str:
        """Format byte size to human-readable string.

        Args:
            size: Size in bytes

        Returns:
            Formatted size string (e.g., "1.23 GB", "456.78 MB")
        """
        if size >= 1024 * 1024 * 1024:
            return f"{size / (1024**3):.2f} GB"
        elif size >= 1024 * 1024:
            return f"{size / (1024**2):.2f} MB"
        elif size >= 1024:
            return f"{size / 1024:.2f} KB"
        else:
            return f"{size} B"

    def format_speed(self, speed: float) -> str:
        """Format speed to human-readable string.

        Args:
            speed: Speed in bytes per second

        Returns:
            Formatted speed string (e.g., "1.23 MB/s", "456.78 KB/s")
        """
        if speed >= 1024 * 1024:
            return f"{speed / (1024 * 1024):.2f} MB/s"
        elif speed >= 1024:
            return f"{speed / 1024:.2f} KB/s"
        else:
            return f"{speed:.2f} B/s"

    def format_percentage(self, value: float, decimals: int = 1) -> str:
        """Format percentage value.

        Args:
            value: Percentage value (0.0 to 1.0)
            decimals: Number of decimal places

        Returns:
            Formatted percentage string (e.g., "45.5%")
        """
        return f"{value * 100:.{decimals}f}%"

    def get_selected_key(self) -> str | None:
        """Get the key of the currently selected row.

        Returns:
            Row key or None if no row selected
        """
        try:
            if hasattr(self, "cursor_row_key"):
                row_key = self.cursor_row_key
                return None if row_key is None else str(row_key)
        except Exception:
            pass
        return None

    def clear_and_populate(self, rows: list[list[Any]], keys: list[str] | None = None) -> None:  # pragma: no cover
        """Clear table and populate with new rows.

        Args:
            rows: List of row data (each row is a list of cell values)
            keys: Optional list of row keys (must match rows length)
        """
        self.clear()
        if keys and len(keys) == len(rows):
            for row, key in zip(rows, keys):
                self.add_row(*row, key=key)
        else:
            for row in rows:
                self.add_row(*row)





















