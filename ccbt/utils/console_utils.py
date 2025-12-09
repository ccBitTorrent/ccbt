"""Enhanced console utilities with spinners and Rich patterns.

Provides spinner utilities, progress context managers, and status message
utilities with i18n support.
"""

from __future__ import annotations

import contextlib
import logging
import sys
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

from ccbt.i18n import _
from ccbt.utils.logging_config import get_logger


def create_console() -> Console:
    """Create a Rich Console with Windows encoding compatibility."""
    if sys.platform == "win32":
        try:
            if hasattr(sys.stdout, "reconfigure") and callable(
                getattr(sys.stdout, "reconfigure", None)
            ):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            if hasattr(sys.stderr, "reconfigure") and callable(
                getattr(sys.stderr, "reconfigure", None)
            ):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    return Console(
        file=sys.stdout,
        force_terminal=None,
        legacy_windows=False,
        safe_box=True,
    )


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
    show_header: bool = True,
    show_footer: bool = False,
    border_style: str = "blue",
    header_style: str = "bold cyan",
    row_styles: list[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Create and print a Rich table with i18n support and enhanced styling.

    Args:
        title: Optional table title (will be translated)
        console: Optional Rich Console instance
        show_header: Whether to show table header
        show_footer: Whether to show table footer
        border_style: Border style color
        header_style: Header text style
        row_styles: List of row styles (alternating)
        **kwargs: Additional arguments for Table constructor

    Returns:
        Rich Table instance

    """
    from rich.table import Table

    if console is None:
        console = create_console()

    # Set default styles
    table_kwargs = {
        "title": _(title) if title else None,
        "show_header": show_header,
        "show_footer": show_footer,
        "border_style": border_style,
        "header_style": header_style,
        **kwargs,
    }

    table = Table(**table_kwargs)  # type: ignore[arg-type]

    # Apply row styles
    if row_styles:
        table.row_styles = row_styles

    return table


def print_panel(
    content: str,
    title: str | None = None,
    console: Console | None = None,
    border_style: str = "blue",
    title_align: str = "left",
    expand: bool = False,
    **kwargs: Any,
) -> None:
    """Print a Rich panel with i18n support and enhanced styling.

    Args:
        content: Panel content (will be translated)
        title: Optional panel title (will be translated)
        console: Optional Rich Console instance
        border_style: Border style color
        title_align: Title alignment ("left", "center", "right")
        expand: Whether to expand panel to fill available space
        **kwargs: Additional arguments for Panel constructor

    """
    from rich.panel import Panel

    if console is None:
        console = create_console()

    translated_content = _(content)
    translated_title = _(title) if title else None

    panel_kwargs = {
        "title": translated_title,
        "border_style": border_style,
        "title_align": title_align,
        "expand": expand,
        **kwargs,
    }

    panel = Panel(translated_content, **panel_kwargs)  # type: ignore[arg-type]
    console.print(panel)


def print_markdown(
    content: str,
    console: Console | None = None,
    code_theme: str = "monokai",
    **kwargs: Any,
) -> None:
    """Print markdown content with Rich rendering.

    Args:
        content: Markdown content to render
        console: Optional Rich Console instance
        code_theme: Code block theme
        **kwargs: Additional arguments for Markdown constructor

    """
    try:
        from rich.markdown import Markdown
    except ImportError:
        if console is None:
            console = create_console()
        console.print(content)
        return

    if console is None:
        console = create_console()

    markdown = Markdown(content, code_theme=code_theme, **kwargs)
    console.print(markdown)


@contextlib.contextmanager
def live_display(
    renderable: Any | None = None,
    console: Console | None = None,
    refresh_per_second: float = 4.0,
    vertical_overflow: str = "visible",
) -> Iterator[Any]:
    """Context manager for Rich Live display updates.

    Args:
        renderable: Initial renderable to display
        console: Optional Rich Console instance
        refresh_per_second: Refresh rate
        vertical_overflow: How to handle vertical overflow

    Yields:
        Live instance that can be updated

    Example:
        with live_display() as live:
            for i in range(10):
                live.update(Table(...))
                time.sleep(0.25)

    """
    from rich.live import Live

    if console is None:
        console = create_console()

    live = Live(
        renderable,
        console=console,
        refresh_per_second=refresh_per_second,
        vertical_overflow=vertical_overflow,
    )
    live.start()
    try:
        yield live
    finally:
        live.stop()


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
        msg = "rich.progress is not available"
        raise ImportError(msg)

    if console is None:
        console = create_console()

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )


# Logging helpers for replacing console.print() with proper logging


def log_user_output(
    message: str,
    verbosity_manager: Any | None = None,
    logger: logging.Logger | None = None,
    level: int = logging.INFO,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Log a user-facing message respecting verbosity levels.

    Use this for messages that should be visible to users but respect verbosity.
    For final results and interactive prompts, use console.print() directly.

    Args:
        message: Message to log (will be translated)
        verbosity_manager: Optional VerbosityManager instance
        logger: Optional logger instance (defaults to caller's logger)
        level: Logging level (default: INFO)
        *args: Format arguments
        **kwargs: Additional logging kwargs

    """
    if logger is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_module = frame.f_back.f_globals.get("__name__", "ccbt")
            logger = get_logger(caller_module)
        else:
            logger = get_logger(__name__)

    # Check verbosity if manager provided
    if verbosity_manager is not None and not verbosity_manager.should_log(level):
        return

    # Translate message
    translated = _(message)

    logger.log(level, translated, *args, **kwargs)


def log_operation(
    operation: str,
    status: str = "started",
    verbosity_manager: Any | None = None,
    logger: logging.Logger | None = None,
    **kwargs: Any,
) -> None:
    """Log an operation status message.

    Args:
        operation: Operation name (will be translated)
        status: Status (e.g., "started", "completed", "failed")
        verbosity_manager: Optional VerbosityManager instance
        logger: Optional logger instance
        **kwargs: Additional logging kwargs

    """
    if logger is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_module = frame.f_back.f_globals.get("__name__", "ccbt")
            logger = get_logger(caller_module)
        else:
            logger = get_logger(__name__)

    # Determine log level based on status
    if status == "failed":
        level = logging.ERROR
    elif status == "completed":
        level = logging.INFO
    else:
        level = logging.INFO

    # Check verbosity
    if verbosity_manager is not None and not verbosity_manager.should_log(level):
        return

    # Translate operation name
    translated_op = _(operation)
    translated_status = _(status)

    message = f"{translated_op} {translated_status}"
    logger.log(level, message, **kwargs)


def log_result(
    operation: str,
    success: bool,
    details: str | None = None,
    verbosity_manager: Any | None = None,
    logger: logging.Logger | None = None,
    **kwargs: Any,
) -> None:
    """Log a command result.

    Args:
        operation: Operation name (will be translated)
        success: Whether operation succeeded
        details: Optional details message
        verbosity_manager: Optional VerbosityManager instance
        logger: Optional logger instance
        **kwargs: Additional logging kwargs

    """
    if logger is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_module = frame.f_back.f_globals.get("__name__", "ccbt")
            logger = get_logger(caller_module)
        else:
            logger = get_logger(__name__)

    level = logging.INFO if success else logging.ERROR

    # Check verbosity
    if verbosity_manager is not None and not verbosity_manager.should_log(level):
        return

    # Translate
    translated_op = _(operation)
    status = _("succeeded") if success else _("failed")

    if details:
        translated_details = _(details)
        message = f"{translated_op} {status}: {translated_details}"
    else:
        message = f"{translated_op} {status}"

    logger.log(level, message, **kwargs)
