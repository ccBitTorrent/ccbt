#!/usr/bin/env python3
"""Test runner for BitTorrent client integration tests.

Runs all integration tests and benchmarks for the high-performance
BitTorrent client implementation.
"""

import argparse
import asyncio
import os
import subprocess
import sys


class TestRunner:
    """Test runner for BitTorrent client tests."""

    def __init__(self):
        self.test_results = {}
        self.benchmark_results = {}

    def run_unit_tests(self) -> bool:
        """Run unit tests using pytest."""
        print("Running unit tests...")
        print("=" * 50)

        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest",
                "tests/",
                "-v",
                "--tb=short",
            ], check=False, capture_output=True, text=True)

            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)

            success = result.returncode == 0
            self.test_results["unit_tests"] = {
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            return success

        except Exception as e:
            print(f"Error running unit tests: {e}")
            self.test_results["unit_tests"] = {
                "success": False,
                "error": str(e),
            }
            return False

    def run_integration_tests(self) -> bool:
        """Run integration tests."""
        print("Running integration tests...")
        print("=" * 50)

        integration_tests = [
            "test_async_peer_connection.py",
            "test_rarest_first.py",
            "test_disk_io.py",
            "test_parallel_metadata.py",
        ]

        all_success = True

        for test_file in integration_tests:
            test_path = f"tests/{test_file}"
            if os.path.exists(test_path):
                print(f"Running {test_file}...")

                try:
                    result = subprocess.run([
                        sys.executable, "-m", "pytest",
                        test_path,
                        "-v",
                        "--tb=short",
                    ], check=False, capture_output=True, text=True)

                    print(result.stdout)
                    if result.stderr:
                        print("STDERR:", result.stderr)

                    success = result.returncode == 0
                    self.test_results[test_file] = {
                        "success": success,
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }

                    if not success:
                        all_success = False

                except Exception as e:
                    print(f"Error running {test_file}: {e}")
                    self.test_results[test_file] = {
                        "success": False,
                        "error": str(e),
                    }
                    all_success = False
            else:
                print(f"Test file {test_file} not found")
                self.test_results[test_file] = {
                    "success": False,
                    "error": "Test file not found",
                }
                all_success = False

        return all_success

    async def run_benchmarks(self) -> bool:
        """Run performance benchmarks."""
        print("Running performance benchmarks...")
        print("=" * 50)

        benchmarks = [
            ("throughput", "benchmarks/bench_throughput.py"),
            ("disk_io", "benchmarks/bench_disk.py"),
            ("hash_verification", "benchmarks/bench_hash_verification.py"),
        ]

        all_success = True

        for benchmark_name, benchmark_script in benchmarks:
            if os.path.exists(benchmark_script):
                print(f"Running {benchmark_name} benchmark...")

                try:
                    result = subprocess.run([
                        sys.executable, benchmark_script,
                    ], check=False, capture_output=True, text=True)

                    print(result.stdout)
                    if result.stderr:
                        print("STDERR:", result.stderr)

                    success = result.returncode == 0
                    self.benchmark_results[benchmark_name] = {
                        "success": success,
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }

                    if not success:
                        all_success = False

                except Exception as e:
                    print(f"Error running {benchmark_name} benchmark: {e}")
                    self.benchmark_results[benchmark_name] = {
                        "success": False,
                        "error": str(e),
                    }
                    all_success = False
            else:
                print(f"Benchmark script {benchmark_script} not found")
                self.benchmark_results[benchmark_name] = {
                    "success": False,
                    "error": "Benchmark script not found",
                }
                all_success = False

        return all_success

    def print_summary(self):
        """Print test and benchmark summary."""
        print("\n" + "=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)

        # Test results
        print("\nUnit Tests:")
        for test_name, result in self.test_results.items():
            if "success" in result:
                status = "PASS" if result["success"] else "FAIL"
                print(f"  {test_name}: {status}")
            else:
                print(f"  {test_name}: ERROR - {result.get('error', 'Unknown error')}")

        # Benchmark results
        print("\nBenchmarks:")
        for benchmark_name, result in self.benchmark_results.items():
            if "success" in result:
                status = "PASS" if result["success"] else "FAIL"
                print(f"  {benchmark_name}: {status}")
            else:
                print(f"  {benchmark_name}: ERROR - {result.get('error', 'Unknown error')}")

        # Overall status
        test_success = all(
            result.get("success", False)
            for result in self.test_results.values()
        )
        benchmark_success = all(
            result.get("success", False)
            for result in self.benchmark_results.values()
        )

        print("\nOverall Status:")
        print(f"  Tests: {'PASS' if test_success else 'FAIL'}")
        print(f"  Benchmarks: {'PASS' if benchmark_success else 'FAIL'}")
        print(f"  Overall: {'PASS' if test_success and benchmark_success else 'FAIL'}")

    async def run_all(self, run_tests: bool = True, run_benchmarks: bool = True):
        """Run all tests and benchmarks."""
        print("BitTorrent Client Test Suite")
        print("=" * 50)

        if run_tests:
            # Run unit tests
            unit_success = self.run_unit_tests()

            # Run integration tests
            integration_success = self.run_integration_tests()

            test_success = unit_success and integration_success
        else:
            test_success = True

        if run_benchmarks:
            # Run benchmarks
            benchmark_success = await self.run_benchmarks()
        else:
            benchmark_success = True

        # Print summary
        self.print_summary()

        return test_success and benchmark_success


async def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="BitTorrent Client Test Runner")
    parser.add_argument("--no-tests", action="store_true",
                      help="Skip running tests")
    parser.add_argument("--no-benchmarks", action="store_true",
                      help="Skip running benchmarks")
    parser.add_argument("--tests-only", action="store_true",
                      help="Run only tests, skip benchmarks")
    parser.add_argument("--benchmarks-only", action="store_true",
                      help="Run only benchmarks, skip tests")

    args = parser.parse_args()

    # Determine what to run
    run_tests = not args.no_tests and not args.benchmarks_only
    run_benchmarks = not args.no_benchmarks and not args.tests_only

    # Run tests and benchmarks
    runner = TestRunner()
    success = await runner.run_all(run_tests, run_benchmarks)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
