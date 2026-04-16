import json
import subprocess
import sys
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("ProjectMemory")

_ROOT = Path(__file__).parent.parent
_DOCS = _ROOT / "data" / "docs"
_RULES = _ROOT / "data" / "rules"
_MEMORY = _ROOT / "data" / "memory" / "project_facts.json"
_TOOLS = _ROOT / "data" / "tools"
_PYTHON = sys.executable


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _load() -> dict:
    if _MEMORY.exists():
        return json.loads(_MEMORY.read_text(encoding="utf8"))
    return {"paths": {}, "assumptions": {}, "workflow_rules": []}


def _save(data: dict) -> None:
    _MEMORY.parent.mkdir(parents=True, exist_ok=True)
    _MEMORY.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf8")


def _run_script(script: str, args: list[str]) -> dict:
    """Run a tool script and return {passed, output}."""
    result = subprocess.run(
        [_PYTHON, str(_TOOLS / script)] + args,
        capture_output=True, text=True, cwd=str(_ROOT),
    )
    return {
        "passed": result.returncode == 0,
        "output": (result.stdout + result.stderr).strip(),
    }


# ─────────────────────────────────────────────
# Step 4 — Validate
# ─────────────────────────────────────────────

@mcp.tool()
def run_checks(fast: bool = False) -> dict:
    """Step 4: Run all project checks (pytest + ruff + structure).

    Args:
        fast: If True, stop on first failure (-x flag for pytest).

    Returns:
        {"passed": bool, "output": str}
    """
    args = ["--fast"] if fast else []
    return _run_script("run_checks.py", args)


# ─────────────────────────────────────────────
# Step 5 — Summarize
# ─────────────────────────────────────────────

@mcp.tool()
def write_update_summary(feature: str, change_type: str = "feat",
                         append_changelog: bool = False,
                         skip_tests: bool = False) -> dict:
    """Step 5: Generate a change report from git diff + test results.

    Args:
        feature: Short name for the change (e.g. 'fix backtest zip path').
        change_type: One of fix | feat | refactor | docs | chore.
        append_changelog: If True, append to CHANGELOG.md instead of updates/.
        skip_tests: If True, skip running tests in the report.

    Returns:
        {"passed": bool, "output": str, "report_path": str}
    """
    args = ["--feature", feature, "--type", change_type]
    if append_changelog:
        args.append("--append-changelog")
    if skip_tests:
        args.append("--skip-tests")
    result = _run_script("post_change_report.py", args)
    # Extract report path from output
    report_path = ""
    for line in result["output"].splitlines():
        if "Report written to" in line or "Appended to" in line:
            report_path = line.split("to", 1)[-1].strip()
    result["report_path"] = report_path
    return result


@mcp.tool()
def update_changelog(change_type: str, description: str,
                     files: str = "", why: str = "",
                     verified: str = "manual test",
                     breaking: bool = False,
                     breaking_desc: str = "") -> dict:
    """Step 5 (alt): Add a structured entry directly to CHANGELOG.md.

    Args:
        change_type: fix | feat | refactor | docs | chore.
        description: Short description of what changed.
        files: Comma-separated list of changed files.
        why: Reason for the change.
        verified: How it was verified.
        breaking: Whether this is a breaking change.
        breaking_desc: Description of the breaking change.

    Returns:
        {"passed": bool, "output": str}
    """
    args = ["--type", change_type, "--desc", description]
    if files:
        args += ["--files", files]
    if why:
        args += ["--why", why]
    if verified:
        args += ["--verified", verified]
    if breaking:
        args.append("--breaking")
    if breaking_desc:
        args += ["--breaking-desc", breaking_desc]
    return _run_script("update_changelog.py", args)


# ─────────────────────────────────────────────
# Step 7 — Commit
# ─────────────────────────────────────────────

@mcp.tool()
def generate_commit_message(change_type: str = None,
                             scope: str = None,
                             body: str = None,
                             breaking: bool = False) -> dict:
    """Step 7: Generate a conventional commit message from staged files.

    Args:
        change_type: Override inferred type (fix|feat|refactor|docs|chore).
        scope: Override inferred scope.
        body: Optional commit body text.
        breaking: Mark as breaking change.

    Returns:
        {"passed": bool, "output": str}
    """
    args = []
    if change_type:
        args += ["--type", change_type]
    if scope:
        args += ["--scope", scope]
    if body:
        args += ["--body", body]
    if breaking:
        args.append("--breaking")
    return _run_script("make_commit_message.py", args)


# ─────────────────────────────────────────────
# Memory — facts, paths, assumptions, rules
# ─────────────────────────────────────────────

@mcp.tool()
def save_fact(category: str, key: str, value: str) -> str:
    """Persist a project fact. category: 'paths' | 'assumptions' | 'workflow_rules'."""
    data = _load()
    if category == "workflow_rules":
        if value not in data["workflow_rules"]:
            data["workflow_rules"].append(value)
    elif category in ("paths", "assumptions"):
        data.setdefault(category, {})[key] = value
    else:
        return f"Unknown category: {category}"
    _save(data)
    return f"Saved [{category}] {key}: {value}"


@mcp.tool()
def get_paths() -> dict:
    """Retrieve all saved project paths."""
    return _load().get("paths", {})


@mcp.tool()
def get_assumptions() -> dict:
    """Retrieve all saved project assumptions."""
    return _load().get("assumptions", {})


@mcp.tool()
def save_workflow_rule(rule: str) -> str:
    """Append a workflow rule to project memory."""
    return save_fact("workflow_rules", "", rule)


@mcp.tool()
def get_workflow_rules() -> list:
    """Retrieve all saved workflow rules."""
    return _load().get("workflow_rules", [])


# ─────────────────────────────────────────────
# Knowledge — docs and rules
# ─────────────────────────────────────────────

@mcp.tool()
def read_doc(name: str) -> str:
    """Read a file from data/docs/ by filename (e.g. 'AGENTS.md', 'WORKFLOW.md')."""
    p = _DOCS / name
    return p.read_text(encoding="utf8") if p.exists() else f"Not found: {name}"


@mcp.tool()
def list_docs() -> list:
    """List all files in data/docs/ (top-level only)."""
    return [f.name for f in _DOCS.iterdir() if f.is_file()] if _DOCS.exists() else []


@mcp.tool()
def read_rule(name: str) -> str:
    """Read a rule file from data/rules/ (e.g. 'guidelines.md')."""
    p = _RULES / name
    return p.read_text(encoding="utf8") if p.exists() else f"Not found: {name}"


@mcp.tool()
def list_rules() -> list:
    """List all files in data/rules/."""
    return [f.name for f in _RULES.iterdir() if f.is_file()] if _RULES.exists() else []


if __name__ == "__main__":
    mcp.run()
