import json
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("ProjectMemory")

_ROOT = Path(__file__).parent.parent
_DOCS = _ROOT / "data" / "docs" / "app_docs"
_RULES = _ROOT / "data" / "rules"
_MEMORY = _ROOT / "data" / "memory" / "project_facts.json"


def _load() -> dict:
    if _MEMORY.exists():
        return json.loads(_MEMORY.read_text(encoding="utf8"))
    return {"paths": {}, "assumptions": {}, "workflow_rules": []}


def _save(data: dict) -> None:
    _MEMORY.parent.mkdir(parents=True, exist_ok=True)
    _MEMORY.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf8")


@mcp.tool()
def save_fact(category: str, key: str, value: str) -> str:
    """Save a project fact. category: 'paths' | 'assumptions' | 'workflow_rules'."""
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


@mcp.tool()
def read_doc(name: str) -> str:
    """Read a file from data/docs/app_docs/ by filename (e.g. 'AGENTS.md')."""
    p = _DOCS / name
    return p.read_text(encoding="utf8") if p.exists() else f"Not found: {name}"


@mcp.tool()
def list_docs() -> list:
    """List all files in data/docs/app_docs/."""
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
