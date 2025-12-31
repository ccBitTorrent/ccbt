#!/usr/bin/env python3
"""Build documentation with detailed logging and error/warning itemization.

This script replicates the pre-commit documentation building tasks and writes
logs to files in a folder to itemize warnings and errors.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def setup_log_directory() -> Path:
    """Create log directory with timestamp."""
    log_dir = Path("dev/docs_build_logs")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_dir = log_dir / timestamp
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def run_docs_build() -> tuple[int, str, str]:
    """Run the documentation build and capture output."""
    print("Building documentation...")  # noqa: T201
    print("=" * 80)  # noqa: T201

    # Run the same command as pre-commit hook
    cmd = ["uv", "run", "python", "dev/build_docs_patched_clean.py"]

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            check=False,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
    except Exception as e:
        error_msg = f"Failed to run documentation build: {e}"
        return 1, "", error_msg
    else:
        return result.returncode, result.stdout, result.stderr


def parse_warnings_and_errors(output: str, stderr: str) -> tuple[list[str], list[str]]:  # noqa: PLR0912, PLR0915
    """Parse warnings and errors from mkdocs output."""
    warnings: list[str] = []
    errors: list[str] = []

    # Combine stdout and stderr
    combined = output + "\n" + stderr

    # Common patterns for warnings and errors
    warning_patterns = [
        r"WARNING\s+-\s+(.+)",
        r"warning:\s*(.+)",
        r"Warning:\s*(.+)",
        r"WARN\s+-\s+(.+)",
        r"⚠\s+(.+)",
    ]

    error_patterns = [
        r"ERROR\s+-\s+(.+)",
        r"error:\s*(.+)",
        r"Error:\s*(.+)",
        r"ERR\s+-\s+(.+)",
        r"✗\s+(.+)",
        r"CRITICAL\s+-\s+(.+)",
        r"Exception:\s*(.+)",
        r"Traceback\s+\(most recent call last\):",
        r"FileNotFoundError:",
        r"ModuleNotFoundError:",
        r"ImportError:",
        r"SyntaxError:",
        r"TypeError:",
        r"ValueError:",
        r"AttributeError:",
    ]

    lines = combined.split("\n")
    current_error: list[str] = []
    in_traceback = False

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            if current_error:
                errors.append("\n".join(current_error))
                current_error = []
            in_traceback = False
            continue

        # Check for traceback start
        if "Traceback (most recent call last)" in line:
            in_traceback = True
            current_error = [line]
            continue

        # If in traceback, collect lines until we hit a non-indented line
        if in_traceback:
            if line.startswith(("  ", "\t")) or any(
                err in line for err in ["File ", "  ", "    "]
            ):
                current_error.append(line)
            else:
                # End of traceback, add the error message line
                if line:
                    current_error.append(line)
                errors.append("\n".join(current_error))
                current_error = []
                in_traceback = False
            continue

        # Check for errors
        error_found = False
        for pattern in error_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # Include context (previous and next lines if available)
                context_lines = []
                if i > 0 and lines[i - 1].strip():
                    context_lines.append(f"Context: {lines[i - 1].strip()}")
                context_lines.append(line)
                if i < len(lines) - 1 and lines[i + 1].strip():
                    context_lines.append(f"Context: {lines[i + 1].strip()}")
                errors.append("\n".join(context_lines))
                error_found = True
                break

        if error_found:
            continue

        # Check for warnings
        for pattern in warning_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # Include context
                context_lines = []
                if i > 0 and lines[i - 1].strip():
                    context_lines.append(f"Context: {lines[i - 1].strip()}")
                context_lines.append(line)
                if i < len(lines) - 1 and lines[i + 1].strip():
                    context_lines.append(f"Context: {lines[i + 1].strip()}")
                warnings.append("\n".join(context_lines))
                break

    # Add any remaining error from traceback
    if current_error:
        errors.append("\n".join(current_error))

    # Remove duplicates while preserving order
    seen_warnings = set()
    unique_warnings = []
    for warn in warnings:
        warn_key = warn.strip().lower()
        if warn_key not in seen_warnings:
            seen_warnings.add(warn_key)
            unique_warnings.append(warn)

    seen_errors = set()
    unique_errors = []
    for err in errors:
        err_key = err.strip().lower()
        if err_key not in seen_errors:
            seen_errors.add(err_key)
            unique_errors.append(err)

    return unique_warnings, unique_errors


def write_logs(
    log_dir: Path,
    returncode: int,
    stdout: str,
    stderr: str,
    warnings: list[str],
    errors: list[str],
) -> None:  # noqa: PLR0913
    """Write all logs to files."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Full output log
    full_log_path = log_dir / "full_output.log"
    with full_log_path.open("w", encoding="utf-8") as f:
        f.write(f"Documentation Build Log - {timestamp}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Return Code: {returncode}\n")
        f.write(f"Exit Status: {'SUCCESS' if returncode == 0 else 'FAILURE'}\n\n")
        f.write("STDOUT:\n")
        f.write("-" * 80 + "\n")
        f.write(stdout)
        f.write("\n\n")
        f.write("STDERR:\n")
        f.write("-" * 80 + "\n")
        f.write(stderr)
        f.write("\n")

    # Warnings log
    warnings_log_path = log_dir / "warnings.log"
    with warnings_log_path.open("w", encoding="utf-8") as f:
        f.write(f"Documentation Build Warnings - {timestamp}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total Warnings: {len(warnings)}\n\n")
        if warnings:
            for i, warning in enumerate(warnings, 1):
                f.write(f"Warning #{i}:\n")
                f.write("-" * 80 + "\n")
                f.write(warning)
                f.write("\n\n")
        else:
            f.write("No warnings found.\n")

    # Errors log
    errors_log_path = log_dir / "errors.log"
    with errors_log_path.open("w", encoding="utf-8") as f:
        f.write(f"Documentation Build Errors - {timestamp}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total Errors: {len(errors)}\n\n")
        if errors:
            for i, error in enumerate(errors, 1):
                f.write(f"Error #{i}:\n")
                f.write("-" * 80 + "\n")
                f.write(error)
                f.write("\n\n")
        else:
            f.write("No errors found.\n")

    # Summary log
    summary_log_path = log_dir / "summary.txt"
    with summary_log_path.open("w", encoding="utf-8") as f:
        f.write(f"Documentation Build Summary - {timestamp}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Exit Status: {'SUCCESS' if returncode == 0 else 'FAILURE'}\n")
        f.write(f"Return Code: {returncode}\n\n")
        f.write(f"Total Warnings: {len(warnings)}\n")
        f.write(f"Total Errors: {len(errors)}\n\n")
        f.write(f"Log Directory: {log_dir}\n")
        f.write(f"Full Output: {full_log_path.name}\n")
        f.write(f"Warnings: {warnings_log_path.name}\n")
        f.write(f"Errors: {errors_log_path.name}\n")

    print(f"\nLogs written to: {log_dir}")  # noqa: T201
    print(f"  - Full output: {full_log_path.name}")  # noqa: T201
    print(f"  - Warnings ({len(warnings)}): {warnings_log_path.name}")  # noqa: T201
    print(f"  - Errors ({len(errors)}): {errors_log_path.name}")  # noqa: T201
    print(f"  - Summary: {summary_log_path.name}")  # noqa: T201


