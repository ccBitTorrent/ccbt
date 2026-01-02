#!/usr/bin/env python3
"""
Script to run pre-commit linting and type checking hooks.
Outputs results to files for analysis.
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime

def run_command(cmd: list[str], output_file: Path, description: str) -> int:
    """Run a command and save output to file."""
    print(f"Running {description}...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=Path.cwd()
            )
        
        print(f"  Exit code: {result.returncode}")
        print(f"  Output saved to: {output_file}")
        return result.returncode
    except Exception as e:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Error running command: {e}\n")
        print(f"  Error: {e}")
        return 1

def main():
    """Run all linting and type checking commands."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("lint_outputs")
    output_dir.mkdir(exist_ok=True)
    
    results = {}
    
    # 1. Ruff check (linting)
    ruff_check_output = output_dir / f"ruff_check_{timestamp}.txt"
    ruff_check_cmd = [
        "uv", "run", "ruff", "--config", "dev/ruff.toml", 
        "check", "ccbt/", "--fix", "--exit-non-zero-on-fix"
    ]
    results["ruff_check"] = run_command(
        ruff_check_cmd, 
        ruff_check_output, 
        "Ruff check (linting)"
    )
    
    # 2. Ruff format (formatting)
    ruff_format_output = output_dir / f"ruff_format_{timestamp}.txt"
    ruff_format_cmd = [
        "uv", "run", "ruff", "--config", "dev/ruff.toml", 
        "format", "ccbt/"
    ]
    results["ruff_format"] = run_command(
        ruff_format_cmd,
        ruff_format_output,
        "Ruff format (formatting)"
    )
    
    # 3. Ty type checking
    ty_output = output_dir / f"ty_check_{timestamp}.txt"
    ty_cmd = [
        "uv", "run", "ty", "check", 
        "--config-file=dev/ty.toml", 
        "--output-format=concise"
    ]
    results["ty_check"] = run_command(
        ty_cmd,
        ty_output,
        "Ty type checking"
    )
    
    # 4. Compatibility linter (Python 3.8/3.9 compatibility)
    compatibility_output = output_dir / f"compatibility_linter_{timestamp}.txt"
    compatibility_cmd = [
        "uv", "run", "python", "dev/compatibility_linter.py", "ccbt/"
    ]
    results["compatibility_linter"] = run_command(
        compatibility_cmd,
        compatibility_output,
        "Compatibility linter (Python 3.8/3.9)"
    )
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, exit_code in results.items():
        status = "PASSED" if exit_code == 0 else "FAILED"
        print(f"{name:20s}: {status} (exit code: {exit_code})")
    
    print(f"\nAll outputs saved to: {output_dir}/")
    print(f"Latest files:")
    print(f"  - Ruff check: {ruff_check_output.name}")
    print(f"  - Ruff format: {ruff_format_output.name}")
    print(f"  - Ty check: {ty_output.name}")
    print(f"  - Compatibility linter: {compatibility_output.name}")
    
    # Return non-zero if any check failed
    return 0 if all(code == 0 for code in results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())












































