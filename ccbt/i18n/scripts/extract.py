"""Extract translatable strings from codebase.

Enhanced to extract from multiple sources:
- _("...") calls (gettext)
- console.print() calls
- logger.*() calls
- Click help text
- print() calls
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from rich.console import Console

# Import comprehensive extraction
try:
    from ccbt.i18n.scripts.extract_comprehensive import extract_strings_from_file as extract_comprehensive_strings
except ImportError:
    # Fallback if comprehensive extraction not available
    extract_comprehensive_strings = None


def extract_strings_from_file(file_path: Path, comprehensive: bool = False) -> list[str]:
    """Extract translatable strings from a Python file.

    Args:
        file_path: Path to Python file
        comprehensive: If True, use comprehensive extraction (all string types)

    Returns:
        List of translatable strings

    """
    if comprehensive and extract_comprehensive_strings:
        # Use comprehensive extraction
        results = extract_comprehensive_strings(file_path)
        # Extract just the string values (deduplicate)
        strings = []
        seen = set()
        for s in results:
            if s.get("string") and s["string"] not in seen:
                strings.append(s["string"])
                seen.add(s["string"])
        return strings

    # Simple extraction (backward compatible)
    strings: list[str] = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)

        for node in ast.walk(tree):
            # Find _("...") calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "_":
                    if node.args:
                        # Handle both ast.Constant (Python 3.8+) and ast.Str (older)
                        if isinstance(node.args[0], ast.Constant):
                            strings.append(node.args[0].value)
                        elif isinstance(node.args[0], ast.Str):  # Python < 3.8
                            strings.append(node.args[0].s)
    except Exception:
        pass

    return strings


def generate_pot_template(
    source_dir: Path, output_file: Path, comprehensive: bool = False
) -> None:
    """Generate .pot template file from source code.

    Args:
        source_dir: Source directory to scan
        output_file: Output .pot file path
        comprehensive: If True, extract all user-facing strings (not just _() calls)

    """
    all_strings: set[str] = set()

    # Find all Python files
    # Scans all modules including: cli, session, daemon, executor, consensus, etc.
    for py_file in source_dir.rglob("*.py"):
        # Skip i18n directory and test files
        if "i18n" in str(py_file) or "test" in str(py_file):
            continue
        strings = extract_strings_from_file(py_file, comprehensive=comprehensive)
        all_strings.update(strings)

    # Generate .pot file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n\n')

        for msg in sorted(all_strings):
            # Escape quotes and newlines
            escaped_msg = (
                msg.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            )
            f.write(f'msgid "{escaped_msg}"\n')
            f.write('msgstr ""\n\n')


if __name__ == "__main__":
    import argparse
    import sys

    # Setup basic logging for script
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    console = Console()

    parser = argparse.ArgumentParser(
        description="Extract translatable strings from codebase"
    )
    parser.add_argument("source_dir", type=Path, help="Source directory to scan")
    parser.add_argument(
        "output_file",
        nargs="?",
        type=Path,
        help="Output .pot file path (default: source_dir/ccbt.pot)",
    )
    parser.add_argument(
        "--comprehensive",
        "-c",
        action="store_true",
        help="Extract all user-facing strings (not just _() calls)",
    )

    args = parser.parse_args()

    source_dir = args.source_dir
    output_file = args.output_file or source_dir / "ccbt.pot"

    if not source_dir.exists():
        console.print(f"[red]Error:[/red] Source directory not found: {source_dir}")
        sys.exit(1)

    console.print(
        f"[cyan]Extracting strings from {source_dir}...[/cyan] "
        f"({'comprehensive' if args.comprehensive else 'standard'} mode)"
    )
    generate_pot_template(source_dir, output_file, comprehensive=args.comprehensive)
    console.print(f"[green]✓[/green] Generated {output_file} with translatable strings")


    # Generate .pot file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n\n')

        for msg in sorted(all_strings):
            # Escape quotes and newlines
            escaped_msg = (
                msg.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            )
            f.write(f'msgid "{escaped_msg}"\n')
            f.write('msgstr ""\n\n')


if __name__ == "__main__":
    import argparse
    import sys

    # Setup basic logging for script
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    console = Console()

    parser = argparse.ArgumentParser(
        description="Extract translatable strings from codebase"
    )
    parser.add_argument("source_dir", type=Path, help="Source directory to scan")
    parser.add_argument(
        "output_file",
        nargs="?",
        type=Path,
        help="Output .pot file path (default: source_dir/ccbt.pot)",
    )
    parser.add_argument(
        "--comprehensive",
        "-c",
        action="store_true",
        help="Extract all user-facing strings (not just _() calls)",
    )

    args = parser.parse_args()

    source_dir = args.source_dir
    output_file = args.output_file or source_dir / "ccbt.pot"

    if not source_dir.exists():
        console.print(f"[red]Error:[/red] Source directory not found: {source_dir}")
        sys.exit(1)

    console.print(
        f"[cyan]Extracting strings from {source_dir}...[/cyan] "
        f"({'comprehensive' if args.comprehensive else 'standard'} mode)"
    )
    generate_pot_template(source_dir, output_file, comprehensive=args.comprehensive)
    console.print(f"[green]✓[/green] Generated {output_file} with translatable strings")
