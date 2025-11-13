#!/usr/bin/env python3
"""Analyze coverage reports to identify missing coverage areas.

This script parses coverage.xml and optionally htmlcov to provide
line-level analysis of uncovered code.
"""

import sys
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from collections import defaultdict
from dataclasses import dataclass

# Fix encoding for Windows console
if sys.platform == "win32":
    if hasattr(sys.stdout, "encoding") and sys.stdout.encoding != "utf-8":
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            # Python < 3.7 or reconfigure failed
            import io
            if hasattr(sys.stdout, "buffer"):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


@dataclass
class FileCoverage:
    """Coverage information for a single file."""

    filename: str
    line_rate: float
    branch_rate: float
    lines_total: int
    lines_covered: int
    lines_missing: list[int]
    branches_total: int
    branches_covered: int


@dataclass
class ModuleCoverage:
    """Coverage information for a module."""

    module_name: str
    files: list[FileCoverage]
    total_line_rate: float


def parse_coverage_xml(xml_path: Path) -> dict[str, FileCoverage]:
    """Parse coverage.xml file and extract file-level coverage."""
    if not xml_path.exists():
        print(f"ERROR: Coverage XML not found at {xml_path}")
        return {}

    tree = ET.parse(xml_path)
    root = tree.getroot()

    coverage_data: dict[str, FileCoverage] = {}

    # Get source root from XML
    sources = root.findall(".//source")
    source_root = Path(sources[0].text).resolve() if sources and sources[0].text else Path.cwd()

    # Parse each class (file) in the coverage report
    for class_elem in root.findall(".//class"):
        filename = class_elem.get("filename", "")
        if not filename:
            continue

        # Build full path to file
        # Coverage XML uses relative paths from source root
        try:
            if Path(filename).is_absolute():
                full_path = Path(filename)
            else:
                # Try relative to source root first
                candidate = source_root / filename
                if candidate.exists():
                    full_path = candidate
                else:
                    # Try relative to current directory
                    full_path = Path(filename).resolve()
            
            # Normalize to relative path from project root
            try:
                # Try to make it relative to current working directory
                rel_path = full_path.relative_to(Path.cwd())
            except ValueError:
                # If not under cwd, use absolute path
                rel_path = full_path
            
            # Only include files under ccbt/
            if "ccbt" not in str(rel_path):
                continue
                
        except Exception as e:
            print(f"Warning: Could not resolve path for {filename}: {e}")
            continue

        # Get line information
        lines = {}
        for line_elem in class_elem.findall(".//line"):
            line_num = int(line_elem.get("number", "0"))
            hits = int(line_elem.get("hits", "0"))
            lines[line_num] = hits

        if not lines:
            continue

        # Calculate coverage stats
        lines_total = len(lines)
        lines_covered = sum(1 for hits in lines.values() if hits > 0)
        lines_missing = [num for num, hits in sorted(lines.items()) if hits == 0]
        line_rate = lines_covered / lines_total if lines_total > 0 else 0.0

        # Branch coverage
        branches_total = 0
        branches_covered = 0
        branch_rate = 0.0

        # Check for branch information
        for line_elem in class_elem.findall(".//line"):
            condition_coverage = line_elem.get("condition-coverage")
            if condition_coverage:
                # Format: "50% (1/2)" - parse this
                try:
                    parts = condition_coverage.split("(")[1].split(")")[0]
                    covered, total = map(int, parts.split("/"))
                    branches_total += total
                    branches_covered += covered
                except (ValueError, IndexError):
                    pass

        if branches_total > 0:
            branch_rate = branches_covered / branches_total

        file_key = str(rel_path)
        coverage_data[file_key] = FileCoverage(
            filename=file_key,
            line_rate=line_rate,
            branch_rate=branch_rate,
            lines_total=lines_total,
            lines_covered=lines_covered,
            lines_missing=lines_missing,
            branches_total=branches_total,
            branches_covered=branches_covered,
        )

    return coverage_data


