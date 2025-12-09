"""Quick launcher for the new splash screen demo.

Usage:
    python -m ccbt.interface.splash.run_demo
    python -m ccbt.interface.splash.run_demo --quick  # Shorter demos
"""

from __future__ import annotations

import asyncio
import sys

if __name__ == "__main__":
    from ccbt.interface.splash.demo_new_system import main
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)














