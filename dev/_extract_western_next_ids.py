"""One-off: list next 450 msgids after shortest-950 (for western manual extension)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_msgids(po_path: Path) -> list[str]:
    text = po_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    in_header = True
    while i < len(lines):
        line = lines[i]
        if in_header and line.startswith('msgid ""'):
            i += 1
            while i < len(lines) and (lines[i].startswith('"') or lines[i] == ""):
                i += 1
            if i < len(lines) and lines[i].startswith('msgstr "'):
                i += 1
                while i < len(lines) and lines[i].startswith('"'):
                    i += 1
            in_header = False
            continue
        if not line.startswith('msgid "'):
            i += 1
            continue
        if line == 'msgid ""':
            msgid_parts = [""]
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                content = lines[i][1:-1] if lines[i].endswith('"') else lines[i][1:]
                msgid_parts.append(
                    content.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
                )
                i += 1
            msgid = "".join(msgid_parts)
        else:
            raw = line[7:-1].replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                content = lines[i][1:-1] if lines[i].endswith('"') else lines[i][1:]
                raw += content.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
                i += 1
            msgid = raw
        if i < len(lines) and lines[i].startswith('msgstr "'):
            if lines[i] == 'msgstr ""':
                i += 1
                while i < len(lines) and lines[i].startswith('"'):
                    i += 1
            else:
                i += 1
                while i < len(lines) and lines[i].startswith('"'):
                    i += 1
        else:
            i += 1
        out.append(msgid)
    return out


def main() -> None:
    from ccbt.i18n.locale_data.western900_loader import iter_western900_quads

    po = ROOT / "ccbt/i18n/locales/en/LC_MESSAGES/ccbt.po"
    msgids = parse_msgids(po)
    seen: set[str] = set()
    ordered_unique: list[str] = []
    for m in msgids:
        if m not in seen:
            seen.add(m)
            ordered_unique.append(m)
    by_len = sorted(ordered_unique, key=lambda x: (len(x), x))
    w9 = [q[0] for q in iter_western900_quads()]
    covered = set(w9)
    remaining = [m for m in by_len if m not in covered]
    next450 = remaining[:450]
    print("unique msgids", len(by_len), "western900", len(w9), "remaining after cover", len(remaining))
    print("next chunk len", len(next450))
    # write json slices 95*4 + 70
    chunks: list[list[str]] = []
    rest = list(next450)
    for _ in range(4):
        chunks.append(rest[:95])
        rest = rest[95:]
    chunks.append(rest[:70])
    assert sum(len(c) for c in chunks) == 450
    dev = ROOT / "dev"
    for idx, ch in enumerate(chunks, start=11):
        path = dev / f"_w9_ids_ts_{idx:02d}.json"
        path.write_text(json.dumps(ch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("wrote", path.name, len(ch))
    targets = dev / "_i18n_manual_targets.txt"
    cur = [ln.strip() for ln in targets.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if cur[: len(w9)] != w9:
        print("WARNING manual targets prefix != western900 keys")
    extended = w9 + next450
    targets.write_text("\n".join(extended) + "\n", encoding="utf-8")
    print("updated _i18n_manual_targets.txt lines", len(extended))


if __name__ == "__main__":
    main()
