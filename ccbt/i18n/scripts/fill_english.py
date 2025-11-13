"""Fill English translations (msgstr = msgid)."""

import re
from pathlib import Path

po_file = Path(__file__).parent / "locales" / "en" / "LC_MESSAGES" / "ccbt.po"

with open(po_file, encoding="utf-8") as f:
    content = f.read()


# Replace empty msgstr with msgid value
def replace_empty_msgstr(match):
    msgid = match.group(1)
    return f'msgid "{msgid}"\nmsgstr "{msgid}"'


# Pattern to match msgid followed by empty msgstr
pattern = r'msgid "([^"]+)"\nmsgstr ""'
content = re.sub(pattern, replace_empty_msgstr, content)

with open(po_file, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Filled English translations in {po_file}")