def analyze_by_module(coverage_data: dict[str, FileCoverage]) -> dict[str, ModuleCoverage]:
    """Group coverage data by module."""
    modules: dict[str, ModuleCoverage] = defaultdict(lambda: ModuleCoverage(module_name="", files=[], total_line_rate=0.0))

    for file_path, file_cov in coverage_data.items():
        # Extract module name (ccbt/module/... -> module)
        parts = Path(file_path).parts
        if len(parts) >= 2 and parts[0] == "ccbt":
            module_name = parts[1] if len(parts) > 1 else "root"
        else:
            module_name = "root"

        if module_name not in modules:
            modules[module_name] = ModuleCoverage(
                module_name=module_name,
                files=[],
                total_line_rate=0.0,
            )

        modules[module_name].files.append(file_cov)

    # Calculate module-level stats
    for module in modules.values():
        if module.files:
            total_lines = sum(f.lines_total for f in module.files)
            covered_lines = sum(f.lines_covered for f in module.files)
            module.total_line_rate = covered_lines / total_lines if total_lines > 0 else 0.0

    return modules


def get_uncovered_ranges(lines_missing: list[int]) -> list[tuple[int, int]]:
    """Convert list of missing line numbers to ranges."""
    if not lines_missing:
        return []

    ranges = []
    start = lines_missing[0]
    end = lines_missing[0]

    for line in lines_missing[1:]:
        if line == end + 1:
            end = line
        else:
            ranges.append((start, end))
            start = line
            end = line

    ranges.append((start, end))
    return ranges


def format_line_ranges(ranges: list[tuple[int, int]]) -> str:
    """Format line ranges as string."""
    if not ranges:
        return ""

    parts = []
    for start, end in ranges:
        if start == end:
            parts.append(str(start))
        else:
            parts.append(f"{start}-{end}")

    return ", ".join(parts)


def print_detailed_report(coverage_data: dict[str, FileCoverage], min_coverage: float = 0.0) -> None:
    """Print detailed coverage report."""
    print("=" * 80)
    print("COVERAGE ANALYSIS REPORT")
    print("=" * 80)
    print()

    # Sort files by coverage rate (lowest first)
    sorted_files = sorted(coverage_data.items(), key=lambda x: x[1].line_rate)

    # Files with low/no coverage
    print("FILES WITH LOW COVERAGE (< 50%):")
    print("-" * 80)
    low_coverage = [
        (path, cov) for path, cov in sorted_files
        if cov.line_rate < 0.50 and cov.lines_total > 0
    ]

    if not low_coverage:
        print("  [OK] All files have at least 50% coverage")
    else:
        for file_path, file_cov in low_coverage[:20]:  # Top 20
            print(f"\n  [FILE] {file_path}")
            print(f"     Coverage: {file_cov.line_rate*100:.1f}% ({file_cov.lines_covered}/{file_cov.lines_total} lines)")
            if file_cov.lines_missing:
                ranges = get_uncovered_ranges(file_cov.lines_missing)
                if len(ranges) <= 10:
                    print(f"     Missing lines: {format_line_ranges(ranges)}")
                else:
                    print(f"     Missing lines: {len(file_cov.lines_missing)} lines in {len(ranges)} ranges")
                    print(f"     First ranges: {format_line_ranges(ranges[:5])} ...")

    print()
    print("=" * 80)
    print("MODULE-LEVEL COVERAGE:")
    print("-" * 80)

    modules = analyze_by_module(coverage_data)
    sorted_modules = sorted(modules.items(), key=lambda x: x[1].total_line_rate)

    for module_name, module_cov in sorted_modules:
        print(f"\n  [MODULE] {module_name}")
        print(f"     Module Coverage: {module_cov.total_line_rate*100:.1f}%")
        print(f"     Files: {len(module_cov.files)}")

        # Show files in this module with low coverage
        low_files = [f for f in module_cov.files if f.line_rate < 0.50]
        if low_files:
            print(f"     Files needing attention: {len(low_files)}")
            for f in sorted(low_files, key=lambda x: x.line_rate)[:5]:
                print(f"       - {f.filename}: {f.line_rate*100:.1f}%")

    print()
    print("=" * 80)
    print("DETAILED LINE-LEVEL ANALYSIS:")
    print("-" * 80)

    # Show detailed missing lines for top 10 files with most missing lines
    sorted_by_missing = sorted(
        coverage_data.items(),
        key=lambda x: len(x[1].lines_missing),
        reverse=True
    )

    print("\nTop 10 files with most uncovered lines:")
    for file_path, file_cov in sorted_by_missing[:10]:
        if file_cov.lines_missing:
            print(f"\n  [FILE] {file_path}")
            print(f"     Coverage: {file_cov.line_rate*100:.1f}%")
            print(f"     Missing: {len(file_cov.lines_missing)} lines")
            ranges = get_uncovered_ranges(file_cov.lines_missing)
            if len(ranges) <= 15:
                print(f"     Uncovered ranges: {format_line_ranges(ranges)}")
            else:
                print(f"     Uncovered ranges ({len(ranges)} ranges):")
                for start, end in ranges[:10]:
                    if start == end:
                        print(f"       Line {start}")
                    else:
                        print(f"       Lines {start}-{end}")
                print(f"       ... and {len(ranges) - 10} more ranges")


