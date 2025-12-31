"""Fill English translations (msgstr = msgid)."""

from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console

po_file = Path(__file__).parent / "locales" / "en" / "LC_MESSAGES" / "ccbt.po"

with open(po_file, encoding="utf-8") as f:
    content = f.read()


# Replace empty msgstr with msgid value
def replace_empty_msgstr(match):
    """Replace empty msgstr with msgid value in .po files.

    Args:
        match: Regex match object containing the msgid

    Returns:
        Formatted string with msgid and msgstr set to the same value

    """
    msgid = match.group(1)
    return f'msgid "{msgid}"\nmsgstr "{msgid}"'


# Pattern to match msgid followed by empty msgstr
pattern = r'msgid "([^"]+)"\nmsgstr ""'
content = re.sub(pattern, replace_empty_msgstr, content)

with open(po_file, "w", encoding="utf-8") as f:
    f.write(content)

console = Console()
console.print(f"[green]✓[/green] Filled English translations in {po_file}")
