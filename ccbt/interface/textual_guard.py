"""Fail loudly on unsupported Textual instead of silently mis-binding reactives."""
from __future__ import annotations

try:
    import textual
except ImportError:  # pragma: no cover - textual always present for the TUI
    textual = None  # type: ignore[assignment]

MIN_TEXTUAL = (8, 2, 8)


def textual_version() -> tuple[int, ...]:
    """Return the installed Textual version as a tuple of ints."""
    try:
        parts = []
        for p in str(getattr(textual, "__version__", "0")).split(".")[:3]:
            digits = "".join(ch for ch in p if ch.isdigit())
            parts.append(int(digits) if digits else 0)
        return tuple(parts)
    except Exception:
        return (0,)


def ensure_textual_version() -> tuple[int, ...]:
    """Raise RuntimeError when the installed Textual is too old."""
    v = textual_version()
    if v and v < MIN_TEXTUAL:
        msg = (
            f"ccBT TUI requires textual>={'.'.join(map(str, MIN_TEXTUAL))}, "
            f"found {'.'.join(map(str, v))}. Upgrade: uv sync (from the repo "
            "root) or pip install -U 'textual>=8.2.8'"
        )
        raise RuntimeError(msg)
    return v
