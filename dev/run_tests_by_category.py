#!/usr/bin/env python3
"""Run tests by category with timeouts and capture all failures."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

# Test categories based on pytest markers (excluding performance, chaos, compatibility as per CI)
CATEGORIES = [
    {"name": "unit", "marker": "unit"},
    {"name": "integration", "marker": "integration"},
    {"name": "core", "marker": "core"},
    {"name": "peer", "marker": "peer"},
    {"name": "piece", "marker": "piece"},
    {"name": "tracker", "marker": "tracker"},
    {"name": "network", "marker": "network"},
    {"name": "metadata", "marker": "metadata"},
    {"name": "disk", "marker": "disk"},
    {"name": "file", "marker": "file"},
    {"name": "storage", "marker": "storage"},
    {"name": "session", "marker": "session"},
    {"name": "resilience", "marker": "resilience"},
    {"name": "connection", "marker": "connection"},
    {"name": "checkpoint", "marker": "checkpoint"},
    {"name": "cli", "marker": "cli"},
    {"name": "extensions", "marker": "extensions"},
    {"name": "ml", "marker": "ml"},
    {"name": "monitoring", "marker": "monitoring"},
    {"name": "observability", "marker": "observability"},
    {"name": "protocols", "marker": "protocols"},
    {"name": "security", "marker": "security"},
    {"name": "transport", "marker": "transport"},
    {"name": "config", "marker": "config"},
    {"name": "discovery", "marker": "discovery"},
    {"name": "plugins", "marker": "plugins"},
    {"name": "services", "marker": "services"},
    {"name": "daemon", "path": "tests/daemon"},
]


def run_category(category: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Run tests for a single category."""
    name = category["name"]
    print(f"\n{'='*60}")
    print(f"Running category: {name}")
    print(f"{'='*60}\n")
    
    output_file = output_dir / f"{name}_output.txt"
    failures_file = output_dir / f"{name}_failures.txt"
    
    # Build pytest command
    pytest_args = [
        "uv", "run", "pytest",
        "-c", "dev/pytest.ini",
        "tests/",
        "-v",
        "--tb=short",
        "--maxfail=999",
        "--timeout=600",
        "--timeout-method=thread",
        "-m", "not performance and not chaos and not compatibility",
    ]
    
    # Add marker or path filter
    if "marker" in category:
        pytest_args.extend(["-m", category["marker"]])
    elif "path" in category:
        pytest_args[-1] = category["path"]  # Replace tests/ with specific path
    
    # Run pytest
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            process = subprocess.Popen(
                pytest_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            
            # Stream output to both file and console
            output_lines = []
            if process.stdout is not None:
                for line in process.stdout:
                    output_lines.append(line)
                    f.write(line)
                f.flush()
                # Print progress indicators
                if "PASSED" in line or "FAILED" in line or "ERROR" in line:
                    print(line.rstrip())
            
            process.wait()
            return_code = process.returncode
        
        # Extract failures
        failures = []
        in_failure = False
        current_failure = []
        
        for i, line in enumerate(output_lines):
            if "FAILED" in line or "ERROR" in line or "TIMEOUT" in line.upper():
                if current_failure:
                    failures.append("\n".join(current_failure))
                current_failure = [line]
                in_failure = True
            elif in_failure and (line.strip().startswith("_") or "test_" in line or "E " in line or ">" in line):
                current_failure.append(line)
            elif in_failure and line.strip() == "":
                if current_failure:
                    failures.append("\n".join(current_failure))
                    current_failure = []
                in_failure = False
        
        if current_failure:
            failures.append("\n".join(current_failure))
        
        # Write failures to file
        if failures:
            with open(failures_file, "w", encoding="utf-8") as f:
                f.write(f"Failures for category: {name}\n")
                f.write("="*60 + "\n\n")
                for failure in failures:
                    f.write(failure)
                    f.write("\n" + "-"*60 + "\n\n")
        
        # Extract summary stats
        passed = sum(1 for line in output_lines if " PASSED " in line)
        failed = sum(1 for line in output_lines if " FAILED " in line)
        errors = sum(1 for line in output_lines if " ERROR " in line)
        
        result = {
            "category": name,
            "return_code": return_code,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "output_file": str(output_file),
            "failures_file": str(failures_file) if failures else None,
        }
        
        if failures:
            print(f"\nFAILURES: {failed} failed, {errors} errors")
        else:
            print(f"\nAll tests passed: {passed} passed")
        
        return result
        
    except Exception as e:
        print(f"ERROR running tests: {e}")
        return {
            "category": name,
            "return_code": -1,
            "error": str(e),
            "output_file": str(output_file),
        }


def main() -> None:
    """Main entry point."""
    output_dir = Path("test_results_by_category")
    output_dir.mkdir(exist_ok=True)
    
    results = []
    
    # Check which categories have already been run
    completed = {f.stem.replace("_output", "") for f in output_dir.glob("*_output.txt")}
    
    print(f"Completed categories: {sorted(completed)}")
    print(f"Remaining categories: {[c['name'] for c in CATEGORIES if c['name'] not in completed]}")
    
    # Run each category
    for category in CATEGORIES:
        if category["name"] in completed:
            print(f"\nSkipping {category['name']} (already completed)")
            continue
        
        result = run_category(category, output_dir)
        results.append(result)
    
    # Create summary
    summary_file = output_dir / "summary.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("Test Results Summary\n")
        f.write("="*60 + "\n\n")
        
        total_passed = sum(r.get("passed", 0) for r in results)
        total_failed = sum(r.get("failed", 0) for r in results)
        total_errors = sum(r.get("errors", 0) for r in results)
        
        f.write(f"Total Passed: {total_passed}\n")
        f.write(f"Total Failed: {total_failed}\n")
        f.write(f"Total Errors: {total_errors}\n\n")
        
        f.write("By Category:\n")
        f.write("-"*60 + "\n")
        for result in results:
            f.write(f"{result['category']:20} | ")
            f.write(f"Passed: {result.get('passed', 0):4} | ")
            f.write(f"Failed: {result.get('failed', 0):4} | ")
            f.write(f"Errors: {result.get('errors', 0):4} | ")
            f.write(f"RC: {result.get('return_code', 'N/A')}\n")
            if result.get("failures_file"):
                f.write(f"  Failures: {result['failures_file']}\n")
    
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"Total Passed: {total_passed}")
    print(f"Total Failed: {total_failed}")
    print(f"Total Errors: {total_errors}")
    print(f"\nFull results saved to: {output_dir}")


if __name__ == "__main__":
    main()

