"""Check translation coverage for all languages."""

from pathlib import Path

base_dir = Path(__file__).parent / "locales"

for lang in ["hi", "ur", "fa", "arc"]:
    po_file = base_dir / lang / "LC_MESSAGES" / "ccbt.po"
    if not po_file.exists():
        print(f"{lang}: File not found")
        continue

    with open(po_file, encoding="utf-8") as f:
        lines = f.readlines()

    # Count msgid entries (excluding header)
    msgids = [l for l in lines if l.startswith('msgid "') and l.strip() != 'msgid ""']
    total = len(msgids)

    # Count translated msgstr entries (non-empty)
    translated = 0
    i = 0
    while i < len(lines):
        if lines[i].startswith('msgid "') and lines[i].strip() != 'msgid ""':
            # Find corresponding msgstr
            i += 1
            while i < len(lines) and not lines[i].startswith("msgstr"):
                i += 1
            if i < len(lines):
                msgstr_line = lines[i].strip()
                # Check if it's not empty (excluding header)
                if msgstr_line != 'msgstr ""':
                    # Check if there's actual content
                    # Collect all msgstr lines
                    content = msgstr_line
                    j = i + 1
                    while j < len(lines) and (
                        lines[j].strip().startswith('"') or lines[j].strip() == ""
                    ):
                        if lines[j].strip().startswith('"'):
                            content += lines[j].strip()
                        j += 1
                        if j < len(lines) and lines[j].strip() == "":
                            break
                    # Check if content has actual translation (more than just quotes)
                    if len(content) > 12:  # More than just 'msgstr ""'
                        # Extract the actual string content
                        if '"' in content and content.count('"') >= 2:
                            translated += 1
        i += 1

    percentage = (translated * 100 // total) if total > 0 else 0
    print(f"{lang}: {translated}/{total} ({percentage}%)")
