"""Check the XET claim registry against docs and collected tests.

Usage:
    python dev/scripts/check_xet_claims.py [--release]

Default mode validates registry structure and reports ungated claims as
warnings. --release mode (the big-bang gate) additionally requires every
claim to be supported with test_ids that resolve to tests in tests/.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "dev" / "xet-claim-registry.yaml"
DEAD_LINK = "implementation-plans/xet-share-feature.md"


def _load_claims() -> list[dict]:
    try:
        import yaml
    except ImportError:
        print("pyyaml is required", file=sys.stderr)
        raise SystemExit(2) from None
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return list(data.get("claims") or [])


def _collected_test_names() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "tests").rglob("test_*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        names.update(re.findall(r"def (test_\w+)", text))
        names.update(re.findall(r"async def (test_\w+)", text))
    return names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()

    claims = _load_claims()
    errors: list[str] = []
    warnings: list[str] = []
    test_names = _collected_test_names()

    seen: set[str] = set()
    for claim in claims:
        cid = claim.get("id")
        if not cid or cid in seen:
            errors.append(f"duplicate or missing claim id: {cid}")
        seen.add(str(cid))
        for field in ("claim", "status", "owner_module", "gate", "test_ids"):
            if field not in claim:
                errors.append(f"{cid}: missing field {field}")
        owner = ROOT / str(claim.get("owner_module", ""))
        if not owner.exists():
            warnings.append(f"{cid}: owner_module does not exist yet: {claim.get('owner_module')}")
        missing = [t for t in claim.get("test_ids") or [] if t not in test_names]
        if claim.get("status") == "supported":
            if missing:
                errors.append(f"{cid}: supported but tests missing: {missing}")
        elif missing:
            warnings.append(f"{cid}: tests not yet present: {missing}")

    for doc in (ROOT / "docs" / "en").rglob("*.md"):
        text = doc.read_text(encoding="utf-8", errors="ignore")
        if DEAD_LINK in text:
            errors.append(f"dead link {DEAD_LINK} in {doc.relative_to(ROOT)}")

    if args.release:
        unsupported = [c["id"] for c in claims if c.get("status") != "supported"]
        if unsupported:
            errors.append(f"release gate: claims not supported: {unsupported}")

    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"claims={len(claims)} warnings={len(warnings)} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
