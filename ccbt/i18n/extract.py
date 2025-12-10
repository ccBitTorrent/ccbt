"""Extract translatable strings from codebase.

Supports both simple extraction (_() calls only) and comprehensive extraction
(all user-facing strings from console.print, logger, Click help, etc.).
"""

from __future__ import annotations

import ast
from pathlib import Path


def extract_strings_from_file(file_path: Path, comprehensive: bool = False) -> list[str]:
    """Extract translatable strings from a Python file.

    Args:
        file_path: Path to Python file
        comprehensive: If True, use comprehensive extraction (all string types)

    Returns:
        List of translatable strings

    """
    if comprehensive:
        # Use comprehensive extraction
        try:
            from ccbt.i18n.scripts.extract_comprehensive import extract_strings_from_file as extract_comprehensive_strings

            results = extract_comprehensive_strings(file_path)
            # Extract just the string values (deduplicate)
            strings = []
            seen = set()
            for s in results:
                if s.get("string") and s["string"] not in seen:
                    strings.append(s["string"])
                    seen.add(s["string"])
            return strings
        except ImportError:
            # Fallback to simple extraction if comprehensive not available
            pass

    # Simple extraction (backward compatible) - only _() calls
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
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
        f.write('"Language: \\n"\n')
        f.write('"MIME-Version: 1.0\\n"\n')
        f.write('"Content-Transfer-Encoding: 8bit\\n"\n\n')

        for msg in sorted(all_strings):
            # Escape quotes and newlines
            escaped_msg = (
                msg.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            )
            f.write(f'msgid "{escaped_msg}"\n')
            f.write('msgstr ""\n\n')


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: uv run extract.py <source_dir> [output_file] [--comprehensive]")
        print("  --comprehensive: Extract all user-facing strings (not just _() calls)")
        sys.exit(1)

    source_dir = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else source_dir / "ccbt.pot"
    comprehensive = "--comprehensive" in sys.argv

    generate_pot_template(source_dir, output_file, comprehensive=comprehensive)
    mode = "comprehensive" if comprehensive else "simple"
    print(f"Generated {output_file} with translatable strings ({mode} mode)")
