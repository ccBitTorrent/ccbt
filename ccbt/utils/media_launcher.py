"""Helpers for launching external media players on the local machine."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


def launch_media_player(
    stream_url: str,
    *,
    vlc_executable_path: Optional[str] = None,
) -> dict[str, Any]:
    """Launch an external player for the given stream URL.

    Prefers an explicitly configured VLC executable, then falls back to a
    discoverable ``vlc`` binary, and finally to the platform default opener.
    """
    if vlc_executable_path:
        executable = Path(vlc_executable_path)
        if executable.exists():
            subprocess.Popen([str(executable), stream_url])
            return {
                "launched": True,
                "method": "configured_vlc",
                "command": [str(executable), stream_url],
            }

    discovered_vlc = shutil.which("vlc")
    if discovered_vlc:
        subprocess.Popen([discovered_vlc, stream_url])
        return {
            "launched": True,
            "method": "vlc",
            "command": [discovered_vlc, stream_url],
        }

    if os.name == "nt":
        os.startfile(stream_url)  # type: ignore[attr-defined]  # noqa: S606
        return {"launched": True, "method": "default_open", "command": [stream_url]}
    if sys.platform == "darwin":
        subprocess.Popen(["open", stream_url])  # noqa: S607
        return {
            "launched": True,
            "method": "default_open",
            "command": ["open", stream_url],
        }

    opener = shutil.which("xdg-open")
    if opener:
        subprocess.Popen([opener, stream_url])
        return {
            "launched": True,
            "method": "default_open",
            "command": [opener, stream_url],
        }

    return {
        "launched": False,
        "method": "unavailable",
        "error": "Could not locate VLC or a platform URL opener",
    }
