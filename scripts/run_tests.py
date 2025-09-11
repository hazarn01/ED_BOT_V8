#!/usr/bin/env python3
"""
Test runner script for ED Bot v8.
Provides convenient test execution with different options.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Use the current Python interpreter for all subprocess calls
PYTHON = sys.executable or "python"

def run_tests(test_type="all", verbose=False, coverage=False, marker=None):
    """Run tests with specified options."""
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Build pytest command
    cmd = [PYTHON, "-m", "pytest"]
    
    # Add test paths based on type
    if test_type == "unit":
        cmd.append("tests/unit/")
    elif test_type == "integration":
        cmd.append("tests/integration/")
    elif test_type == "all":
        cmd.append("tests/")
    else:
        cmd.append(test_type)  # Assume it's a specific path
    
    # Add options
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=html", "--cov-report=term"])
    
    if marker:
        cmd.extend(["-m", marker])
    
    # Add asyncio mode
    cmd.append("--asyncio-mode=auto")
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ Tests completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code {e.returncode}")
        return False

def run_linting():
    """Run code linting."""
    print("Running code linting...")
    
    linting_commands = [
        [PYTHON, "-m", "ruff", "check", "src/"],
        [PYTHON, "-m", "ruff", "check", "tests/"],
        [PYTHON, "-m", "ruff", "format", "--check", "src/"],
        [PYTHON, "-m", "ruff", "format", "--check", "tests/"]
    ]
    
    all_passed = True
    
    for cmd in linting_commands:
        try:
            print(f"Running: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            all_passed = False
    
    if all_passed:
        print("✅ All linting checks passed!")
    else:
        print("❌ Some linting checks failed")
    
    return all_passed

def run_type_checking():
    """Run type checking."""
    print("Running type checking...")
    
    try:
        cmd = [PYTHON, "-m", "mypy", "src/", "--ignore-missing-imports"]
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        print("✅ Type checking passed!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Type checking failed")
        return False

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="ED Bot v8 Test Runner")
    
    parser.add_argument(
        "test_type", 
        nargs="?", 
        default="all",
        help="Type of tests to run: unit, integration, all, or specific path"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "-c", "--coverage",
        action="store_true", 
        help="Run with coverage report"
    )
    
    parser.add_argument(
        "-m", "--marker",
        help="Run tests with specific pytest marker"
    )
    
    parser.add_argument(
        "-l", "--lint",
        action="store_true",
        help="Run linting checks"
    )
    
    parser.add_argument(
        "-t", "--type-check",
        action="store_true",
        help="Run type checking"
    )
    
    parser.add_argument(
        "--all-checks",
        action="store_true",
        help="Run all checks: tests, linting, and type checking"
    )
    
    args = parser.parse_args()
    
    success = True
    
    if args.all_checks:
        print("🚀 Running all checks...")
        
        print("\n1. Running tests...")
        success &= run_tests(args.test_type, args.verbose, args.coverage, args.marker)
        
        print("\n2. Running linting...")
        success &= run_linting()
        
        print("\n3. Running type checking...")
        success &= run_type_checking()
        
        if success:
            print("\n🎉 All checks passed!")
        else:
            print("\n💥 Some checks failed!")
    
    else:
        if args.lint:
            success &= run_linting()
        
        if args.type_check:
            success &= run_type_checking()
        
        if not args.lint and not args.type_check:
            success &= run_tests(args.test_type, args.verbose, args.coverage, args.marker)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
