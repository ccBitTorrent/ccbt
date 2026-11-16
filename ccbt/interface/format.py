"""Shared formatting for the Textual TUI. Single source for all screens/widgets."""
from __future__ import annotations

from typing import Optional, Union


def fmt_bytes(value: Optional[Union[float, int]]) -> str:
    v = float(value or 0)
    if v >= 1024**3: return f"{v/(1024**3):.2f} GB"
    if v >= 1024**2: return f"{v/(1024**2):.2f} MB"
    if v >= 1024: return f"{v/1024:.2f} KB"
    return f"{int(v)} B"

def fmt_rate(value: Optional[Union[float, int]]) -> str:
    v = float(value or 0)
    if v >= 1024**2: return f"{v/(1024**2):.2f} MB/s"
    if v >= 1024: return f"{v/1024:.1f} KB/s"
    return f"{v:.0f} B/s"

def fmt_duration(seconds: Optional[Union[float, int]]) -> str:
    s = int(seconds or 0)
    if s < 60: return f"{s}s"
    if s < 3600: return f"{s//60}m {s%60:02d}s"
    if s < 86400: return f"{s//3600}h {(s%3600)//60:02d}m"
    return f"{s//86400}d {(s%86400)//3600}h"

def fmt_eta(seconds: Optional[Union[float, int]]) -> str:
    if seconds is None or float(seconds) <= 0: return "∞"
    return fmt_duration(seconds)

def fmt_ratio(downloaded: Optional[Union[float, int]], uploaded: Optional[Union[float, int]] = None, ratio: Optional[float] = None) -> str:
    if ratio is not None: return f"{float(ratio):.2f}"
    d = float(downloaded or 0)
    return f"{(float(uploaded or 0)/d):.2f}" if d > 0 else "∞"

def fmt_progress_bar(progress: float, width: int = 10) -> str:
    p = max(0.0, min(1.0, float(progress or 0)))
    filled = int(round(p * width))
    return "█" * filled + "░" * (width - filled) + f" {p*100:.1f}%"

def fmt_hash(value: Optional[Union[str, bytes]], chars: int = 8) -> str:
    if isinstance(value, bytes): value = value.hex()
    return str(value or "")[:chars]

STATUS_CHIPS: dict[str, tuple[str, str]] = {
    "downloading": ("▼", "downloading"), "seeding": ("▲", "seeding"),
    "paused": ("⏸", "paused"), "stopped": ("⏹", "stopped"),
    "error": ("✖", "error"), "checking": ("◌", "checking"),
    "queued": ("⋯", "queued"), "metadata": ("◌", "metadata"),
    "completed": ("✓", "completed"), "unknown": ("?", "unknown"),
}

def fmt_status(status: Optional[str]) -> str:
    key = str(status or "unknown").lower()
    icon, label = STATUS_CHIPS.get(key, STATUS_CHIPS["unknown"])
    return f"{icon} {label}"
