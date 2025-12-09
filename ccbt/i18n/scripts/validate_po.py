"""Validate .po file format."""

from __future__ import annotations

import re
from pathlib import Path


def validate_po_file(po_path: Path) -> tuple[bool, list[str]]:
    """Validate a .po file format.

    Args:
        po_path: Path to .po file

    Returns:
        Tuple of (is_valid, list_of_errors)

    """
    errors = []

    with open(po_path, encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    # Check for required header fields
    required_fields = [
        "Project-Id-Version",
        "Language",
        "Content-Type",
    ]

    for field in required_fields:
        if field not in content:
            errors.append(f"Missing required header field: {field}")

    # Check for valid msgid/msgstr pairs
    msgid_pattern = re.compile(r'^msgid\s+"')
    msgstr_pattern = re.compile(r'^msgstr\s+"')

    i = 0
    in_msgid = False
    in_msgstr = False

    while i < len(lines):
        line = lines[i].strip()

        if msgid_pattern.match(line):
            if in_msgid:
                errors.append(f"Line {i + 1}: Nested msgid found")
            in_msgid = True
            in_msgstr = False
        elif msgstr_pattern.match(line):
            if not in_msgid:
                errors.append(f"Line {i + 1}: msgstr without msgid")
            in_msgstr = True
            in_msgid = False
        elif line == "":
            in_msgid = False
            in_msgstr = False

        i += 1

    # Check for unclosed strings
    quote_count = content.count('"') - content.count('\\"')
    if quote_count % 2 != 0:
        errors.append("Unclosed string quotes detected")

    return len(errors) == 0, errors


def validate_all() -> int:
    """Validate all .po files.
    
    Returns:
        0 if all files are valid, 1 if any have errors
    """
    base_dir = Path(__file__).parent.parent / "locales"

    if not base_dir.exists():
        print(f"Locales directory not found: {base_dir}")
        return 1

    print("PO File Validation\n" + "=" * 50)

    all_valid = True

    for lang_dir in sorted(base_dir.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name.startswith("."):
            continue

        po_file = lang_dir / "LC_MESSAGES" / "ccbt.po"

        if not po_file.exists():
            continue

        is_valid, errors = validate_po_file(po_file)

        print(f"\n{lang_dir.name.upper()}:")
        if is_valid:
            print("  [OK] Valid")
        else:
            print("  [ERROR] Invalid")
            all_valid = False
            for error in errors:
                print(f"    - {error}")

    if all_valid:
        print("\n[OK] All .po files are valid")
        return 0
    print("\n[ERROR] Some .po files have errors")
    return 1


if __name__ == "__main__":
    exit(validate_all())
