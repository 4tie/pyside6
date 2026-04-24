"""Architecture linter — enforces layer boundary rules across app/.

Rules enforced:
1. No PySide6 imports in app/core/
2. No app.ui or app.app_state imports in app/core/services/
3. No app.ui imports in app/web/

Can be run as a pytest module or as a standalone script:
    python tests/test_architecture.py
"""
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ArchRule:
    """A single layer boundary rule."""

    name: str
    scan_dir: str           # directory to scan (relative to repo root)
    forbidden_patterns: List[str]  # regex patterns matched against each line


@dataclass
class Violation:
    """A single forbidden-import violation."""

    rule_name: str
    file_path: str   # relative to repo root
    line_number: int
    line_text: str   # offending line, stripped


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

RULES: List[ArchRule] = [
    ArchRule(
        name="No PySide6 in app/core/",
        scan_dir="app/core",
        forbidden_patterns=[r"^\s*(import|from)\s+PySide6"],
    ),
    ArchRule(
        name="No app.ui or app.app_state in app/core/services/",
        scan_dir="app/core/services",
        forbidden_patterns=[
            r"^\s*(import|from)\s+app\.ui",
            r"^\s*(import|from)\s+app\.app_state",
        ],
    ),
    ArchRule(
        name="No app.ui in app/web/",
        scan_dir="app/web",
        forbidden_patterns=[r"^\s*(import|from)\s+app\.ui"],
    ),
]

# Flat list of all forbidden patterns (used in property tests)
ALL_FORBIDDEN_PATTERNS: List[str] = [
    p for rule in RULES for p in rule.forbidden_patterns
]


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan_for_violations(rules: List[ArchRule], repo_root: Path) -> List[Violation]:
    """Scan all .py files under each rule's scan_dir and return all violations.

    Args:
        rules: List of ArchRule objects to enforce.
        repo_root: Absolute path to the repository root.

    Returns:
        List of Violation objects, one per offending line.
    """
    violations: List[Violation] = []

    for rule in rules:
        scan_path = repo_root / rule.scan_dir
        if not scan_path.exists():
            import warnings
            warnings.warn(f"scan_dir does not exist, skipping rule: {rule.name}")
            continue

        for py_file in scan_path.rglob("*.py"):
            try:
                lines = py_file.read_text(encoding="utf-8").splitlines()
            except Exception as exc:
                import warnings
                warnings.warn(f"Could not read {py_file}: {exc}")
                continue

            for line_number, line in enumerate(lines, start=1):
                for pattern in rule.forbidden_patterns:
                    if re.search(pattern, line):
                        violations.append(
                            Violation(
                                rule_name=rule.name,
                                file_path=str(py_file.relative_to(repo_root)),
                                line_number=line_number,
                                line_text=line.strip(),
                            )
                        )

    return violations


def format_violations(violations: List[Violation]) -> str:
    """Format violations into a human-readable string."""
    lines = [f"Architecture violations found ({len(violations)} total):"]
    for v in violations:
        lines.append(f"  [{v.rule_name}] {v.file_path}:{v.line_number}  {v.line_text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper for property tests (scans a source string, not a real file)
# ---------------------------------------------------------------------------

def _scan_source(source: str, patterns: List[str]) -> List[Violation]:
    """Scan a source string against a list of patterns; returns violations."""
    violations = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        for pattern in patterns:
            if re.search(pattern, line):
                violations.append(
                    Violation(
                        rule_name="test",
                        file_path="<test>",
                        line_number=line_number,
                        line_text=line.strip(),
                    )
                )
    return violations


# ---------------------------------------------------------------------------
# pytest test
# ---------------------------------------------------------------------------

def test_architecture_boundaries():
    """Fail if any forbidden cross-layer import is detected."""
    repo_root = Path(__file__).parent.parent
    violations = scan_for_violations(RULES, repo_root)
    assert violations == [], format_violations(violations)


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: web-layer-architecture, Property 1: Linter detects forbidden imports
@given(
    pattern=st.sampled_from([
        "import PySide6",
        "from PySide6 import",
        "from app.ui import",
        "import app.ui",
        "from app.app_state import",
    ]),
    prefix=st.text(
        alphabet=st.characters(whitelist_categories=("Zs",)),
        max_size=4,
    ),
)
@h_settings(max_examples=100)
def test_linter_detects_forbidden_import(pattern, prefix):
    """Property 1: Linter detects forbidden imports."""
    source = f"{prefix}{pattern} Something\n"
    # Use the first rule's patterns (PySide6) or app.ui patterns
    all_patterns = ALL_FORBIDDEN_PATTERNS
    violations = _scan_source(source, all_patterns)
    assert len(violations) >= 1


# Feature: web-layer-architecture, Property 2: Linter passes on clean files
@given(
    st.lists(
        st.text(alphabet=st.characters(blacklist_characters="\x00"), max_size=80),
        max_size=20,
    )
)
@h_settings(max_examples=100)
def test_linter_clean_on_safe_lines(lines):
    """Property 2: Linter passes on clean files."""
    safe_lines = [
        line for line in lines
        if not any(re.search(p, line) for p in ALL_FORBIDDEN_PATTERNS)
    ]
    source = "\n".join(safe_lines)
    violations = _scan_source(source, ALL_FORBIDDEN_PATTERNS)
    assert violations == []


# Feature: web-layer-architecture, Property 3: All violations reported in single pass
@given(st.integers(min_value=1, max_value=10))
@h_settings(max_examples=100)
def test_linter_reports_all_violations(n):
    """Property 3: All violations reported in single pass."""
    lines = [f"import PySide6.module{i}" for i in range(n)]
    source = "\n".join(lines)
    violations = _scan_source(source, [r"^\s*(import|from)\s+PySide6"])
    assert len(violations) == n


# Feature: web-layer-architecture, Property 4: Violation report contains path, line number, and import text
@given(
    line_number=st.integers(min_value=1, max_value=500),
    import_text=st.sampled_from([
        "import PySide6",
        "from PySide6.QtCore import Signal",
    ]),
)
@h_settings(max_examples=100)
def test_violation_report_structure(line_number, import_text):
    """Property 4: Violation report contains path, line number, and import text."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        lines = ["# safe line\n"] * (line_number - 1) + [import_text + "\n"]
        f = tmp_path / "test_module.py"
        f.write_text("".join(lines))

        # Create a rule that scans tmp_path
        rule = ArchRule(
            name="No PySide6 in app/core/",
            scan_dir=".",
            forbidden_patterns=[r"^\s*(import|from)\s+PySide6"],
        )
        violations = scan_for_violations([rule], tmp_path)

        assert len(violations) == 1
        v = violations[0]
        assert v.file_path != ""
        assert v.line_number == line_number
        assert import_text.strip() in v.line_text


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    violations = scan_for_violations(RULES, repo_root)
    if violations:
        print(format_violations(violations))
        sys.exit(1)
    else:
        print("No architecture violations found.")
        sys.exit(0)
