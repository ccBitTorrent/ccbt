"""Optional .env file loading before configuration reads os.environ.

The process environment is the only source ``ConfigManager`` uses (see
``ccbt.config.config.ConfigManager._get_env_config``). A ``.env`` file on disk is
not loaded unless the launcher sets ``CCBT_LOAD_DOTENV=1`` (or ``true``/``yes``/``on``)
so existing deployments are unchanged.

``CCBT_DOTENV_PATH`` may point to an alternate file; otherwise ``.env`` in the
current working directory is used. Variables already set in ``os.environ`` are
not overwritten (standard dotenv behavior).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_LOAD_DOTENV_FLAG = "CCBT_LOAD_DOTENV"
_DOTENV_PATH_VAR = "CCBT_DOTENV_PATH"


def _truthy_env(raw: Optional[str]) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _strip_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def _strip_inline_comment_suffix(text: str) -> str:
    """Drop trailing comment after whitespace+``#`` (same rule as shell / python-dotenv)."""
    s = text
    i = 0
    while True:
        idx = s.find("#", i)
        if idx == -1:
            return s
        if idx > 0 and s[idx - 1].isspace():
            return s[: idx - 1].rstrip()
        i = idx + 1


def _parse_dotenv_value(rest: str) -> str:
    """Parse the RHS of ``KEY=...``: quotes, then strip trailing `` # comment``."""
    s = rest.strip()
    if not s:
        return ""
    if s.startswith("#"):
        return ""
    q = s[0]
    if q in "\"'":
        i = 1
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s):
                i += 2
                continue
            if s[i] == q:
                inner = s[1:i]
                tail = s[i + 1 :].strip()
                if not tail or tail.startswith("#"):
                    return inner
                return inner
            i += 1
        # Unclosed quote: best-effort like unquoted
    return _strip_quotes(_strip_inline_comment_suffix(s))


def _parse_dotenv_line(line: str) -> Optional[tuple[str, str]]:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if s.lower().startswith("export "):
        s = s[7:].lstrip()
    if "=" not in s:
        return None
    key, _, rest = s.partition("=")
    key = key.strip()
    if not key or not all(c.isalnum() or c == "_" for c in key):
        return None
    return key, _parse_dotenv_value(rest)


def load_dotenv_file(path: Path) -> int:
    """Load KEY=VALUE pairs from path into os.environ if keys are unset.

    Returns:
        Number of variables set (not counting skipped existing keys).

    """
    if not path.is_file():
        logger.debug("Dotenv file not found or not a file: %s", path)
        return 0

    count = 0
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.debug("Could not read dotenv file %s: %s", path, e)
        return 0

    for line in text.splitlines():
        parsed = _parse_dotenv_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if key in os.environ:
            continue
        os.environ[key] = value
        count += 1
    return count


def maybe_load_dotenv_from_env() -> None:
    """If ``CCBT_LOAD_DOTENV`` is truthy, merge ``.env`` into the process environment."""
    raw_flag = os.getenv(_LOAD_DOTENV_FLAG)
    if not _truthy_env(raw_flag):
        os.environ.setdefault("CCBT_DOTENV_LOADED", "0")
        logger.debug(
            "Skipping dotenv load: %s is not truthy (value=%r)",
            _LOAD_DOTENV_FLAG,
            raw_flag,
        )
        return

    raw_path = os.getenv(_DOTENV_PATH_VAR)
    path = Path(raw_path).expanduser() if raw_path else Path.cwd() / ".env"
    n = load_dotenv_file(path)
    os.environ["CCBT_DOTENV_LOADED"] = "1"
    os.environ["CCBT_DOTENV_PATH_EFFECTIVE"] = str(path)
    os.environ["CCBT_DOTENV_KEYS_LOADED"] = str(int(n))
    logger.debug(
        "Loaded %d variable(s) from dotenv (path=%s, CCBT_LOAD_DOTENV set)",
        n,
        path,
    )
