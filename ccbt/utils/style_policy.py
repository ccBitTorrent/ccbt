"""Shared Rich and Textual style policy for ccBitTorrent output.

Centralizes semantic color names and helper utilities so logging, TUI, and splash
output share a consistent visual language.
"""

from __future__ import annotations

import re

LOG_LEVEL_STYLES: dict[str, str] = {
    "DEBUG": "dim",
    "TRACE": "dim",
    "INFO": "cyan",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold red",
}

LOG_METHOD_STYLE = "#ff69b4"  # hot pink
LOG_ACTION_STYLE = "bright_cyan"
LOG_ALL_CAPS_STYLE = "orange1"
DIM_STYLE = "dim"

LOG_ACTION_PATTERNS = (
    r"PIECE_MANAGER:",
    r"PIECE_MESSAGE:",
    r"Sent \d+ REQUEST message\(s\)",
    r"Received piece",
    r"state transition:",
    r"No available peers",
    r"Checking \d+ active peers",
)

ALL_CAPS_PATTERN = r"\b[A-Z][A-Z_]*[A-Z]\b|\b[A-Z]{2,}\b"

# Common status colors used in dashboard and alerts
SUCCESS_STYLE = "green"
WARNING_STYLE = "yellow"
FAIR_STYLE = "orange1"
ERROR_STYLE = "red"
KEY_STYLE = "cyan"
SECTION_HEADER_STYLE = "bold yellow"


def markup(text: str, style: str) -> str:
    """Wrap text in Rich markup.

    Args:
        text: Text to wrap
        style: Rich style name or markup token

    Returns:
        Text wrapped in markup
    """
    if not style:
        return text
    return f"[{style}]{text}[/{style}]"


def color_for_log_level(level_name: str) -> str:
    """Resolve a log level name to a shared style token."""
    return LOG_LEVEL_STYLES.get(level_name.upper(), "white")


def format_log_level_label(level_name: str) -> str:
    """Format the level prefix with shared log-level coloring."""
    return markup(level_name, color_for_log_level(level_name))


def format_log_method_name(func_name: str) -> str:
    """Format a method name with the shared method color."""
    if not func_name:
        return ""
    return markup(func_name, LOG_METHOD_STYLE)


def colorize_action_text(message: str) -> str:
    """Colorize log action text and uppercase tokens using shared style tokens."""
    if not message:
        return message

    output = message
    for pattern in LOG_ACTION_PATTERNS:
        matches = list(re.finditer(pattern, output))
        for match in reversed(matches):
            start, end = match.span()
            token = output[start:end]
            if f"[{LOG_ACTION_STYLE}]" not in output[max(0, start - 20) : start]:
                output = (
                    output[:start]
                    + f"[{LOG_ACTION_STYLE}]{token}[/{LOG_ACTION_STYLE}]"
                    + output[end:]
                )

    matches = list(re.finditer(ALL_CAPS_PATTERN, output))
    for match in reversed(matches):
        start, end = match.span()
        token = output[start:end]
        if not (token.isupper() or (token.replace("_", "").isupper() and "_" in token)):
            continue

        before_context = output[max(0, start - 30) : start]
        after_context = output[end : min(len(output), end + 30)]
        if "[" in before_context and "]" in after_context:
            if "[/" in after_context:
                continue
            if before_context.rstrip().endswith("]"):
                continue

        if (
            f"[{LOG_ALL_CAPS_STYLE}]" in before_context
            or f"[/{LOG_ALL_CAPS_STYLE}]" in before_context
            or f"#{LOG_ALL_CAPS_STYLE}" in before_context
            or f"[{LOG_ALL_CAPS_STYLE}]" in after_context
        ):
            continue

        output = (
            output[:start]
            + f"[{LOG_ALL_CAPS_STYLE}]{token}[/{LOG_ALL_CAPS_STYLE}]"
            + output[end:]
        )

    return output


def quality_style_for_percentage(value: float) -> str:
    """Map a score into shared quality colors."""
    if value >= 80:
        return SUCCESS_STYLE
    if value >= 60:
        return WARNING_STYLE
    if value >= 40:
        return FAIR_STYLE
    return ERROR_STYLE
