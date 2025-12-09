"""Compile all .po files to .mo files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def compile_po_to_mo(po_path: Path, mo_path: Path) -> bool:
    """Compile a .po file to .mo file using Python gettext or msgfmt.

    Args:
        po_path: Path to .po file
        mo_path: Path to output .mo file

    Returns:
        True if successful, False otherwise

    """
    try:
        # Try using msgfmt first (if available)
        result = subprocess.run(
            ["msgfmt", str(po_path), "-o", str(mo_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass

    # Fallback: Use Python's gettext to compile
    try:
        import gettext

        # Read .po file and create .mo file
        # Note: This is a placeholder - proper .mo compilation requires msgfmt or polib
        # The file is read but not processed in this simplified implementation
        with open(po_path, "rb") as _:
            pass

        # Parse .po file manually and create .mo
        # This is a simplified version - for full support, use polib or msgfmt
        # Translation object is created but not used in this simplified implementation
        _ = gettext.translation(
            "ccbt",
            localedir=str(po_path.parent.parent.parent),
            languages=[po_path.parent.parent.name],
            fallback=False,
        )

        # Write .mo file (simplified - gettext.translation loads from .mo, not creates it)
        # For proper .mo creation, we need msgfmt or polib
        print(f"Warning: msgfmt not found. Cannot compile {po_path.name} to .mo")
        print(f"Please install gettext tools or use: msgfmt {po_path} -o {mo_path}")
        return False
    except Exception as e:
        print(f"Error compiling {po_path}: {e}")
        return False


def compile_all() -> None:
    """Compile all .po files in locales directory."""
    base_dir = Path(__file__).parent.parent / "locales"

    if not base_dir.exists():
        print(f"Locales directory not found: {base_dir}")
        sys.exit(1)

    compiled = 0
    failed = 0

    for lang_dir in base_dir.iterdir():
        if not lang_dir.is_dir() or lang_dir.name.startswith("."):
            continue

        po_file = lang_dir / "LC_MESSAGES" / "ccbt.po"
        mo_file = lang_dir / "LC_MESSAGES" / "ccbt.mo"

        if not po_file.exists():
            continue

        print(f"Compiling {lang_dir.name}...")
        if compile_po_to_mo(po_file, mo_file):
            print(f"  [OK] Compiled {mo_file.name}")
            compiled += 1
        else:
            print(f"  [ERROR] Failed to compile {po_file.name}")
            failed += 1

    print(f"\nCompiled: {compiled}, Failed: {failed}")
    if failed > 0:
        print("\nNote: Install gettext tools for .mo compilation:")
        print(
            "  - Windows: Install gettext from https://mlocati.github.io/articles/gettext-iconv-windows.html"
        )
        print("  - Linux: sudo apt-get install gettext")
        print("  - macOS: brew install gettext")


if __name__ == "__main__":
    compile_all()
