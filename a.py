#!/usr/bin/env python3
"""
PySide6 UI Application - Cache Management & Utility Script

This script provides command-line options to:
- Clear __pycache__ folders and .pyc files
- Validate paths (check if they exist)
- Validate virtual environments (check if venv is properly set up)
- Validate requirements.txt (check if file exists and parse for basic syntax)

Usage:
    python a.py --clear-cache
    python a.py --validate-paths /path/to/dir1 /path/to/dir2
    python a.py --validate-venv /path/to/venv
    python a.py --validate-req /path/to/requirements.txt
    Combine options as needed.

Options can be used together, e.g., --clear-cache --validate-paths .
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


def clear_cache(root_dir="."):
    """
    Recursively find and delete __pycache__ directories and .pyc files starting from root_dir.
    """
    root_path = Path(root_dir).resolve()
    if not root_path.exists():
        print(f"Error: Root directory '{root_dir}' does not exist.")
        return False

    deleted_items = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Remove __pycache__ directories
        if "__pycache__" in dirnames:
            pycache_path = Path(dirpath) / "__pycache__"
            try:
                shutil.rmtree(pycache_path)
                deleted_items.append(str(pycache_path))
                dirnames.remove("__pycache__")  # Prevent walking into it
            except Exception as e:
                print(f"Error deleting {pycache_path}: {e}")

        # Remove .pyc files
        for filename in filenames:
            if filename.endswith(".pyc"):
                pyc_file = Path(dirpath) / filename
                try:
                    pyc_file.unlink()
                    deleted_items.append(str(pyc_file))
                except Exception as e:
                    print(f"Error deleting {pyc_file}: {e}")

    if deleted_items:
        print(f"Cleared cache: {len(deleted_items)} items removed.")
        for item in deleted_items:
            print(f"  - {item}")
    else:
        print("No cache items found to clear.")
    return True


def validate_paths(*paths):
    """
    Validate if the given paths exist.
    """
    if not paths:
        print("Error: No paths provided for validation.")
        return False

    all_valid = True
    for path_str in paths:
        path = Path(path_str).resolve()
        if path.exists():
            print(f"✓ Path exists: {path}")
        else:
            print(f"✗ Path does not exist: {path}")
            all_valid = False
    return all_valid


def validate_venv(venv_path):
    """
    Validate if the given path is a valid virtual environment.
    Checks for key directories/files like bin/python, Scripts/python.exe (Windows), etc.
    """
    venv_path = Path(venv_path).resolve()
    if not venv_path.exists():
        print(f"✗ Virtual environment path does not exist: {venv_path}")
        return False

    # Check for platform-specific python executable
    if os.name == "nt":  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
    else:  # Unix-like
        python_exe = venv_path / "bin" / "python"

    if python_exe.exists():
        print(f"✓ Valid virtual environment: {venv_path} (found {python_exe})")
        return True
    else:
        print(f"✗ Invalid virtual environment: {venv_path} (missing {python_exe})")
        return False


def validate_req(req_file):
    """
    Validate requirements.txt: Check if file exists and parse for basic syntax.
    Does not install or check package availability.
    """
    req_path = Path(req_file).resolve()
    if not req_path.exists():
        print(f"✗ Requirements file does not exist: {req_path}")
        return False

    try:
        with open(req_path, "r") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"✗ Error reading requirements file: {e}")
        return False

    valid_lines = []
    invalid_lines = []
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # Skip empty or comment lines
        # Basic check: line should have package name (possibly with version)
        if (
            " " in stripped
            or "=" in stripped
            or ">" in stripped
            or "<" in stripped
            or stripped.isalnum()
        ):
            valid_lines.append((i, stripped))
        else:
            invalid_lines.append((i, stripped))

    if not invalid_lines:
        print(f"✓ Valid requirements file: {req_path} ({len(valid_lines)} entries)")
        return True
    else:
        print(f"✗ Invalid requirements file: {req_path}")
        for line_no, content in invalid_lines:
            print(f"  - Line {line_no}: '{content}' (possible syntax issue)")
        return False


def interactive_menu():
    """Interactive menu for running utility functions."""
    while True:
        print("\n=== PySide6 Utility Menu ===")
        print("1. Clear __pycache__ and .pyc files")
        print("2. Validate path(s)")
        print("3. Validate virtual environment")
        print("4. Validate requirements.txt")
        print("5. Run all validations")
        print("6. Exit")

        choice = input("\nEnter your choice (1-6): ").strip()

        if choice == "1":
            root_dir = input("Enter root directory (default '.'): ").strip() or "."
            clear_cache(root_dir)

        elif choice == "2":
            paths_input = input("Enter paths to validate (space-separated): ").strip()
            if paths_input:
                validate_paths(*paths_input.split())
            else:
                print("Error: No paths provided.")

        elif choice == "3":
            venv_path = input("Enter virtual environment path: ").strip()
            if venv_path:
                validate_venv(venv_path)
            else:
                print("Error: No venv path provided.")

        elif choice == "4":
            req_file = input("Enter requirements.txt path: ").strip()
            if req_file:
                validate_req(req_file)
            else:
                print("Error: No requirements file provided.")

        elif choice == "5":
            root_dir = (
                input("Enter root directory for cache clear (default '.'): ").strip()
                or "."
            )
            paths_input = input(
                "Enter paths to validate (space-separated, optional): "
            ).strip()
            venv_path = input("Enter virtual environment path (optional): ").strip()
            req_file = input("Enter requirements.txt path (optional): ").strip()

            success = True
            success &= clear_cache(root_dir)
            if paths_input:
                success &= validate_paths(*paths_input.split())
            if venv_path:
                success &= validate_venv(venv_path)
            if req_file:
                success &= validate_req(req_file)

            print(f"\nOverall: {'SUCCESS' if success else 'FAILURE'}")

        elif choice == "6":
            print("Exiting...")
            sys.exit(0)

        else:
            print("Invalid choice. Please enter a number between 1 and 6.")


def main():
    parser = argparse.ArgumentParser(
        description="PySide6 Python Utility Script for Cache Management and Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --clear-cache
  %(prog)s --validate-paths /path/to/dir1 /path/to/dir2
  %(prog)s --validate-venv /path/to/venv
  %(prog)s --validate-req /path/to/requirements.txt
        """,
    )

    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear __pycache__ folders and .pyc files",
    )
    parser.add_argument(
        "--root-dir",
        default=".",
        help="Root directory for cache clearing (default: current dir)",
    )
    parser.add_argument(
        "--validate-paths",
        nargs="*",
        help="Validate if paths exist (one or more paths)",
    )
    parser.add_argument("--validate-venv", help="Validate virtual environment path")
    parser.add_argument("--validate-req", help="Validate requirements.txt file")
    parser.add_argument(
        "--interactive", action="store_true", help="Start interactive menu mode"
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_menu()
        return

    success = True

    if args.clear_cache:
        success &= clear_cache(args.root_dir)

    if args.validate_paths:
        success &= validate_paths(*args.validate_paths)

    if args.validate_venv:
        success &= validate_venv(args.validate_venv)

    if args.validate_req:
        success &= validate_req(args.validate_req)

    if not any(
        [args.clear_cache, args.validate_paths, args.validate_venv, args.validate_req]
    ):
        parser.print_help()
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
