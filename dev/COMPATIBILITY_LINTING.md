# Python 3.8/3.9 Compatibility Linting

This document describes the compatibility linting rules integrated into the ccBitTorrent project to ensure Python 3.8 and 3.9 compatibility.

## Overview

The compatibility linter enforces design patterns from [`compatibility_tests/COMPREHENSIVE_RESOLUTION_PLAN.md`](../compatibility_tests/COMPREHENSIVE_RESOLUTION_PLAN.md) to prevent Python 3.10+ syntax from being introduced into the codebase.

## Linting Tools

### 1. Custom Compatibility Linter

**Location**: [`dev/compatibility_linter.py`](compatibility_linter.py)

A custom Python script that checks for:
- **Union type syntax (`|`)**: Detects `type | None` and `type1 | type2` patterns
- **Built-in generic types**: Detects `tuple[...]`, `list[...]`, `dict[...]`, `set[...]` without `from __future__ import annotations`

**Usage**:
```bash
# Check all files in ccbt/
uv run python dev/compatibility_linter.py ccbt/

# Check specific files
uv run python dev/compatibility_linter.py ccbt/session/session.py

# JSON output
uv run python dev/compatibility_linter.py ccbt/ --format json
```

**Integration**: Automatically runs as part of pre-commit hooks (see [`dev/pre-commit-config.yaml`](pre-commit-config.yaml))

### 2. Ruff Configuration

**Location**: [`dev/ruff.toml`](ruff.toml)

Ruff is configured with:
- **Target Python version**: `py38` (ensures compatibility checks)
- **Ignored rules**: `UP045` and `UP007` (which suggest using `|` syntax) are intentionally ignored to enforce compatibility

## Design Patterns Enforced

### Pattern 1: Union Type Syntax

**Invalid (Python 3.10+ only)**:
```python
def func(param: str | None = None) -> dict | None:
    pass

var: int | float = 1.0
```

**Valid (Python 3.8/3.9 compatible)**:
```python
from typing import Optional, Union

def func(param: Optional[str] = None) -> Optional[dict]:
    pass

var: Union[int, float] = 1.0
```

**Detection**: The compatibility linter detects union syntax (`|`) in:
- Function parameters: `param: type | None`
- Return types: `-> type | None`
- Variable annotations: `var: type | None`
- Type aliases: `TypeAlias = type | None`

### Pattern 2: Built-in Generic Types

**❌ Invalid (Python 3.8 without `__future__`)**:
```python
_PacketInfo = tuple[UTPPacket, float, int]
items: list[str] = []
mapping: dict[str, int] = {}
```

**Valid Option 1 (Recommended)**:
```python
from __future__ import annotations

_PacketInfo = tuple[UTPPacket, float, int]
items: list[str] = []
mapping: dict[str, int] = {}
```

**Valid Option 2 (Alternative)**:
```python
from typing import Tuple, List, Dict

_PacketInfo = Tuple[UTPPacket, float, int]
items: List[str] = []
mapping: Dict[str, int] = {}
```

**Detection**: The compatibility linter detects built-in generic types (`tuple[...]`, `list[...]`, `dict[...]`, `set[...]`) and checks if `from __future__ import annotations` is present in the first 20 lines of the file.

## Issue Types

The compatibility linter reports issues with the following types:

1. **`union-syntax-param`**: Union syntax in function parameter
2. **`union-syntax-return`**: Union syntax in return type
3. **`union-syntax-var`**: Union syntax in variable annotation
4. **`union-syntax-alias`**: Union syntax in type alias
5. **`builtin-generic-tuple`**: `tuple[...]` without `__future__` import
6. **`builtin-generic-list`**: `list[...]` without `__future__` import
7. **`builtin-generic-dict`**: `dict[...]` without `__future__` import
8. **`builtin-generic-set`**: `set[...]` without `__future__` import

## Integration

### Pre-commit Hooks

The compatibility linter runs automatically before commits via pre-commit hooks:

```yaml
- id: compatibility-linter
  name: compatibility-linter
  entry: uv run python dev/compatibility_linter.py ccbt/
  language: system
  types: [python]
  files: ^ccbt/.*\.py$
```

### CI/CD Pipeline

The compatibility linter should be integrated into CI/CD pipelines to catch issues before merging. Add to `.github/workflows/ci.yml`:

```yaml
- name: Check Python 3.8/3.9 compatibility
  run: |
    uv run python dev/compatibility_linter.py ccbt/
```

## Fixing Issues

### Automatic Fixes

Some issues can be fixed automatically:

1. **Union syntax**: Replace `type | None` with `Optional[type]`
2. **Complex unions**: Replace `A | B | C` with `Union[A, B, C]`
3. **Built-in generics**: Add `from __future__ import annotations` at the top of the file

### Manual Fixes

Complex cases may require manual review:
- Nested types: `dict[str, int | None]` → `dict[str, Optional[int]]`
- Type aliases with unions
- Context-specific type annotations

## Examples

### Example 1: Function with Union Type

**Before**:
```python
def get_value(key: str) -> str | None:
    return cache.get(key)
```

**After**:
```python
from typing import Optional

def get_value(key: str) -> Optional[str]:
    return cache.get(key)
```

### Example 2: Built-in Generic Type

**Before**:
```python
def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}
```

**After**:
```python
from __future__ import annotations

def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}
```

### Example 3: Complex Union

**Before**:
```python
def parse_value(value: str | int | float) -> str | None:
    try:
        return str(value)
    except Exception:
        return None
```

**After**:
```python
from typing import Optional, Union

def parse_value(value: Union[str, int, float]) -> Optional[str]:
    try:
        return str(value)
    except Exception:
        return None
```

## Related Documentation

- [`compatibility_tests/COMPREHENSIVE_RESOLUTION_PLAN.md`](../compatibility_tests/COMPREHENSIVE_RESOLUTION_PLAN.md) - Full compatibility resolution plan
- [`dev/ruff.toml`](ruff.toml) - Ruff linting configuration
- [`dev/pre-commit-config.yaml`](pre-commit-config.yaml) - Pre-commit hook configuration

## Troubleshooting

### False Positives

The linter may report false positives for:
- Bitwise OR operations (e.g., `flags | MASK`)
- String literals containing `|`
- Comments containing type annotations

These are filtered out automatically, but if you encounter issues, please report them.

### Performance

The linter processes files sequentially. For large codebases, consider:
- Running on specific directories: `uv run python dev/compatibility_linter.py ccbt/session/`
- Using JSON output for programmatic processing
- Excluding test files if not needed

## Contributing

When adding new compatibility checks:

1. Add the pattern to `dev/compatibility_linter.py`
2. Update this documentation
3. Test with existing codebase
4. Add to pre-commit hooks if appropriate

