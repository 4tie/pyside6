"""Architecture linter test to enforce layer boundaries.

Validates that:
- No PySide6 imports exist in app/core/
- No app.ui or app.app_state imports exist in app/core/services/
- No app.ui imports exist in app/web/

This test can be run standalone or as part of pytest.
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple


def find_python_files(directory: Path) -> List[Path]:
    """Find all Python files in a directory recursively."""
    return list(directory.rglob("*.py"))


def check_file_for_patterns(
    file_path: Path,
    patterns: List[Tuple[str, str]],
) -> List[Tuple[int, str, str]]:
    """Check a file for forbidden import patterns.

    Args:
        file_path: Path to the Python file to check.
        patterns: List of (pattern_name, regex_pattern) tuples.

    Returns:
        List of (line_number, pattern_name, offending_line) tuples.
    """
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, start=1):
            for pattern_name, pattern in patterns:
                if re.search(pattern, line):
                    violations.append((line_num, pattern_name, line.strip()))
    except Exception:
        pass  # Skip files that can't be read
    
    return violations


def test_no_pyside6_in_core():
    """Requirement 1: No PySide6 imports in app/core/."""
    core_dir = Path(__file__).parent.parent / "app" / "core"
    if not core_dir.exists():
        return
    
    patterns = [
        ("PySide6 import", r"import\s+PySide6"),
        ("PySide6 from import", r"from\s+PySide6"),
    ]
    
    all_violations = []
    for py_file in find_python_files(core_dir):
        violations = check_file_for_patterns(py_file, patterns)
        for line_num, pattern_name, line in violations:
            all_violations.append(
                f"{py_file.relative_to(Path(__file__).parent.parent)}:{line_num} - {pattern_name}: {line}"
            )
    
    if all_violations:
        error_msg = "PySide6 imports found in app/core/:\n" + "\n".join(all_violations)
        assert False, error_msg


def test_no_ui_imports_in_services():
    """Requirement 2: No app.ui or app.app_state imports in app/core/services/."""
    services_dir = Path(__file__).parent.parent / "app" / "core" / "services"
    if not services_dir.exists():
        return
    
    patterns = [
        ("app.ui import", r"import\s+app\.ui"),
        ("app.ui from import", r"from\s+app\.ui"),
        ("app.app_state import", r"import\s+app\.app_state"),
        ("app.app_state from import", r"from\s+app\.app_state"),
    ]
    
    all_violations = []
    for py_file in find_python_files(services_dir):
        violations = check_file_for_patterns(py_file, patterns)
        for line_num, pattern_name, line in violations:
            all_violations.append(
                f"{py_file.relative_to(Path(__file__).parent.parent)}:{line_num} - {pattern_name}: {line}"
            )
    
    if all_violations:
        error_msg = "UI imports found in app/core/services/:\n" + "\n".join(all_violations)
        assert False, error_msg


def test_no_ui_imports_in_web():
    """Requirement 2: No app.ui imports in app/web/."""
    web_dir = Path(__file__).parent.parent / "app" / "web"
    if not web_dir.exists():
        return
    
    patterns = [
        ("app.ui import", r"import\s+app\.ui"),
        ("app.ui from import", r"from\s+app\.ui"),
    ]
    
    all_violations = []
    for py_file in find_python_files(web_dir):
        violations = check_file_for_patterns(py_file, patterns)
        for line_num, pattern_name, line in violations:
            all_violations.append(
                f"{py_file.relative_to(Path(__file__).parent.parent)}:{line_num} - {pattern_name}: {line}"
            )
    
    if all_violations:
        error_msg = "UI imports found in app/web/:\n" + "\n".join(all_violations)
        assert False, error_msg


def main():
    """Run the architecture linter as a standalone script."""
    import pytest
    
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
