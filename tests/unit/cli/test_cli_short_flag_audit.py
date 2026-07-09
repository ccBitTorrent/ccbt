"""AST audit: user-facing ``click.option`` long flags should declare a short alias."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ccbt.cli.cli_short_flag_exceptions import CLI_SHORT_FLAG_EXCEPTIONS

CLI_ROOT = Path(__file__).resolve().parents[3] / "ccbt" / "cli"
_MIN_SHORT_LEN = 2


def _primary_long_flag(first_arg: ast.expr) -> str | None:
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        raw = first_arg.value
        if "/" in raw:
            # e.g. ``--peers/--no-peers`` or ``-P/--peers/--no-peers``
            for part in raw.split("/"):
                if part.startswith("--"):
                    return part.split()[0] if " " in part else part
                if part.startswith("-") and not part.startswith("--"):
                    continue
            return None
        if raw.startswith("--"):
            return raw
    return None


def _has_short_option(call: ast.Call) -> bool:
    if call.args:
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            raw = first.value
            if "/" in raw:
                lead = raw.split("/")[0]
                if (
                    lead.startswith("-")
                    and not lead.startswith("--")
                    and len(lead) >= _MIN_SHORT_LEN
                ):
                    return True
    for arg in call.args[1:]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            s = arg.value
            if (
                len(s) >= _MIN_SHORT_LEN
                and s.startswith("-")
                and not s.startswith("--")
            ):
                return True
    return False


def _is_click_option_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "option":
        if isinstance(func.value, ast.Name) and func.value.id == "click":
            return True
        if (
            isinstance(func.value, ast.Attribute)
            and func.value.attr == "click"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "click"
        ):
            return True
    return False


def _scan_file(path: Path) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_click_option_call(node):
            continue
        if not node.args:
            continue
        primary = _primary_long_flag(node.args[0])
        if primary is None:
            continue
        if primary in CLI_SHORT_FLAG_EXCEPTIONS:
            continue
        if _has_short_option(node):
            continue
        violations.append((node.lineno, primary))
    return violations


@pytest.mark.unit
def test_cli_click_options_have_short_or_exemption() -> None:
    """Fail if any ``click.option`` exposes ``--long`` without a short or exemption."""
    all_violations: list[str] = []
    for path in sorted(CLI_ROOT.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        for lineno, flag in _scan_file(path):
            rel = path.relative_to(CLI_ROOT.parent.parent)
            all_violations.append(f"{rel}:{lineno}: {flag} missing short alias")
    if all_violations:
        msg = (
            "Long-only click.option declarations:\n"
            + "\n".join(all_violations)
            + "\n\nAdd a short flag or extend CLI_SHORT_FLAG_EXCEPTIONS "
            "with justification."
        )
        pytest.fail(msg)
