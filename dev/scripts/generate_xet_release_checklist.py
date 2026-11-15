"""Generate the big-bang XET release checklist from the claim registry."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "dev" / "xet-claim-registry.yaml"
OUT = ROOT / "dev" / "xet-release-checklist.md"


def main() -> int:
    try:
        import yaml
    except ImportError:
        print("pyyaml required", file=sys.stderr)
        return 2
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    claims = list(data.get("claims") or [])
    lines = [
        "# XET big-bang release checklist",
        "",
        f"Generated from `{REGISTRY.relative_to(ROOT)}`.",
        "Every claim must be `supported` with passing `test_ids` before release.",
        "",
        "| ID | Gate | Status | Claim | Tests |",
        "|----|------|--------|-------|-------|",
    ]
    for c in claims:
        tests = ", ".join(f"`{t}`" for t in (c.get("test_ids") or []))
        lines.append(
            f"| {c.get('id')} | {c.get('gate')} | {c.get('status')} | "
            f"{c.get('claim')} | {tests} |"
        )
    lines.extend(
        [
            "",
            "## Gate commands",
            "",
            "```bash",
            "python dev/scripts/check_xet_claims.py",
            "python dev/scripts/check_xet_claims.py --release",
            "pytest -c dev/pytest.ini tests/unit/storage/test_xet_golden_codec.py "
            "tests/integration/xet_e2e tests/unit/session/test_xet_transport.py "
            "tests/unit/consensus/test_consensus_raft_byzantine.py",
            "```",
            "",
        ]
    )
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
