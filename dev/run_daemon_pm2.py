#!/usr/bin/env python3
"""PM2 entry point: run ccbt daemon as __main__.

Use this script as the PM2 'script' so the daemon can be managed by PM2.
Arguments (e.g. --config, --foreground) are passed through to the daemon.
"""

from __future__ import annotations

import runpy
import sys

if __name__ == "__main__":
    runpy.run_module("ccbt.daemon.main", run_name="__main__")
