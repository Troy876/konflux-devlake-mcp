#!/usr/bin/env python3
"""
Test Runner for Konflux DevLake MCP Server

This script provides a convenient way to run different types of tests
with various options and configurations.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and handle the output."""
    if description:
        print(f"\n🔄 {description}")
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    return result.returncode == 0


def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking dependencies...")
    
    try:
        import pytest
        print(f"✅ pytest {pytest.__version__} is installed")
    except ImportError:
        print("❌ pytest is not installed. Run: pip install -r requirements.txt")
        return False
    
    try:
        import pytest_asyncio
        print(f"✅ pytest-asyncio is installed")
    except ImportError:
        print("❌ pytest-asyncio is not installed. Run: pip install -r requirements.txt")
        return False
    
    return True


def run_unit_tests(verbose=False, coverage=False, specific_test=None):
    """Run unit tests."""
    cmd = ["python", "-m", "pytest", "-m", "unit"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
    
    if specific_test:
        cmd.append(specific_test)
    
    return run_command(cmd, "Running unit tests")


def run_all_tests(verbose=False, coverage=False):
    """Run all tests."""
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
    
    return run_command(cmd, "Running all tests")


def run_security_tests(verbose=False):
    """Run security-related tests."""
    cmd = ["python", "-m", "pytest", "-m", "security"]
    
    if verbose:
        cmd.append("-v")
    
    return run_command(cmd, "Running security tests")


def run_specific_test_file(test_file, verbose=False):
    """Run a specific test file."""
    cmd = ["python", "-m", "pytest", test_file]
    
    if verbose:
        cmd.append("-v")
    
    return run_command(cmd, f"Running tests in {test_file}")


def lint_code():
    """Run code linting."""
    success = True
    
    # Run flake8
    if run_command(["python", "-m", "flake8", ".", "--exclude=tests"], "Running flake8 linting"):
        print("✅ flake8 linting passed")
    else:
        print("❌ flake8 linting failed")
        success = False
    
    # Run black check
    if run_command(["python", "-m", "black", "--check", "."], "Checking code formatting with black"):
        print("✅ black formatting check passed")
    else:
        print("❌ black formatting check failed. Run: python -m black .")
        success = False
    
    return success


def format_code():
    """Format code using black."""
    return run_command(["python", "-m", "black", "."], "Formatting code with black")


def type_check():
    """Run type checking with mypy."""
    return run_command(["python", "-m", "mypy", ".", "--ignore-missing-imports"], "Running type checking with mypy")


def clean_test_artifacts():
    """Clean test artifacts and cache files."""
    print("🧹 Cleaning test artifacts...")
    
    artifacts = [
        ".pytest_cache",
        "__pycache__",
        "htmlcov",
        ".coverage",
        "*.pyc",
        "*.pyo"
    ]
    
    for artifact in artifacts:
        if os.path.exists(artifact):
            if os.path.isdir(artifact):
                import shutil
                shutil.rmtree(artifact)
                print(f"Removed directory: {artifact}")
            else:
                os.remove(artifact)
                print(f"Removed file: {artifact}")
    
    # Clean __pycache__ directories recursively
    for root, dirs, files in os.walk("."):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                dir_path = os.path.join(root, dir_name)
                import shutil
                shutil.rmtree(dir_path)
                print(f"Removed directory: {dir_path}")


def main():
    """Main function to handle command line arguments and run tests."""
    parser = argparse.ArgumentParser(
        description="Test runner for Konflux DevLake MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --unit                    # Run unit tests only
  python run_tests.py --all --coverage          # Run all tests with coverage
  python run_tests.py --security                # Run security tests only
  python run_tests.py --file test_config.py     # Run specific test file
  python run_tests.py --lint                    # Run code linting
  python run_tests.py --format                  # Format code
  python run_tests.py --clean                   # Clean test artifacts
        """
    )
    
    # Test execution options
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--security", action="store_true", help="Run security tests only")
    parser.add_argument("--file", type=str, help="Run specific test file")
    parser.add_argument("--test", type=str, help="Run specific test (e.g., test_config.py::TestDatabaseConfig::test_defaults)")
    
    # Code quality options
    parser.add_argument("--lint", action="store_true", help="Run code linting")
    parser.add_argument("--format", action="store_true", help="Format code with black")
    parser.add_argument("--type-check", action="store_true", help="Run type checking with mypy")
    
    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    
    # Utility options
    parser.add_argument("--clean", action="store_true", help="Clean test artifacts and cache files")
    parser.add_argument("--check-deps", action="store_true", help="Check if dependencies are installed")
    
    args = parser.parse_args()
    
    # Change to the script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    success = True
    
    # Handle utility options first
    if args.clean:
        clean_test_artifacts()
        return
    
    if args.check_deps:
        if check_dependencies():
            print("✅ All dependencies are installed")
        else:
            print("❌ Some dependencies are missing")
            sys.exit(1)
        return
    
    # Check dependencies before running tests
    if not check_dependencies():
        print("❌ Cannot run tests without required dependencies")
        sys.exit(1)
    
    # Handle code quality options
    if args.lint:
        success = lint_code() and success
    
    if args.format:
        success = format_code() and success
    
    if args.type_check:
        success = type_check() and success
    
    # Handle test execution options
    if args.unit:
        success = run_unit_tests(args.verbose, args.coverage, args.test) and success
    elif args.security:
        success = run_security_tests(args.verbose) and success
    elif args.file:
        success = run_specific_test_file(args.file, args.verbose) and success
    elif args.all:
        success = run_all_tests(args.verbose, args.coverage) and success
    elif args.test:
        success = run_unit_tests(args.verbose, args.coverage, args.test) and success
    else:
        # Default: run unit tests
        success = run_unit_tests(args.verbose, args.coverage) and success
    
    # Print summary
    if success:
        print("\n✅ All operations completed successfully!")
    else:
        print("\n❌ Some operations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
