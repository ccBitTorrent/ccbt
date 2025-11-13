import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> int:
    proc = subprocess.run(cmd)
    return proc.returncode


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    examples_cfg = repo_root / "docs" / "examples" / "example-config-performance.toml"

    commands: list[list[str]] = [
        [
            sys.executable,
            str(repo_root / "tests" / "performance" / "bench_hash_verify.py"),
            "--quick",
            "--config-file",
            str(examples_cfg),
        ],
        [
            sys.executable,
            str(repo_root / "tests" / "performance" / "bench_disk_io.py"),
            "--quick",
            "--sizes",
            "256KiB",
            "1MiB",
            "4MiB",
            "--config-file",
            str(examples_cfg),
        ],
        [
            sys.executable,
            str(repo_root / "tests" / "performance" / "bench_piece_assembly.py"),
            "--quick",
            "--config-file",
            str(examples_cfg),
        ],
        [
            sys.executable,
            str(repo_root / "tests" / "performance" / "bench_loopback_throughput.py"),
            "--quick",
            "--config-file",
            str(examples_cfg),
        ],
        [
            sys.executable,
            str(repo_root / "tests" / "performance" / "bench_encryption.py"),
            "--quick",
            "--config-file",
            str(examples_cfg),
        ],
    ]

    for cmd in commands:
        code = run(cmd)
        if code != 0:
            return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


