"""Clear Python cache and verify imports."""
import importlib
import shutil
from pathlib import Path

# Clear __pycache__ directories
for pycache_dir in Path(".").rglob("__pycache__"):
    shutil.rmtree(pycache_dir, ignore_errors=True)
    print(f"Removed {pycache_dir}")

# Clear .pyc files
for pyc_file in Path(".").rglob("*.pyc"):
    pyc_file.unlink()
    print(f"Removed {pyc_file}")

# Invalidate import cache
importlib.invalidate_caches()

print("\nCache cleared. Testing import...")

# Test import
try:
    from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
    print("SUCCESS: daemon_session_adapter imports successfully")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"OTHER ERROR: {e}")
    import traceback
    traceback.print_exc()

