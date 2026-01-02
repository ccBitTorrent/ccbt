#!/usr/bin/env python3
"""
Compatibility Linter for Python 3.8/3.9 Compatibility.

This script checks for Python 3.8/3.9 compatibility issues:
1. Union type syntax (`|`) - should use `Optional` or `Union` instead
2. Built-in generic types without `__future__` import - requires `from __future__ import annotations` for Python 3.8
3. `tuple[...]` usage - should use `Tuple[...]` from typing for Python 3.8 compatibility
4. `tuple[...]` in type aliases - even with `__future__` import, type aliases are evaluated at runtime in Python 3.8
5. `Tuple[...]` usage without proper import from typing - must import `Tuple` from typing
6. Other compatibility patterns

Based on patterns from compatibility_tests/COMPREHENSIVE_RESOLUTION_PLAN.md and
compatibility_tests/PYTHON38_RESOLUTION_PLAN.md
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple, Optional


class CompatibilityIssue(NamedTuple):
    """Represents a compatibility issue found in code."""

    file_path: Path
    line_number: int
    issue_type: str
    message: str
    code: str


class CompatibilityLinter:
    """Linter for Python 3.8/3.9 compatibility issues."""

    def __init__(self, root_dir: Path) -> None:
        """Initialize the linter with root directory."""
        self.root_dir = root_dir
        self.issues: list[CompatibilityIssue] = []

    def check_file(self, file_path: Path) -> list[CompatibilityIssue]:
        """Check a single file for compatibility issues."""
        file_issues: list[CompatibilityIssue] = []

        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            # Check for __future__ import
            has_future_annotations = self._has_future_annotations(content)

            # Check for typing imports
            has_tuple_import = self._has_tuple_import(content)

            # Check each line
            for line_num, line in enumerate(lines, start=1):
                # Check for union syntax (|) in type annotations
                union_issues = self._check_union_syntax(
                    file_path, line_num, line, content
                )
                file_issues.extend(union_issues)

                # Check for built-in generics without __future__ import
                if not has_future_annotations:
                    generic_issues = self._check_builtin_generics(
                        file_path, line_num, line
                    )
                    file_issues.extend(generic_issues)

                # Check for tuple[...] usage (should use Tuple[...] for Python 3.8 compatibility)
                # Skip if file has __future__ import annotations (tuple[...] is compatible then)
                if not has_future_annotations:
                    tuple_issues = self._check_tuple_usage(
                        file_path, line_num, line
                    )
                    file_issues.extend(tuple_issues)

                # Check for tuple[...] in type aliases (even with __future__ import)
                # Type aliases are evaluated at runtime in Python 3.8, so they need Tuple from typing
                tuple_alias_issues = self._check_tuple_type_alias(
                    file_path, line_num, line
                )
                file_issues.extend(tuple_alias_issues)

                # Check for Tuple[...] usage without proper import
                if not has_tuple_import:
                    tuple_import_issues = self._check_tuple_import(
                        file_path, line_num, line
                    )
                    file_issues.extend(tuple_import_issues)

        except Exception as e:
            # Skip files that can't be read (binary, etc.)
            if "encoding" not in str(e).lower():
                print(f"Warning: Could not check {file_path}: {e}", file=sys.stderr)

        # Deduplicate issues: same line, same issue type, same code
        # This prevents reporting the same issue multiple times
        seen: set[tuple[int, str, str]] = set()
        deduplicated: list[CompatibilityIssue] = []
        for issue in file_issues:
            key = (issue.line_number, issue.issue_type, issue.code)
            if key not in seen:
                seen.add(key)
                deduplicated.append(issue)

        return deduplicated

    def _has_future_annotations(self, content: str) -> bool:
        """
        Check if file has `from __future__ import annotations`.
        
        The __future__ import must be at the top of the file (before any other imports
        or code, except for module docstrings and comments). We check the first 50 lines
        to allow for longer module docstrings and comments before the import.
        
        This method is more robust and handles various edge cases:
        - Multi-line docstrings
        - Comments before the import
        - Different quote styles
        - Case-insensitive matching
        """
        # Check first 50 lines for __future__ import
        # This allows for longer module docstrings and comments before the import
        lines = content.splitlines()[:50]
        in_docstring = False
        docstring_quote = None
        
        for line in lines:
            stripped = line.strip()
            
            # Handle docstrings (single or triple quotes)
            if not in_docstring:
                # Check for opening docstring
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    docstring_quote = stripped[:3]
                    in_docstring = True
                    # Check if it's a closing docstring on the same line
                    if stripped.count(docstring_quote) >= 2:
                        in_docstring = False
                        docstring_quote = None
                    continue
            else:
                # Inside docstring - check for closing
                if docstring_quote in line:
                    in_docstring = False
                    docstring_quote = None
                continue
            
            # Skip empty lines and comments (but not docstrings)
            if not stripped or stripped.startswith("#"):
                continue
            
            # Check for __future__ import (must be before other imports)
            # Match: from __future__ import annotations
            # Also match: from __future__ import annotations, other_stuff
            if re.search(r"from\s+__future__\s+import\s+.*\bannotations\b", line, re.IGNORECASE):
                return True
            
            # If we hit a non-__future__ import or executable code, stop checking
            # (__future__ imports must come before everything else)
            if stripped.startswith("import ") or (stripped.startswith("from ") and "__future__" not in stripped.lower()):
                # But allow shebang lines
                if not stripped.startswith("#!"):
                    break
        
        # Also do a full-file search as fallback (in case future import is later)
        # This handles edge cases where the import might be after some comments
        if re.search(r"from\s+__future__\s+import\s+.*\bannotations\b", content, re.IGNORECASE | re.MULTILINE):
            return True
        
        return False

    def _has_tuple_import(self, content: str) -> bool:
        """
        Check if file imports `Tuple` from typing.
        
        Checks for imports like:
        - `from typing import Tuple`
        - `from typing import TYPE_CHECKING, Optional, Tuple`
        - `from typing import Tuple as T` (also valid)
        """
        # Check for Tuple import from typing
        # Pattern matches: from typing import Tuple, from typing import ..., Tuple, ...
        patterns = [
            r"from\s+typing\s+import\s+.*\bTuple\b",  # from typing import Tuple or from typing import ..., Tuple
            r"from\s+typing\s+import\s+.*\bTuple\s+as\s+\w+",  # from typing import Tuple as T
        ]
        
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False

    def _check_union_syntax(
        self, file_path: Path, line_num: int, line: str, full_content: str
    ) -> list[CompatibilityIssue]:
        """Check for union syntax (`|`) in type annotations."""
        issues: list[CompatibilityIssue] = []

        # Skip if line is a comment or string
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            return issues

        # Check if union syntax is in a comment (after #)
        # Split line at # and only check the part before the comment
        if "#" in line:
            code_part = line.split("#")[0]
            # If the code part doesn't contain |, skip (it's only in the comment)
            if "|" not in code_part:
                return issues
        else:
            code_part = line

        # Skip if it's clearly a bitwise OR operation (not a type annotation)
        # Check if there are numbers or expressions that suggest bitwise operations
        if re.search(r'\d+\s*\|\s*\d+', code_part):  # Number | Number
            return issues

        # More comprehensive pattern to match union syntax in type annotations
        # This pattern matches: type | None, type | OtherType, type | list[str] | None, etc.
        # It captures the full union expression, not just the first part
        union_pattern = r"([a-zA-Z_][a-zA-Z0-9_.]*(?:\[[^\]]*\])?)\s*\|\s*([a-zA-Z_][a-zA-Z0-9_.]*(?:\[[^\]]*\])?|None)"
        
        # Check for union syntax in different contexts
        # Function parameters: `param: type | None` or `param: type | OtherType`
        param_match = re.search(r":\s*" + union_pattern, code_part)
        if param_match:
            # Check if it's in a function parameter context (not just any colon)
            before_colon = code_part[:param_match.start()]
            # Skip if it's in a dict literal or slice
            if not re.search(r'[\[\{]\s*$', before_colon.rstrip()):
                # Check if we're inside a string literal
                start_pos = param_match.start()
                before_match = code_part[:start_pos]
                single_quotes_before = before_match.count("'") - before_match.count("\\'")
                double_quotes_before = before_match.count('"') - before_match.count('\\"')
                
                if not ((single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1)):
                    issues.append(
                        CompatibilityIssue(
                            file_path=file_path,
                            line_number=line_num,
                            issue_type="union-syntax-param",
                            message="Union type syntax (`|`) in function parameter. Use `Optional[type]` or `Union[type1, type2]` for Python 3.8/3.9 compatibility",
                            code=line.strip(),
                        )
                    )

        # Return types: `-> type | None` or `-> type | OtherType`
        return_match = re.search(r"->\s*" + union_pattern, code_part)
        if return_match:
            start_pos = return_match.start()
            before_match = code_part[:start_pos]
            single_quotes_before = before_match.count("'") - before_match.count("\\'")
            double_quotes_before = before_match.count('"') - before_match.count('\\"')
            
            if not ((single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1)):
                issues.append(
                    CompatibilityIssue(
                        file_path=file_path,
                        line_number=line_num,
                        issue_type="union-syntax-return",
                        message="Union type syntax (`|`) in return type. Use `Optional[type]` or `Union[type1, type2]` for Python 3.8/3.9 compatibility",
                        code=line.strip(),
                    )
                )

        # Variable annotations: `var: type | None` (but not function parameters)
        # Only match if it's not already matched as a parameter
        if not param_match:
            var_match = re.search(r"^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*:\s*" + union_pattern, code_part)
            if var_match:
                start_pos = var_match.start()
                before_match = code_part[:start_pos]
                single_quotes_before = before_match.count("'") - before_match.count("\\'")
                double_quotes_before = before_match.count('"') - before_match.count('\\"')
                
                if not ((single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1)):
                    issues.append(
                        CompatibilityIssue(
                            file_path=file_path,
                            line_number=line_num,
                            issue_type="union-syntax-var",
                            message="Union type syntax (`|`) in variable annotation. Use `Optional[type]` or `Union[type1, type2]` for Python 3.8/3.9 compatibility",
                            code=line.strip(),
                        )
                    )

        # Type aliases: `TypeAlias = type | None` (but not variable assignments)
        # Only match if it's not already matched as a variable annotation
        if not param_match and not var_match:
            alias_match = re.search(r"=\s*" + union_pattern, code_part)
            if alias_match:
                # Check if it's a type alias (usually uppercase or has TypeAlias)
                before_equals = code_part[:alias_match.start()].rstrip()
                if re.search(r'[A-Z][a-zA-Z0-9_]*\s*$', before_equals) or 'TypeAlias' in before_equals:
                    start_pos = alias_match.start()
                    before_match = code_part[:start_pos]
                    single_quotes_before = before_match.count("'") - before_match.count("\\'")
                    double_quotes_before = before_match.count('"') - before_match.count('\\"')
                    
                    if not ((single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1)):
                        issues.append(
                            CompatibilityIssue(
                                file_path=file_path,
                                line_number=line_num,
                                issue_type="union-syntax-alias",
                                message="Union type syntax (`|`) in type alias. Use `Optional[type]` or `Union[type1, type2]` for Python 3.8/3.9 compatibility",
                                code=line.strip(),
                            )
                        )

        # Check for multi-union types (e.g., `str | list[str] | None`)
        # This is a more complex pattern that might span the union
        multi_union_pattern = r"([a-zA-Z_][a-zA-Z0-9_.]*(?:\[[^\]]*\])?)\s*\|\s*([a-zA-Z_][a-zA-Z0-9_.]*(?:\[[^\]]*\])?)\s*\|\s*(None|[a-zA-Z_][a-zA-Z0-9_.]*(?:\[[^\]]*\])?)"
        
        # Check in parameter context
        if not param_match:
            multi_param = re.search(r":\s*" + multi_union_pattern, code_part)
            if multi_param:
                start_pos = multi_param.start()
                before_match = code_part[:start_pos]
                single_quotes_before = before_match.count("'") - before_match.count("\\'")
                double_quotes_before = before_match.count('"') - before_match.count('\\"')
                
                if not ((single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1)):
                    issues.append(
                        CompatibilityIssue(
                            file_path=file_path,
                            line_number=line_num,
                            issue_type="union-syntax-param",
                            message="Union type syntax (`|`) in function parameter. Use `Union[type1, type2, type3]` for Python 3.8/3.9 compatibility",
                            code=line.strip(),
                        )
                    )

        # Check in return context
        if not return_match:
            multi_return = re.search(r"->\s*" + multi_union_pattern, code_part)
            if multi_return:
                start_pos = multi_return.start()
                before_match = code_part[:start_pos]
                single_quotes_before = before_match.count("'") - before_match.count("\\'")
                double_quotes_before = before_match.count('"') - before_match.count('\\"')
                
                if not ((single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1)):
                    issues.append(
                        CompatibilityIssue(
                            file_path=file_path,
                            line_number=line_num,
                            issue_type="union-syntax-return",
                            message="Union type syntax (`|`) in return type. Use `Union[type1, type2, type3]` for Python 3.8/3.9 compatibility",
                            code=line.strip(),
                        )
                    )

        return issues

    def _check_builtin_generics(
        self, file_path: Path, line_num: int, line: str
    ) -> list[CompatibilityIssue]:
        """
        Check for built-in generic types without __future__ import.
        
        Python 3.8 requires `from __future__ import annotations` to use built-in
        generic syntax like `tuple[...]`, `list[...]`, `dict[...]`, `set[...]`.
        Python 3.9+ supports these natively, but for 3.8 compatibility, we
        must either use the __future__ import or use typing.Tuple, typing.List, etc.
        
        This check only runs if the file doesn't have the __future__ import.
        """
        issues: list[CompatibilityIssue] = []

        # Pattern to match built-in generic types: tuple[...], list[...], dict[...], set[...]
        # Using word boundary (\b) to avoid false positives like "tuple_list" or "list_dict"
        patterns = [
            (
                r"\btuple\s*\[",
                "builtin-generic-tuple",
                "Built-in generic `tuple[...]` requires `from __future__ import annotations` for Python 3.8 compatibility. Add the import at the top of the file, or use `typing.Tuple` instead.",
            ),
            (
                r"\blist\s*\[",
                "builtin-generic-list",
                "Built-in generic `list[...]` requires `from __future__ import annotations` for Python 3.8 compatibility. Add the import at the top of the file, or use `typing.List` instead.",
            ),
            (
                r"\bdict\s*\[",
                "builtin-generic-dict",
                "Built-in generic `dict[...]` requires `from __future__ import annotations` for Python 3.8 compatibility. Add the import at the top of the file, or use `typing.Dict` instead.",
            ),
            (
                r"\bset\s*\[",
                "builtin-generic-set",
                "Built-in generic `set[...]` requires `from __future__ import annotations` for Python 3.8 compatibility. Add the import at the top of the file, or use `typing.Set` instead.",
            ),
        ]

        # Skip if line is a comment or string
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            return issues

        # Skip if the pattern is inside a string literal
        # Check for quotes around the pattern
        for pattern, issue_type, message in patterns:
            matches = list(re.finditer(pattern, line))
            for match in matches:
                start_pos = match.start()
                end_pos = match.end()
                
                # Check if we're inside a string literal
                # Simple heuristic: count quotes before the match
                before_match = line[:start_pos]
                single_quotes_before = before_match.count("'") - before_match.count("\\'")
                double_quotes_before = before_match.count('"') - before_match.count('\\"')
                
                # If odd number of quotes, we're inside a string
                if (single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1):
                    continue  # Skip - it's inside a string literal
                
                # Also check for common string contexts like cast("...", ...)
                if re.search(r'(cast|typing\.cast)\s*\(', line[:start_pos]):
                    # Check if the match is within the string argument
                    # Look for the opening quote before the match
                    quote_match = re.search(r'["\']', line[max(0, start_pos-50):start_pos][::-1])
                    if quote_match:
                        continue  # Likely in a string argument
                
                issues.append(
                    CompatibilityIssue(
                        file_path=file_path,
                        line_number=line_num,
                        issue_type=issue_type,
                        message=message,
                        code=line.strip(),
                    )
                )

        return issues

    def _check_tuple_usage(
        self, file_path: Path, line_num: int, line: str
    ) -> list[CompatibilityIssue]:
        """
        Check for tuple[...] usage in type annotations.
        
        NOTE: This method is only called when the file does NOT have
        `from __future__ import annotations`. If the file has the future import,
        `tuple[...]` is compatible with Python 3.8/3.9 and this check is skipped.
        
        For Python 3.8 compatibility without the future import, we should use
        `Tuple[...]` from typing instead of `tuple[...]`.
        """
        issues: list[CompatibilityIssue] = []

        # Pattern to match tuple[...] in type annotations
        # Matches: tuple[type, ...], tuple[type1, type2], tuple[...]
        # Using word boundary (\b) to avoid false positives
        pattern = r"\btuple\s*\["

        # Skip if line is a comment or string
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            return issues

        # Skip if it's clearly not a type annotation (e.g., variable assignment, function call)
        # We want to catch: -> tuple[...], param: tuple[...], var: tuple[...]
        # But skip: my_tuple = tuple([...]), tuple([...])
        
        # Check if we're in a type annotation context
        # Look for common type annotation patterns: ->, :, or in type alias context
        is_type_annotation = (
            "->" in line or  # Return type
            re.search(r":\s*tuple\s*\[", line) or  # Parameter or variable annotation
            re.search(r"=\s*tuple\s*\[", line)  # Type alias (may be false positive, but check anyway)
        )

        if not is_type_annotation:
            # Could still be a type annotation in a complex context, so check for tuple[...]
            # but be more careful
            if not re.search(r"tuple\s*\[[^\]]+\]", line):
                return issues  # No tuple[...] found, skip

        matches = list(re.finditer(pattern, line))
        for match in matches:
            start_pos = match.start()
            
            # Check if we're inside a string literal
            before_match = line[:start_pos]
            single_quotes_before = before_match.count("'") - before_match.count("\\'")
            double_quotes_before = before_match.count('"') - before_match.count('\\"')
            
            # If odd number of quotes, we're inside a string
            if (single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1):
                continue  # Skip - it's inside a string literal
            
            # Additional check: skip if it's a function call like tuple([...])
            # Look for tuple( after the match (not tuple[...])
            after_match = line[start_pos:]
            if re.match(r"tuple\s*\(", after_match):
                continue  # Skip - it's a function call, not a type annotation
            
            # Check if it's in a type annotation context
            # Extract the tuple[...] part to verify it's a type annotation
            tuple_match = re.search(r"tuple\s*\[[^\]]*\]", line[start_pos:])
            if not tuple_match:
                continue  # No complete tuple[...] found
            
            # Verify it's in a type annotation context
            # Check if there's a colon or arrow before it (within reasonable distance)
            context_before = line[max(0, start_pos - 50):start_pos]
            if not (":" in context_before or "->" in context_before):
                # Might still be a type alias or other context, but be lenient
                # Only flag if it's clearly a type annotation pattern
                if not re.search(r"(->|:\s*|=\s*)", context_before):
                    continue  # Not clearly a type annotation
            
            issues.append(
                CompatibilityIssue(
                    file_path=file_path,
                    line_number=line_num,
                    issue_type="tuple-usage",
                    message="Built-in generic `tuple[...]` should be replaced with `Tuple[...]` from typing for Python 3.8 compatibility. Import `Tuple` from typing and use `Tuple[...]` instead.",
                    code=line.strip(),
                )
            )

        return issues

    def _check_tuple_type_alias(
        self, file_path: Path, line_num: int, line: str
    ) -> list[CompatibilityIssue]:
        """
        Check for tuple[...] usage in type aliases.
        
        IMPORTANT: Even with `from __future__ import annotations`, type aliases
        are still evaluated at runtime in Python 3.8. This means `tuple[...]`
        in type aliases will fail with `TypeError: 'type' object is not subscriptable`.
        
        Type aliases must use `Tuple[...]` from typing for Python 3.8 compatibility,
        even when the file has `from __future__ import annotations`.
        
        Examples of type aliases that need fixing:
        - `_PacketInfo = tuple[UTPPacket, float, int]`  # ❌ Fails in Python 3.8
        - `RenewalCallback = Callable[..., Awaitable[tuple[bool, int]]]`  # ❌ Fails in Python 3.8
        
        Should be:
        - `_PacketInfo = Tuple[UTPPacket, float, int]`  # ✅ Works
        - `RenewalCallback = Callable[..., Awaitable[Tuple[bool, int]]]`  # ✅ Works
        """
        issues: list[CompatibilityIssue] = []

        # Pattern to match tuple[...] in type aliases
        # Matches: tuple[type, ...], tuple[type1, type2], tuple[...]
        # Using word boundary (\b) to avoid false positives
        pattern = r"\btuple\s*\["

        # Skip if line is a comment or string
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            return issues

        # Check if this looks like a type alias
        # Type aliases typically:
        # 1. Have uppercase variable names (convention)
        # 2. Use = assignment
        # 3. Are at module level (no indentation or minimal indentation)
        # 4. May be nested inside generic types like Callable[...], Awaitable[...]
        
        # Pattern 1: Direct type alias: `_PacketInfo = tuple[...]`
        # Matches: Uppercase identifier = tuple[...]
        direct_alias_pattern = r"^[A-Z_][a-zA-Z0-9_]*\s*=\s*tuple\s*\["
        
        # Pattern 2: Nested in generic: `Callable[..., Awaitable[tuple[...]]]`
        # Matches: tuple[...] inside generic type parameters
        nested_pattern = r"[,\[\s]tuple\s*\["
        
        is_type_alias = False
        match_start = None
        
        # Check for direct type alias
        direct_match = re.search(direct_alias_pattern, stripped)
        if direct_match:
            is_type_alias = True
            match_start = direct_match.start() + len(direct_match.group(0)) - len("tuple[")
        
        # Check for nested tuple in generic types (common in type aliases)
        if not is_type_alias:
            nested_match = re.search(nested_pattern, line)
            if nested_match:
                # Check if it's in a type alias context (has = before it, uppercase identifier)
                before_match = line[:nested_match.start()]
                # Look for type alias pattern: identifier = ... before the tuple
                if re.search(r"[A-Z_][a-zA-Z0-9_]*\s*=\s*", before_match):
                    is_type_alias = True
                    match_start = nested_match.start() + 1  # +1 to skip the comma/bracket/space
        
        if not is_type_alias:
            return issues  # Not a type alias, skip
        
        # Find all tuple[...] matches
        matches = list(re.finditer(pattern, line))
        for match in matches:
            start_pos = match.start()
            
            # Check if we're inside a string literal
            before_match = line[:start_pos]
            single_quotes_before = before_match.count("'") - before_match.count("\\'")
            double_quotes_before = before_match.count('"') - before_match.count('\\"')
            
            # If odd number of quotes, we're inside a string
            if (single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1):
                continue  # Skip - it's inside a string literal
            
            # Additional check: skip if it's a function call like tuple([...])
            # Look for tuple( after the match (not tuple[...])
            after_match = line[start_pos:]
            if re.match(r"tuple\s*\(", after_match):
                continue  # Skip - it's a function call, not a type annotation
            
            # Verify it's a complete tuple[...] expression
            tuple_match = re.search(r"tuple\s*\[[^\]]*\]", line[start_pos:])
            if not tuple_match:
                continue  # No complete tuple[...] found
            
            issues.append(
                CompatibilityIssue(
                    file_path=file_path,
                    line_number=line_num,
                    issue_type="tuple-type-alias",
                    message="Type alias uses `tuple[...]` which fails at runtime in Python 3.8. Even with `from __future__ import annotations`, type aliases are evaluated at runtime. Use `Tuple[...]` from typing instead and import `Tuple` from typing.",
                    code=line.strip(),
                )
            )

        return issues

    def _check_tuple_import(
        self, file_path: Path, line_num: int, line: str
    ) -> list[CompatibilityIssue]:
        """
        Check for Tuple[...] usage without proper import from typing.
        
        For Python 3.8 compatibility, when using `Tuple[...]` in type annotations,
        it must be imported from typing. This check flags `Tuple[...]` usage when
        `Tuple` is not imported from typing.
        
        This check only runs if `Tuple` is not imported, to avoid false positives.
        """
        issues: list[CompatibilityIssue] = []

        # Pattern to match Tuple[...] in type annotations
        # Matches: Tuple[type, ...], Tuple[type1, type2], Tuple[...]
        # Using word boundary (\b) to ensure we match Tuple, not MyTuple
        pattern = r"\bTuple\s*\["

        # Skip if line is a comment or string
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            return issues

        # Skip if it's clearly not a type annotation (e.g., variable assignment, function call)
        # We want to catch: -> Tuple[...], param: Tuple[...], var: Tuple[...]
        # But skip: my_tuple = Tuple([...]), Tuple([...])
        
        # Check if we're in a type annotation context
        # Look for common type annotation patterns: ->, :, or in type alias context
        is_type_annotation = (
            "->" in line or  # Return type
            re.search(r":\s*Tuple\s*\[", line) or  # Parameter or variable annotation
            re.search(r"=\s*Tuple\s*\[", line)  # Type alias (may be false positive, but check anyway)
        )

        if not is_type_annotation:
            # Could still be a type annotation in a complex context, so check for Tuple[...]
            # but be more careful
            if not re.search(r"Tuple\s*\[[^\]]+\]", line):
                return issues  # No Tuple[...] found, skip

        matches = list(re.finditer(pattern, line))
        for match in matches:
            start_pos = match.start()
            
            # Check if we're inside a string literal
            before_match = line[:start_pos]
            single_quotes_before = before_match.count("'") - before_match.count("\\'")
            double_quotes_before = before_match.count('"') - before_match.count('\\"')
            
            # If odd number of quotes, we're inside a string
            if (single_quotes_before % 2 == 1) or (double_quotes_before % 2 == 1):
                continue  # Skip - it's inside a string literal
            
            # Additional check: skip if it's a function call like Tuple([...])
            # Look for Tuple( after the match (not Tuple[...])
            after_match = line[start_pos:]
            if re.match(r"Tuple\s*\(", after_match):
                continue  # Skip - it's a function call, not a type annotation
            
            # Check if it's in a type annotation context
            # Extract the Tuple[...] part to verify it's a type annotation
            tuple_match = re.search(r"Tuple\s*\[[^\]]*\]", line[start_pos:])
            if not tuple_match:
                continue  # No complete Tuple[...] found
            
            # Verify it's in a type annotation context
            # Check if there's a colon or arrow before it (within reasonable distance)
            context_before = line[max(0, start_pos - 50):start_pos]
            if not (":" in context_before or "->" in context_before):
                # Might still be a type alias or other context, but be lenient
                # Only flag if it's clearly a type annotation pattern
                if not re.search(r"(->|:\s*|=\s*)", context_before):
                    continue  # Not clearly a type annotation
            
            issues.append(
                CompatibilityIssue(
                    file_path=file_path,
                    line_number=line_num,
                    issue_type="tuple-missing-import",
                    message="`Tuple[...]` is used but `Tuple` is not imported from typing. Add `from typing import Tuple` (or include `Tuple` in existing typing import) for Python 3.8 compatibility.",
                    code=line.strip(),
                )
            )

        return issues

    def lint_directory(self, directory: Path, exclude_patterns: Optional[list[str]] = None) -> list[CompatibilityIssue]:
        """Lint all Python files in a directory."""
        if exclude_patterns is None:
            exclude_patterns = [
                ".git",
                ".venv",
                "__pycache__",
                ".pytest_cache",
                ".ruff_cache",
                "node_modules",
                "build",
                "dist",
                "htmlcov",
                "site",
            ]

        all_issues: list[CompatibilityIssue] = []

        for py_file in directory.rglob("*.py"):
            # Skip excluded paths
            if any(exclude in str(py_file) for exclude in exclude_patterns):
                continue

            file_issues = self.check_file(py_file)
            all_issues.extend(file_issues)

        return all_issues

    def format_output(self, issues: list[CompatibilityIssue]) -> str:
        """Format issues for output."""
        if not issues:
            return "No compatibility issues found!"

        output_lines = [f"Found {len(issues)} compatibility issue(s):\n"]

        # Group by file
        by_file: dict[Path, list[CompatibilityIssue]] = {}
        for issue in issues:
            if issue.file_path not in by_file:
                by_file[issue.file_path] = []
            by_file[issue.file_path].append(issue)

        for file_path, file_issues in sorted(by_file.items()):
            output_lines.append(f"\n{file_path}:")
            for issue in sorted(file_issues, key=lambda x: x.line_number):
                output_lines.append(
                    f"  Line {issue.line_number}: [{issue.issue_type}] {issue.message}"
                )
                output_lines.append(f"    {issue.code}")

        return "\n".join(output_lines)


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check Python 3.8/3.9 compatibility issues"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path("ccbt")],
        help="Paths to check (default: ccbt/)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Patterns to exclude (can be specified multiple times)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

    linter = CompatibilityLinter(Path.cwd())
    all_issues: list[CompatibilityIssue] = []

    for path in args.paths:
        if path.is_file():
            issues = linter.check_file(path)
            all_issues.extend(issues)
        elif path.is_dir():
            issues = linter.lint_directory(path, exclude_patterns=args.exclude)
            all_issues.extend(issues)
        else:
            print(f"Error: {path} does not exist", file=sys.stderr)
            return 1

    if args.format == "json":
        import json

        output = json.dumps(
            [
                {
                    "file": str(issue.file_path),
                    "line": issue.line_number,
                    "type": issue.issue_type,
                    "message": issue.message,
                    "code": issue.code,
                }
                for issue in all_issues
            ],
            indent=2,
        )
        print(output)
    else:
        output = linter.format_output(all_issues)
        print(output)

    return 0 if not all_issues else 1


if __name__ == "__main__":
    sys.exit(main())

