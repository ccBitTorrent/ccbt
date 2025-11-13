"""Enhanced console utilities with spinners and Rich patterns.

Provides spinner utilities, progress context managers, and status message
utilities with i18n support.
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterator

from rich.console import Console
from rich.status import Status

try:
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    _RICH_PROGRESS_AVAILABLE = True
except ImportError:
    _RICH_PROGRESS_AVAILABLE = False


from ccbt.cli.console import create_console
from ccbt.i18n import _


@contextlib.contextmanager
def spinner(
    message: str,
    console: Console | None = None,
    spinner_style: str = "dots",
) -> Iterator[Status]:
    """Context manager for showing a spinner during async operations.

    Args:
        message: Message to display (will be translated)
        console: Optional Rich Console instance
        spinner_style: Spinner style (e.g., "dots", "line", "bouncingBar")

    Yields:
        Status object that can be updated

    Example:
        with spinner("Loading data...") as status:
            await load_data()
            status.update("Processing...")

    """
    if console is None:
        console = create_console()

    # Translate message
    translated_message = _(message)

    status = Status(translated_message, console=console, spinner=spinner_style)
    status.start()
    try:
        yield status
    finally:
        status.stop()


def print_success(
    message: str,
    console: Console | None = None,
    **kwargs: Any,
) -> None:
    """Print a success message with Rich formatting and i18n.

    Args:
        message: Message to display (will be translated)
        console: Optional Rich Console instance
        **kwargs: Additional arguments for console.print()

    """
    if console is None:
        console = create_console()

    translated = _(message)
    console.print(f"[green]✓[/green] {translated}", **kwargs)


def print_error(
    message: str,
    console: Console | None = None,
    **kwargs: Any,
) -> None:
    """Print an error message with Rich formatting and i18n.

    Args:
        message: Message to display (will be translated)
        console: Optional Rich Console instance
        **kwargs: Additional arguments for console.print()

    """
    if console is None:
        console = create_console()

    translated = _(message)
    console.print(f"[red]✗[/red] {translated}", **kwargs)


def print_warning(
    message: str,
    console: Console | None = None,
    **kwargs: Any,
) -> None:
    """Print a warning message with Rich formatting and i18n.

    Args:
        message: Message to display (will be translated)
        console: Optional Rich Console instance
        **kwargs: Additional arguments for console.print()

    """
    if console is None:
        console = create_console()

    translated = _(message)
    console.print(f"[yellow]⚠[/yellow] {translated}", **kwargs)


def print_info(
    message: str,
    console: Console | None = None,
    **kwargs: Any,
) -> None:
    """Print an info message with Rich formatting and i18n.

    Args:
        message: Message to display (will be translated)
        console: Optional Rich Console instance
        **kwargs: Additional arguments for console.print()

    """
    if console is None:
        console = create_console()

    translated = _(message)
    console.print(f"[cyan]ℹ[/cyan] {translated}", **kwargs)


def print_table(
    title: str | None = None,
    console: Console | None = None,
    **kwargs: Any,
) -> Any:
    """Create and print a Rich table with i18n support.

    Args:
        title: Optional table title (will be translated)
        console: Optional Rich Console instance
        **kwargs: Additional arguments for Table constructor

    Returns:
        Rich Table instance

    """
    from rich.table import Table

    if console is None:
        console = create_console()

    table = Table(title=_(title) if title else None, **kwargs)
    return table


def print_panel(
    content: str,
    title: str | None = None,
    console: Console | None = None,
    **kwargs: Any,
) -> None:
    """Print a Rich panel with i18n support.

    Args:
        content: Panel content (will be translated)
        title: Optional panel title (will be translated)
        console: Optional Rich Console instance
        **kwargs: Additional arguments for Panel constructor

    """
    from rich.panel import Panel

    if console is None:
        console = create_console()

    translated_content = _(content)
    translated_title = _(title) if title else None

    panel = Panel(translated_content, title=translated_title, **kwargs)
    console.print(panel)


def create_progress(
    console: Console | None = None,
    description: str | None = None,
) -> Progress:
    """Create a Rich Progress bar with i18n support.

    Args:
        console: Optional Rich Console instance
        description: Optional progress description (will be translated)

    Returns:
        Rich Progress instance

    """
    if not _RICH_PROGRESS_AVAILABLE:
        raise ImportError("rich.progress is not available")

    if console is None:
        console = create_console()

    translated_description = _(description) if description else None

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )
