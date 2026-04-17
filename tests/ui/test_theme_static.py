"""Static analysis test: no bare hex colour literals outside theme.py.

Property 3: No hex literals outside theme module
Validates: Requirements 1.5, 2.3
"""
import re
from pathlib import Path

# Pattern for hex colour literals: # followed by 3-6 hex digits, word boundary
_HEX_PATTERN = re.compile(r'#[0-9a-fA-F]{3,6}\b')

# Files modified in this spec that must be clean
_TARGET_FILES = [
    Path("app/ui/main_window.py"),
    Path("app/ui/pages/backtest_page.py"),
    Path("app/ui/pages/download_data_page.py"),
    Path("app/ui/pages/optimize_page.py"),
    Path("app/ui/pages/strategy_config_page.py"),
    Path("app/ui/widgets/backtest_results_widget.py"),
]


def _is_comment_line(line: str) -> bool:
    """Return True if the line is a pure comment line."""
    return line.strip().startswith('#')


def _strip_inline_comment(line: str) -> str:
    """Remove inline comment from a line, respecting string literals."""
    in_string = False
    quote_char = None
    for i, ch in enumerate(line):
        if not in_string and ch in ('"', "'"):
            in_string = True
            quote_char = ch
        elif in_string and ch == quote_char:
            in_string = False
            quote_char = None
        elif not in_string and ch == '#':
            return line[:i]
    return line


def _find_hex_literals_in_file(path: Path) -> list:
    """Return list of (line_number, line_content) for lines with hex literals."""
    violations = []
    content = path.read_text(encoding='utf-8')
    for lineno, line in enumerate(content.splitlines(), 1):
        # Skip pure comment lines
        if _is_comment_line(line):
            continue
        # Skip setObjectName calls (they use # for Qt object names, not colours)
        if 'setObjectName' in line:
            continue
        # Remove inline comments before checking
        code_part = _strip_inline_comment(line)
        # Check for hex literals in the code part
        if _HEX_PATTERN.search(code_part):
            violations.append((lineno, line.rstrip()))
    return violations


def test_no_hex_literals_outside_theme():
    """Property 3: No bare hex colour literals in spec-modified files.

    Checks the files modified in the app-theme-redesign spec to ensure all
    inline hex colour literals have been replaced with theme.py references
    or setObjectName calls.

    **Validates: Requirements 1.5, 2.3**
    """
    violations = {}

    for py_file in _TARGET_FILES:
        if not py_file.exists():
            continue
        file_violations = _find_hex_literals_in_file(py_file)
        if file_violations:
            violations[str(py_file)] = file_violations

    if violations:
        msg_parts = ['Found bare hex colour literals in spec-modified files:']
        for filepath, lines in violations.items():
            msg_parts.append(f'\n  {filepath}:')
            for lineno, line in lines[:5]:  # Show max 5 per file
                msg_parts.append(f'    Line {lineno}: {line}')
        assert False, '\n'.join(msg_parts)
