"""Generate docs/en/xet-support-matrix.md from the claim registry."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "dev" / "xet-claim-registry.yaml"
OUT = ROOT / "docs" / "en" / "xet-support-matrix.md"


def main() -> int:
    try:
        import yaml
    except ImportError:
        print("pyyaml required", file=sys.stderr)
        return 2
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    claims = list(data.get("claims") or [])
    statuses = {str(c.get("status")) for c in claims}
    if statuses == {"supported"}:
        status_line = "Every row is **supported** (big-bang gate G9 passed)."
    elif statuses == {"experimental"}:
        status_line = "Until big-bang release, every row is **experimental**."
    else:
        status_line = "Mixed claim statuses; see the Status column per row."
    lines = [
        "# XET support matrix",
        "",
        "Generated from `dev/xet-claim-registry.yaml`. Do not edit by hand.",
        status_line,
        "",
        "| Claim | Gate | Status | Owner | Tests |",
        "|-------|------|--------|-------|-------|",
    ]
    for c in claims:
        tests = ", ".join(f"`{t}`" for t in (c.get("test_ids") or []))
        lines.append(
            f"| {c.get('id')}: {c.get('claim')} | {c.get('gate')} | "
            f"**{c.get('status')}** | `{c.get('owner_module')}` | {tests} |"
        )
    lines.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
