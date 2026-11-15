"""Rewrite `raise X(f"...")` / `raise X("...")` to assign msg first (EM101/EM102/TRY003)."""

from __future__ import annotations

import re
from pathlib import Path

FILES = [
    Path("ccbt/discovery/xet_cas_http.py"),
]

# raise Foo(f"...") or raise Foo("...")
PATTERN = re.compile(
    r"^(\s*)raise ([A-Za-z_][A-Za-z0-9_]*)\((f?\".*?\"|f?'.*?')(, status=\d+)?\)(.*)$"
)


def main() -> None:
    for path in FILES:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        out: list[str] = []
        changed = 0
        for line in lines:
            m = PATTERN.match(line.rstrip("\n\r"))
            if not m:
                out.append(line)
                continue
            indent, exc, literal, status, trail = m.groups()
            status = status or ""
            trail = trail or ""
            # Skip already-msg pattern
            if "msg =" in line:
                out.append(line)
                continue
            out.append(f"{indent}msg = {literal}\n")
            out.append(f"{indent}raise {exc}(msg{status}){trail}\n")
            changed += 1
        path.write_text("".join(out), encoding="utf-8")
        print(f"{path}: {changed} raises rewritten")


if __name__ == "__main__":
    main()
