#!/usr/bin/env python3
"""Automated test diagnosis runner for ccBitTorrent.

Runs each test file individually with appropriate timeouts to identify
hanging or failing tests, then generates a comprehensive diagnostic report.
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union


class TestResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    SKIP = "SKIP"


@dataclass
class TestFileResult:
    """Result of running a single test file."""
    file_path: str
    category: str
    timeout: int
    result: TestResult
    duration: float
    stdout: str
    stderr: str
    return_code: int
    error_message: Optional[str] = None


class TestDiagnosisRunner:
    """Test diagnosis runner with timeout support and detailed logging."""

    def __init__(self):
        self.results: List[TestFileResult] = []
        self.test_categories: Dict[str, Dict[str, Union[str, int, List[str]]]] = {
            "basic": {
                "timeout": 30,
                "description": "Basic functionality and imports",
                "files": [
                    "test_basic_imports.py",
                    "test_bencode.py",
                    "test_torrent.py",
                    "test_magnet.py",
                ],
            },
            "cli": {
                "timeout": 45,
                "description": "CLI interface tests",
                "files": [
                    "cli/test_resume_commands.py",
                ],
            },
            "unit": {
                "timeout": 60,
                "description": "Core unit tests",
                "files": [
                    "test_peer.py",
                    "test_piece_manager.py",
                    "test_checkpoint.py",
                    "test_file_assembler_blocks.py",
                    "test_tracker.py",
                ],
            },
            "async": {
                "timeout": 60,
                "description": "Async and integration tests",
                "files": [
                    "test_async_peer_connection.py",
                    "test_peer_connection.py",
                    # "test_disk_io.py",  # Temporarily skip - hanging issue
                    "test_rarest_first.py",
                    "test_parallel_metadata.py",
                    "test_simple_functionality.py",
                    "test_tracker_server_http.py",
                ],
            },
            "integration": {
                "timeout": 120,
                "description": "Integration tests",
                "files": [
                    "integration/test_end_to_end.py",
                    "integration/test_resume.py",
                    "integration/test_resume_integration.py",
                ],
            },
            "performance": {
                "timeout": 180,
                "description": "Performance and stress tests",
                "files": [
                    # "performance/test_benchmarks.py"  # Temporarily disabled - hanging issues
                ],
            },
            "advanced": {
                "timeout": 180,
                "description": "Advanced features and edge cases",
                "files": [
                    "extensions/test_compact_peer_lists.py",
                    "extensions/test_fast_extension.py",
                    "protocols/test_protocol_base.py",
                    "protocols/test_hybrid_protocol.py",
                    "security/test_security_manager.py",
                    "chaos/test_fault_injection.py",
                    "property/test_bencode_properties.py",
                    "property/test_piece_selection_properties.py",
                ],
            },
        }

    def find_test_files(self) -> Dict[str, List[str]]:
        """Find all test files and organize by category."""
        tests_dir = Path("tests")
        if not tests_dir.exists():
            print(f"ERROR: Tests directory '{tests_dir}' not found!")
            return {}

        found_tests: Dict[str, List[str]] = {}

        for category, config in self.test_categories.items():
            found_tests[category] = []
            files_list = config["files"]
            if isinstance(files_list, list):
                for test_file in files_list:
                    test_path = tests_dir / test_file
                    if test_path.exists():
                        found_tests[category].append(str(test_path))
                    else:
                        print(f"WARNING: Test file not found: {test_path}")

        return found_tests

    def run_test_file(self, test_path: str, category: str, timeout: int) -> TestFileResult:
        """Run a single test file with timeout."""
        print(f"\n{'='*60}")
        print(f"Running: {test_path}")
        print(f"Category: {category}, Timeout: {timeout}s")
        print(f"{'='*60}")

        start_time = time.time()

        try:
            # Run pytest with timeout
            cmd = [
                sys.executable, "-m", "pytest",
                test_path,
                "-v",
                "--tb=short",
                "--no-header",
                "--disable-warnings",
            ]

            result = subprocess.run(
                cmd,
                check=False, capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )

            duration = time.time() - start_time

            # Determine result
            if result.returncode == 0:
                test_result = TestResult.PASS
            else:
                test_result = TestResult.FAIL

            return TestFileResult(
                file_path=test_path,
                category=category,
                timeout=timeout,
                result=test_result,
                duration=duration,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"TIMEOUT after {timeout}s")

            return TestFileResult(
                file_path=test_path,
                category=category,
                timeout=timeout,
                result=TestResult.TIMEOUT,
                duration=duration,
                stdout="",
                stderr=f"Test timed out after {timeout} seconds",
                return_code=-1,
                error_message=f"Timeout after {timeout}s",
            )

        except Exception as e:
            duration = time.time() - start_time
            print(f"ERROR: {e}")

            return TestFileResult(
                file_path=test_path,
                category=category,
                timeout=timeout,
                result=TestResult.ERROR,
                duration=duration,
                stdout="",
                stderr=str(e),
                return_code=-1,
                error_message=str(e),
            )

    def run_all_tests(self) -> List[TestFileResult]:
        """Run all test files and collect results."""
        print("BitTorrent Test Diagnosis Runner")
        print("="*60)

        found_tests = self.find_test_files()

        if not found_tests:
            print("No test files found!")
            return []

        # Run tests by category
        for category, config in self.test_categories.items():
            if category not in found_tests or not found_tests[category]:
                print(f"\nSkipping {category} tests - no files found")
                continue

            description = config.get("description", category)
            print(f"\n{'='*20} {category.upper()} TESTS - {description} {'='*20}")
            timeout_value = config["timeout"]
            timeout = timeout_value if isinstance(timeout_value, int) else 30

            for test_path in found_tests[category]:
                result = self.run_test_file(test_path, category, timeout)
                self.results.append(result)

                # Print summary
                status_symbol = {
                    TestResult.PASS: "[PASS]",
                    TestResult.FAIL: "[FAIL]",
                    TestResult.TIMEOUT: "[TIMEOUT]",
                    TestResult.ERROR: "[ERROR]",
                }

                print(f"{status_symbol[result.result]} {os.path.basename(test_path)} "
                      f"({result.duration:.1f}s)")

        return self.results

    def generate_report(self) -> str:
        """Generate comprehensive diagnostic report."""
        if not self.results:
            return "No test results to report."

        report = []
        report.append("BITTORRENT TEST DIAGNOSIS REPORT")
        report.append("="*60)
        report.append(f"Total tests run: {len(self.results)}")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Summary by result type
        summary = {}
        for result in self.results:
            summary[result.result] = summary.get(result.result, 0) + 1

        report.append("SUMMARY:")
        for result_type, count in summary.items():
            report.append(f"  {result_type.value}: {count}")
        report.append("")

        # Results by category
        for category in self.test_categories.keys():
            category_results = [r for r in self.results if r.category == category]
            if not category_results:
                continue

            description = self.test_categories[category].get("description", category)
            report.append(f"{category.upper()} TESTS - {description}:")
            report.append("-" * 50)

            for result in category_results:
                filename = os.path.basename(result.file_path)
                status_symbol = {
                    TestResult.PASS: "[PASS]",
                    TestResult.FAIL: "[FAIL]",
                    TestResult.TIMEOUT: "[TIMEOUT]",
                    TestResult.ERROR: "[ERROR]",
                }

                report.append(f"{status_symbol[result.result]} {filename} "
                            f"({result.duration:.1f}s)")

                if result.result != TestResult.PASS:
                    report.append(f"    Return code: {result.return_code}")
                    if result.error_message:
                        report.append(f"    Error: {result.error_message}")
                    if result.stderr:
                        # Show first few lines of stderr
                        stderr_lines = result.stderr.strip().split("\n")[:3]
                        for line in stderr_lines:
                            if line.strip():
                                report.append(f"    {line.strip()}")
            report.append("")

        # Detailed failure analysis
        failures = [r for r in self.results if r.result != TestResult.PASS]
        if failures:
            report.append("DETAILED FAILURE ANALYSIS:")
            report.append("-" * 40)

            for result in failures:
                report.append(f"\n{os.path.basename(result.file_path)} ({result.result.value}):")
                report.append(f"  Duration: {result.duration:.1f}s")
                report.append(f"  Return code: {result.return_code}")

                if result.error_message:
                    report.append(f"  Error: {result.error_message}")

                if result.stderr:
                    report.append("  Stderr:")
                    for line in result.stderr.strip().split("\n")[:10]:
                        if line.strip():
                            report.append(f"    {line}")

                if result.stdout and "FAILED" in result.stdout:
                    report.append("  Key stdout:")
                    for line in result.stdout.strip().split("\n"):
                        if "FAILED" in line or "ERROR" in line or "FAILURES" in line:
                            report.append(f"    {line}")

        return "\n".join(report)

    def save_results(self, filename: str = "test_diagnosis_results.json"):
        """Save results to JSON file."""
        results_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": len(self.results),
            "results": [
                {
                    "file_path": result.file_path,
                    "category": result.category,
                    "timeout": result.timeout,
                    "result": result.result.value,
                    "duration": result.duration,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.return_code,
                    "error_message": result.error_message,
                }
                for result in self.results
            ],
        }

        with open(filename, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"\nResults saved to: {filename}")


def main():
    """Main function."""
    runner = TestDiagnosisRunner()

    # Run all tests
    results = runner.run_all_tests()

    # Generate and print report
    report = runner.generate_report()
    print("\n" + report)

    # Save results
    runner.save_results()

    # Exit with appropriate code
    failures = [r for r in results if r.result != TestResult.PASS]
    if failures:
        print(f"\nFound {len(failures)} failing/hanging tests")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