def main() -> int:
    """Main entry point."""
    # Coverage files are generated in site/reports/ by pre-commit hooks
    xml_path = Path("site/reports/coverage.xml")
    
    if not xml_path.exists():
        print("ERROR: coverage.xml not found at site/reports/coverage.xml")
        print("\nCoverage reports are generated in site/reports/ by pre-commit hooks.")
        print("To generate coverage, run:")
        print("  uv run python tests/scripts/run_pytest_selective.py --coverage --full-suite")
        print("\nOr directly:")
        print("  uv run pytest -c dev/pytest.ini tests/ --cov=ccbt --cov-config=dev/.coveragerc \\")
        print("    --cov-report=xml:site/reports/coverage.xml \\")
        print("    --cov-report=html:site/reports/htmlcov")
        return 1

    print(f"Parsing coverage data from {xml_path}...")
    coverage_data = parse_coverage_xml(xml_path)

    if not coverage_data:
        print("ERROR: No coverage data found in XML file.")
        return 1

    print(f"Found coverage data for {len(coverage_data)} files\n")

    # Calculate overall stats
    total_lines = sum(c.lines_total for c in coverage_data.values())
    covered_lines = sum(c.lines_covered for c in coverage_data.values())
    overall_coverage = covered_lines / total_lines if total_lines > 0 else 0.0

    print(f"Overall Coverage: {overall_coverage*100:.2f}%")
    print(f"Total Lines: {total_lines}")
    print(f"Covered Lines: {covered_lines}")
    print(f"Missing Lines: {total_lines - covered_lines}")
    print()

    # Print detailed report
    print_detailed_report(coverage_data)

    # Summary statistics
    print()
    print("=" * 80)
    print("SUMMARY STATISTICS:")
    print("-" * 80)

    coverage_buckets = {
        "0%": 0,
        "1-25%": 0,
        "26-50%": 0,
        "51-75%": 0,
        "76-95%": 0,
        "96-100%": 0,
    }

    for file_cov in coverage_data.values():
        rate = file_cov.line_rate * 100
        if rate == 0:
            coverage_buckets["0%"] += 1
        elif rate <= 25:
            coverage_buckets["1-25%"] += 1
        elif rate <= 50:
            coverage_buckets["26-50%"] += 1
        elif rate <= 75:
            coverage_buckets["51-75%"] += 1
        elif rate <= 95:
            coverage_buckets["76-95%"] += 1
        else:
            coverage_buckets["96-100%"] += 1

    for bucket, count in coverage_buckets.items():
        if count > 0:
            print(f"  Files with {bucket} coverage: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

