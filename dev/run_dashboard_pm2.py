#!/usr/bin/env python3
"""PM2 entry point: run ccBitTorrent TUI dashboard (bitonic).

Use this script as the PM2 'script' so the interface logs are captured
to the same logs/pm2/ directory as the daemon. Arguments (e.g. --refresh, --dev)
are passed through to the dashboard.
"""

from __future__ import annotations

import sys

if __name__ == "__main__":
    from ccbt.interface.terminal_dashboard import main

    sys.exit(main())
