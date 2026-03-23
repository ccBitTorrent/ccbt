"""Complete translation workflow script.

This script orchestrates the entire translation workflow:
1. Extract strings from codebase
2. Merge the English template (.pot) into each locale's ccbt.po via GNU msgmerge
3. Check completeness
4. Validate .po files
5. Compile .mo files
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def run_script(script_name: str, *args: str) -> bool:
    """Run a Python script and return success status."""
    script_path = Path(__file__).parent / script_name

    if not script_path.exists():
        print(f"✗ Script not found: {script_path}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + list(args),
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error running {script_name}:")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        return False


def workflow_extract() -> bool:
    """Step 1: Extract strings from codebase."""
    print("\n" + "=" * 70)
    print("STEP 1: Extract translatable strings")
    print("=" * 70)

    base_dir = Path(__file__).parent.parent.parent.parent
    extract_script = Path(__file__).parent.parent / "extract.py"
    pot_file = (
        Path(__file__).parent.parent / "locales" / "en" / "LC_MESSAGES" / "ccbt.pot"
    )

    try:
        subprocess.run(
            [
                sys.executable,
                str(extract_script),
                str(base_dir / "ccbt"),
                str(pot_file),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print("✓ Strings extracted successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Extraction failed: {e}")
        return False


def workflow_update() -> bool:
    """Step 2: Merge template (.pot) into each locale catalog using msgmerge."""
    print("\n" + "=" * 70)
    print("STEP 2: Merge template into locale catalogs (msgmerge)")
    print("=" * 70)

    locales_root = Path(__file__).resolve().parent.parent / "locales"
    pot_path = locales_root / "en" / "LC_MESSAGES" / "ccbt.pot"

    msgmerge = shutil.which("msgmerge")
    if not msgmerge:
        print(
            "✗ msgmerge not found on PATH. Install GNU gettext, for example:\n"
            "  Linux: sudo apt install gettext\n"
            "  macOS: brew install gettext\n"
            "  Windows: install gettext binaries or use WSL"
        )
        return False

    if not pot_path.is_file():
        print(f"✗ POT file not found: {pot_path}")
        print("  Run extract first: python -m ccbt.i18n.scripts.translation_workflow --step extract")
        return False

    po_paths = sorted(locales_root.glob("*/LC_MESSAGES/ccbt.po"))
    if not po_paths:
        print(f"✗ No ccbt.po files under {locales_root}")
        return False

    merged_langs: list[str] = []
    for po_path in po_paths:
        try:
            subprocess.run(
                [
                    msgmerge,
                    "--update",
                    "--backup=none",
                    "--sort-output",
                    str(po_path),
                    str(pot_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"✗ msgmerge failed for {po_path}:")
            if e.stdout:
                print(e.stdout)
            if e.stderr:
                print(e.stderr)
            return False
        merged_langs.append(po_path.parent.parent.name)

    print(f"✓ Merged POT into locales: {', '.join(merged_langs)}")
    return True


def workflow_check() -> bool:
    """Step 3: Check completeness."""
    print("\n" + "=" * 70)
    print("STEP 3: Check translation completeness")
    print("=" * 70)

    return run_script("check_completeness.py")


def workflow_validate() -> bool:
    """Step 4: Validate .po files."""
    print("\n" + "=" * 70)
    print("STEP 4: Validate .po files")
    print("=" * 70)

    return run_script("validate_po.py")


def workflow_compile() -> bool:
    """Step 5: Compile .mo files."""
    print("\n" + "=" * 70)
    print("STEP 5: Compile .mo files")
    print("=" * 70)

    return run_script("compile_all.py")


def full_workflow(skip_extract: bool = False) -> None:
    """Run the complete translation workflow."""
    print("\n" + "=" * 70)
    print("TRANSLATION WORKFLOW")
    print("=" * 70)

    steps = []

    if not skip_extract:
        steps.append(("Extract", workflow_extract))

    steps.extend(
        [
            ("Update", workflow_update),
            ("Check", workflow_check),
            ("Validate", workflow_validate),
            ("Compile", workflow_compile),
        ]
    )

    results = {}

    for step_name, step_func in steps:
        success = step_func()
        results[step_name] = success
        if not success:
            print(f"\n⚠️  {step_name} step failed. Continuing anyway...")

    # Summary
    print("\n" + "=" * 70)
    print("WORKFLOW SUMMARY")
    print("=" * 70)

    for step_name, success in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {step_name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n✓ All steps completed successfully!")
    else:
        print("\n⚠️  Some steps failed. Please review the output above.")

    print("\nNext steps:")
    print(
        "  1. Review untranslated strings: python -m ccbt.i18n.scripts.check_completeness"
    )
    print("  2. Translate missing strings in .po files")
    print("  3. Run workflow again to validate and compile")


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Complete translation workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full workflow
  python -m ccbt.i18n.scripts.translation_workflow

  # Skip extraction (if .pot is already up to date)
  python -m ccbt.i18n.scripts.translation_workflow --skip-extract

  # Run specific step
  python -m ccbt.i18n.scripts.translation_workflow --step check
        """,
    )

    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Skip string extraction step",
    )

    parser.add_argument(
        "--step",
        choices=["extract", "update", "check", "validate", "compile"],
        help="Run only a specific step",
    )

    args = parser.parse_args()

    if args.step:
        step_map = {
            "extract": workflow_extract,
            "update": workflow_update,
            "check": workflow_check,
            "validate": workflow_validate,
            "compile": workflow_compile,
        }
        step_func = step_map[args.step]
        success = step_func()
        sys.exit(0 if success else 1)
    else:
        full_workflow(skip_extract=args.skip_extract)


if __name__ == "__main__":
    main()
