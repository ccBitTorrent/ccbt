"""Extract translatable strings from codebase."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from rich.console import Console


def extract_strings_from_file(file_path: Path) -> list[str]:
    """Extract translatable strings from a Python file.

    Args:
        file_path: Path to Python file

    Returns:
        List of translatable strings

    """
    strings: list[str] = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)

        for node in ast.walk(tree):
            # Find _("...") calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "_":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        strings.append(node.args[0].value)
    except Exception:
        pass

    return strings


def generate_pot_template(source_dir: Path, output_file: Path) -> None:
    """Generate .pot template file from source code.

    Args:
        source_dir: Source directory to scan
        output_file: Output .pot file path

    """
    all_strings: set[str] = set()

    # Find all Python files
    for py_file in source_dir.rglob("*.py"):
        # Skip i18n directory and test files
        if "i18n" in str(py_file) or "test" in str(py_file):
            continue
        strings = extract_strings_from_file(py_file)
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
    import sys

    # Setup basic logging for script
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    console = Console()

    if len(sys.argv) < 2:
        console.print(
            "[red]Error:[/red] Usage: uv run extract.py <source_dir> [output_file]"
        )
        sys.exit(1)

    source_dir = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else source_dir / "ccbt.pot"

    generate_pot_template(source_dir, output_file)
    console.print(f"[green]✓[/green] Generated {output_file} with translatable strings")
