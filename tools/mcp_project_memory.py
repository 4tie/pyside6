import json
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("ProjectMemory")

_ROOT = Path(__file__).parent.parent
_DOCS = _ROOT / "docs"
_RULES = _ROOT / ".amazonq" / "rules" / "memory-bank"
_MEMORY_FILE = _ROOT / ".amazonq" / "project_facts.json"


def _load_facts() -> dict:
    if _MEMORY_FILE.exists():
        return json.loads(_MEMORY_FILE.read_text(encoding="utf8"))
    return {"paths": {}, "assumptions": {}, "workflow_rules": []}


def _save_facts(data: dict) -> None:
    _MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf8")


@mcp.tool()
def save_fact(category: str, key: str, value: str) -> str:
    """Save a project fact to persistent memory.

    Args:
        category: One of 'paths', 'assumptions', or 'workflow_rules'
        key: Fact key (ignored for workflow_rules, which is a list)
        value: Fact value
    """
    data = _load_facts()
    if category == "workflow_rules":
        if value not in data["workflow_rules"]:
            data["workflow_rules"].append(value)
    elif category in ("paths", "assumptions"):
        data.setdefault(category, {})[key] = value
    else:
        return f"Unknown category: {category}. Use 'paths', 'assumptions', or 'workflow_rules'."
    _save_facts(data)
    return f"Saved [{category}] {key}: {value}"


@mcp.tool()
def get_paths() -> dict:
    """Retrieve all saved project paths."""
    return _load_facts().get("paths", {})


@mcp.tool()
def save_workflow_rule(rule: str) -> str:
    """Append a workflow rule to project memory.

    Args:
        rule: The rule to remember (e.g. 'Always run pytest after editing services')
    """
    return save_fact("workflow_rules", "", rule)


@mcp.tool()
def get_assumptions() -> dict:
    """Retrieve all saved project assumptions."""
    return _load_facts().get("assumptions", {})


@mcp.tool()
def get_workflow_rules() -> list:
    """Retrieve all saved workflow rules."""
    return _load_facts().get("workflow_rules", [])


@mcp.tool()
def read_doc(name: str) -> str:
    """Read a file from docs/ by filename (e.g. 'AGENTS.md')."""
    p = _DOCS / name
    return p.read_text(encoding="utf8") if p.exists() else f"Not found: {name}"


@mcp.tool()
def list_docs() -> list:
    """List all files in docs/."""
    return [f.name for f in _DOCS.iterdir() if f.is_file()] if _DOCS.exists() else []


@mcp.tool()
def read_rule(name: str) -> str:
    """Read a memory-bank rule file (e.g. 'guidelines.md')."""
    p = _RULES / name
    return p.read_text(encoding="utf8") if p.exists() else f"Not found: {name}"


@mcp.tool()
def list_rules() -> list:
    """List all memory-bank rule files."""
    return [f.name for f in _RULES.iterdir() if f.is_file()] if _RULES.exists() else []


if __name__ == "__main__":
    mcp.run()