def main() -> int:
    """Run documentation build with logging."""
    log_dir = setup_log_directory()

    returncode, stdout, stderr = run_docs_build()

    warnings, errors = parse_warnings_and_errors(stdout, stderr)

    write_logs(log_dir, returncode, stdout, stderr, warnings, errors)

    # Print summary to console
    print("\n" + "=" * 80)  # noqa: T201
    print("BUILD SUMMARY")  # noqa: T201
    print("=" * 80)  # noqa: T201
    print(f"Exit Status: {'SUCCESS' if returncode == 0 else 'FAILURE'}")  # noqa: T201
    print(f"Return Code: {returncode}")  # noqa: T201
    print(f"Warnings: {len(warnings)}")  # noqa: T201
    print(f"Errors: {len(errors)}")  # noqa: T201

    if warnings:
        print("\nFirst few warnings:")  # noqa: T201
        for i, warning in enumerate(warnings[:3], 1):
            print(f"  {i}. {warning.split(chr(10))[0][:100]}...")  # noqa: T201

    if errors:
        print("\nFirst few errors:")  # noqa: T201
        for i, error in enumerate(errors[:3], 1):
            print(f"  {i}. {error.split(chr(10))[0][:100]}...")  # noqa: T201

    print(f"\nDetailed logs available in: {log_dir}")  # noqa: T201

    return returncode


if __name__ == "__main__":
    sys.exit(main())

