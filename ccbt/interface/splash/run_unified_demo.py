"""Standalone entry point for unified_demo to avoid import issues.

Run this directly: python ccbt/interface/splash/run_unified_demo.py
"""

import sys
import os
from pathlib import Path

# Add the splash directory to path
splash_dir = Path(__file__).parent
if str(splash_dir) not in sys.path:
    sys.path.insert(0, str(splash_dir))

# Now import and run
from unified_demo import _main

if __name__ == "__main__":
    _main()


