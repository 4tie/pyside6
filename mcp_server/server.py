#!/usr/bin/env python3
"""
Freqtrade GUI — MCP File Server
================================
Exposes workspace file operations as MCP tools so any MCP-compatible AI
(Kiro, Claude Desktop, Cursor, etc.) can read, write, search, and edit
files in this project without friction.

Tools exposed
-------------
- read_file          : Read a file's full content (with optional line range)
- write_file         : Create or overwrite a file
- edit_file          : Replace an exact string block inside a file
- append_file        : Append text to the end of a file
- delete_file        : Delete a file
- list_directory     : List directory contents (recursive optional)
- search_text        : Regex/literal search across files (ripgrep-style)
- search_files       : Find files by name pattern
- get_diagnostics    : Return Python syntax errors for a file
- run_tests          : Run pytest for a path/file and return output
- read_multiple_files: Read several files in one call

Transport: stdio (JSON-RPC 2.0 over stdin/stdout)
"""

import json
import os
import re
import subprocess
import sys
import ast
from pathlib import Path
from typing import Any

# ── Project root is one level up from this file ──────────────────────────────
ROOT = Path(__file__).parent.parent.resolve()

# ── MCP protocol helpers ──────────────────────────────────────────────────────

def _ok(content: str) -> dict:
    return {"content": [{"type": "text", "text": content}]}


def _err(msg: str) -> dict:
    return {"content": [{"type": "text", "text": f"ERROR: {msg}"}], "isError": True}


def _resolve(rel: str) -> Path:
    """Resolve a relative path against ROOT, refusing path traversal."""
    p = (ROOT / rel).resolve()
    if not str(p).startswith(str(ROOT)):
        raise ValueError(f"Path '{rel}' escapes workspace root")
    return p


# ── Tool implementations ──────────────────────────────────────────────────────

def tool_read_file(args: dict) -> dict:
    """Read a file, optionally limited to a line range."""
    path_str: str = args.get("path", "")
    start: int | None = args.get("start_line")
    end: int | None = args.get("end_line")

    if not path_str:
        return _err("'path' is required")
    try:
        p = _resolve(path_str)
        if not p.exists():
            return _err(f"File not found: {path_str}")
        if not p.is_file():
            return _err(f"Not a file: {path_str}")

        lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        total = len(lines)

        if start is not None or end is not None:
            s = max(0, (start or 1) - 1)
            e = (end or total)
            selected = lines[s:e]
            content = "".join(selected)
            header = f"# {path_str}  [lines {s+1}–{min(e, total)} of {total}]\n\n"
        else:
            content = "".join(lines)
            header = f"# {path_str}  [{total} lines]\n\n"

        return _ok(header + content)
    except Exception as exc:
        return _err(str(exc))


def tool_read_multiple_files(args: dict) -> dict:
    """Read several files and return them concatenated."""
    paths: list[str] = args.get("paths", [])
    if not paths:
        return _err("'paths' list is required")

    parts: list[str] = []
    for rel in paths:
        try:
            p = _resolve(rel)
            if not p.exists() or not p.is_file():
                parts.append(f"# {rel}\nERROR: file not found\n")
            else:
                text = p.read_text(encoding="utf-8", errors="replace")
                parts.append(f"# {rel}\n\n{text}\n")
        except Exception as exc:
            parts.append(f"# {rel}\nERROR: {exc}\n")

    return _ok("\n---\n".join(parts))


def tool_write_file(args: dict) -> dict:
    """Create or overwrite a file with the given content."""
    path_str: str = args.get("path", "")
    content: str = args.get("content", "")

    if not path_str:
        return _err("'path' is required")
    try:
        p = _resolve(path_str)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return _ok(f"Written {len(content)} bytes to {path_str}")
    except Exception as exc:
        return _err(str(exc))


def tool_edit_file(args: dict) -> dict:
    """Replace an exact string block inside a file (like str_replace)."""
    path_str: str = args.get("path", "")
    old_str: str = args.get("old_str", "")
    new_str: str = args.get("new_str", "")

    if not path_str:
        return _err("'path' is required")
    if old_str == new_str:
        return _err("'old_str' and 'new_str' are identical — nothing to do")
    try:
        p = _resolve(path_str)
        if not p.exists():
            return _err(f"File not found: {path_str}")

        original = p.read_text(encoding="utf-8")
        count = original.count(old_str)
        if count == 0:
            return _err(
                f"'old_str' not found in {path_str}.\n"
                "Tip: make sure whitespace and indentation match exactly."
            )
        if count > 1:
            return _err(
                f"'old_str' matches {count} locations in {path_str}. "
                "Add more surrounding context to make it unique."
            )

        updated = original.replace(old_str, new_str, 1)
        p.write_text(updated, encoding="utf-8")
        return _ok(f"Replaced 1 occurrence in {path_str}")
    except Exception as exc:
        return _err(str(exc))


def tool_append_file(args: dict) -> dict:
    """Append text to the end of an existing file."""
    path_str: str = args.get("path", "")
    content: str = args.get("content", "")

    if not path_str:
        return _err("'path' is required")
    try:
        p = _resolve(path_str)
        if not p.exists():
            return _err(f"File not found: {path_str}. Use write_file to create it first.")

        existing = p.read_text(encoding="utf-8")
        separator = "" if existing.endswith("\n") else "\n"
        p.write_text(existing + separator + content, encoding="utf-8")
        return _ok(f"Appended {len(content)} bytes to {path_str}")
    except Exception as exc:
        return _err(str(exc))


def tool_delete_file(args: dict) -> dict:
    """Delete a file."""
    path_str: str = args.get("path", "")
    if not path_str:
        return _err("'path' is required")
    try:
        p = _resolve(path_str)
        if not p.exists():
            return _err(f"File not found: {path_str}")
        if p.is_dir():
            return _err(f"'{path_str}' is a directory. Only files can be deleted.")
        p.unlink()
        return _ok(f"Deleted {path_str}")
    except Exception as exc:
        return _err(str(exc))


def tool_list_directory(args: dict) -> dict:
    """List directory contents. Set recursive=true for a full tree."""
    path_str: str = args.get("path", ".")
    recursive: bool = args.get("recursive", False)
    max_depth: int = args.get("max_depth", 4)

    try:
        p = _resolve(path_str)
        if not p.exists():
            return _err(f"Path not found: {path_str}")
        if not p.is_dir():
            return _err(f"Not a directory: {path_str}")

        lines: list[str] = [f"Directory: {path_str}\n"]

        # Directories to skip
        SKIP = {".git", "__pycache__", ".venv", ".pytest_cache", ".hypothesis",
                "node_modules", ".mypy_cache", ".ruff_cache"}

        def _walk(directory: Path, prefix: str, depth: int) -> None:
            if depth > max_depth:
                lines.append(f"{prefix}... (max depth reached)\n")
                return
            try:
                entries = sorted(directory.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
            except PermissionError:
                lines.append(f"{prefix}[permission denied]\n")
                return

            for i, entry in enumerate(entries):
                if entry.name in SKIP:
                    continue
                connector = "└── " if i == len(entries) - 1 else "├── "
                kind = "/" if entry.is_dir() else ""
                lines.append(f"{prefix}{connector}{entry.name}{kind}\n")
                if entry.is_dir() and recursive:
                    extension = "    " if i == len(entries) - 1 else "│   "
                    _walk(entry, prefix + extension, depth + 1)

        _walk(p, "", 1)
        return _ok("".join(lines))
    except Exception as exc:
        return _err(str(exc))


def tool_search_text(args: dict) -> dict:
    """Search for a regex/literal pattern across workspace files."""
    query: str = args.get("query", "")
    include_pattern: str = args.get("include_pattern", "")
    exclude_pattern: str = args.get("exclude_pattern", "")
    case_sensitive: bool = args.get("case_sensitive", False)
    max_results: int = min(args.get("max_results", 50), 200)

    if not query:
        return _err("'query' is required")

    try:
        # Try ripgrep first, fall back to pure Python
        cmd = ["rg", "--line-number", "--no-heading", "--with-filename"]
        if not case_sensitive:
            cmd.append("--ignore-case")
        if include_pattern:
            cmd += ["--glob", include_pattern]
        if exclude_pattern:
            cmd += ["--glob", f"!{exclude_pattern}"]
        cmd += ["--max-count", "5", query, str(ROOT)]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        raw = result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Pure-Python fallback
        raw = _python_search(query, include_pattern, exclude_pattern, case_sensitive, max_results)

    lines = raw.splitlines()[:max_results]
    if not lines:
        return _ok(f"No matches found for: {query}")

    # Make paths relative to ROOT
    rel_lines: list[str] = []
    for line in lines:
        try:
            abs_path, rest = line.split(":", 1)
            rel = Path(abs_path).relative_to(ROOT)
            rel_lines.append(f"{rel}:{rest}")
        except (ValueError, TypeError):
            rel_lines.append(line)

    summary = f"Found {len(rel_lines)} match(es) for '{query}':\n\n"
    return _ok(summary + "\n".join(rel_lines))


def _python_search(
    query: str,
    include_pattern: str,
    exclude_pattern: str,
    case_sensitive: bool,
    max_results: int,
) -> str:
    """Pure-Python text search fallback when ripgrep is unavailable."""
    SKIP_DIRS = {".git", "__pycache__", ".venv", ".pytest_cache", ".hypothesis"}
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags)
    except re.error as exc:
        return f"Invalid regex: {exc}"

    include_re = re.compile(
        re.escape(include_pattern).replace(r"\*", ".*"), re.IGNORECASE
    ) if include_pattern else None
    exclude_re = re.compile(
        re.escape(exclude_pattern).replace(r"\*", ".*"), re.IGNORECASE
    ) if exclude_pattern else None

    results: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            rel = str(fpath.relative_to(ROOT))
            if include_re and not include_re.search(rel):
                continue
            if exclude_re and exclude_re.search(rel):
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
                for lineno, line in enumerate(text.splitlines(), 1):
                    if pattern.search(line):
                        results.append(f"{fpath}:{lineno}:{line.rstrip()}")
                        if len(results) >= max_results:
                            return "\n".join(results)
            except (OSError, PermissionError):
                continue
    return "\n".join(results)


def tool_search_files(args: dict) -> dict:
    """Find files by name pattern (glob or substring)."""
    pattern: str = args.get("pattern", "")
    path_str: str = args.get("path", ".")

    if not pattern:
        return _err("'pattern' is required")

    SKIP_DIRS = {".git", "__pycache__", ".venv", ".pytest_cache", ".hypothesis"}

    try:
        base = _resolve(path_str)
        matches: list[str] = []

        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                rel = str(fpath.relative_to(ROOT))
                # Support glob-style * wildcard or plain substring
                if "*" in pattern:
                    import fnmatch
                    if fnmatch.fnmatch(fname, pattern) or fnmatch.fnmatch(rel, pattern):
                        matches.append(rel)
                else:
                    if pattern.lower() in fname.lower():
                        matches.append(rel)
                if len(matches) >= 100:
                    break

        if not matches:
            return _ok(f"No files matching '{pattern}' found under {path_str}")
        return _ok(f"Found {len(matches)} file(s):\n\n" + "\n".join(sorted(matches)))
    except Exception as exc:
        return _err(str(exc))


def tool_get_diagnostics(args: dict) -> dict:
    """Return Python syntax errors for a file using ast.parse."""
    path_str: str = args.get("path", "")
    if not path_str:
        return _err("'path' is required")
    try:
        p = _resolve(path_str)
        if not p.exists():
            return _err(f"File not found: {path_str}")

        source = p.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(p))
            return _ok(f"No syntax errors found in {path_str}")
        except SyntaxError as exc:
            return _ok(
                f"SyntaxError in {path_str}:\n"
                f"  Line {exc.lineno}: {exc.msg}\n"
                f"  {exc.text or ''}"
            )
    except Exception as exc:
        return _err(str(exc))


def tool_run_tests(args: dict) -> dict:
    """Run pytest for a given path and return the output."""
    path_str: str = args.get("path", "tests/")
    extra_args: list[str] = args.get("extra_args", [])
    timeout: int = args.get("timeout", 60)

    try:
        target = _resolve(path_str)
        python = ROOT / ".venv" / "bin" / "python"
        if not python.exists():
            python = Path(sys.executable)

        cmd = [str(python), "-m", "pytest", str(target), "--tb=short", "-q"] + extra_args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT),
        )
        output = result.stdout + result.stderr
        return _ok(output or "(no output)")
    except subprocess.TimeoutExpired:
        return _err(f"Tests timed out after {timeout}s")
    except Exception as exc:
        return _err(str(exc))


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS: dict[str, dict] = {
    "read_file": {
        "description": (
            "Read a file's content. Optionally limit to a line range with "
            "start_line / end_line (1-indexed, inclusive)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root"},
                "start_line": {"type": "integer", "description": "First line to return (1-indexed)"},
                "end_line": {"type": "integer", "description": "Last line to return (1-indexed, inclusive)"},
            },
            "required": ["path"],
        },
        "handler": tool_read_file,
    },
    "read_multiple_files": {
        "description": "Read several files in one call. Returns each file's content separated by ---.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of relative paths from workspace root",
                },
            },
            "required": ["paths"],
        },
        "handler": tool_read_multiple_files,
    },
    "write_file": {
        "description": "Create or fully overwrite a file. Parent directories are created automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root"},
                "content": {"type": "string", "description": "Full file content to write"},
            },
            "required": ["path", "content"],
        },
        "handler": tool_write_file,
    },
    "edit_file": {
        "description": (
            "Replace an exact string block inside a file. "
            "'old_str' must match exactly one location (include enough context lines to be unique). "
            "'new_str' is the replacement. Whitespace and indentation must match exactly."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root"},
                "old_str": {"type": "string", "description": "Exact text to find (must be unique in the file)"},
                "new_str": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_str", "new_str"],
        },
        "handler": tool_edit_file,
    },
    "append_file": {
        "description": "Append text to the end of an existing file. Adds a newline separator if needed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root"},
                "content": {"type": "string", "description": "Text to append"},
            },
            "required": ["path", "content"],
        },
        "handler": tool_append_file,
    },
    "delete_file": {
        "description": "Delete a file. Only works on files, not directories.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root"},
            },
            "required": ["path"],
        },
        "handler": tool_delete_file,
    },
    "list_directory": {
        "description": (
            "List directory contents as a tree. "
            "Set recursive=true to walk subdirectories (max_depth default 4). "
            "Skips .git, __pycache__, .venv, etc."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root (default '.')"},
                "recursive": {"type": "boolean", "description": "Walk subdirectories (default false)"},
                "max_depth": {"type": "integer", "description": "Max recursion depth (default 4)"},
            },
        },
        "handler": tool_list_directory,
    },
    "search_text": {
        "description": (
            "Search for a regex or literal pattern across workspace files. "
            "Uses ripgrep if available, otherwise pure Python. "
            "Returns file:line:content matches."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Regex or literal search pattern"},
                "include_pattern": {"type": "string", "description": "Glob to restrict files, e.g. '**/*.py'"},
                "exclude_pattern": {"type": "string", "description": "Glob to exclude files, e.g. '*.log'"},
                "case_sensitive": {"type": "boolean", "description": "Case-sensitive search (default false)"},
                "max_results": {"type": "integer", "description": "Max matches to return (default 50, max 200)"},
            },
            "required": ["query"],
        },
        "handler": tool_search_text,
    },
    "search_files": {
        "description": (
            "Find files by name pattern. Supports glob wildcards (e.g. '*.py') "
            "or plain substring match. Returns relative paths."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Filename pattern or substring"},
                "path": {"type": "string", "description": "Directory to search under (default '.')"},
            },
            "required": ["pattern"],
        },
        "handler": tool_search_files,
    },
    "get_diagnostics": {
        "description": "Check a Python file for syntax errors using ast.parse. Returns errors or a clean message.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to a Python file"},
            },
            "required": ["path"],
        },
        "handler": tool_get_diagnostics,
    },
    "run_tests": {
        "description": (
            "Run pytest for a given path (file or directory) and return the output. "
            "Uses the project's .venv Python. Default path is 'tests/'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Test file or directory (default 'tests/')"},
                "extra_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra pytest arguments, e.g. ['-k', 'test_backtest', '-v']",
                },
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)"},
            },
        },
        "handler": tool_run_tests,
    },
}


# ── JSON-RPC 2.0 / MCP dispatcher ─────────────────────────────────────────────

def _jsonrpc_response(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _jsonrpc_error(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def handle_request(req: dict) -> dict | None:
    """Dispatch a single JSON-RPC request and return the response (or None for notifications)."""
    method: str = req.get("method", "")
    params: dict = req.get("params") or {}
    req_id = req.get("id")

    # ── MCP lifecycle ──────────────────────────────────────────────────────────
    if method == "initialize":
        return _jsonrpc_response(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "freqtrade-gui-mcp", "version": "1.0.0"},
        })

    if method == "notifications/initialized":
        return None  # notification — no response

    if method == "ping":
        return _jsonrpc_response(req_id, {})

    # ── Tool listing ───────────────────────────────────────────────────────────
    if method == "tools/list":
        tool_list = [
            {
                "name": name,
                "description": meta["description"],
                "inputSchema": meta["inputSchema"],
            }
            for name, meta in TOOLS.items()
        ]
        return _jsonrpc_response(req_id, {"tools": tool_list})

    # ── Tool execution ─────────────────────────────────────────────────────────
    if method == "tools/call":
        tool_name: str = params.get("name", "")
        tool_args: dict = params.get("arguments") or {}

        if tool_name not in TOOLS:
            return _jsonrpc_error(req_id, -32601, f"Unknown tool: {tool_name}")

        try:
            result = TOOLS[tool_name]["handler"](tool_args)
            return _jsonrpc_response(req_id, result)
        except Exception as exc:
            return _jsonrpc_response(req_id, _err(f"Unhandled exception: {exc}"))

    # ── Unknown method ─────────────────────────────────────────────────────────
    if req_id is not None:
        return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")
    return None  # unknown notification — ignore


# ── Main stdio loop ───────────────────────────────────────────────────────────

def _read_one_object(stdin) -> "dict | None":
    """
    Read exactly one JSON object from stdin, handling embedded literal newlines.

    Real MCP clients (Kiro, Claude Desktop, etc.) send proper ndjson where
    \\n inside string values is the two-character escape sequence.  But when
    testing from a shell with `printf '...\\n...'`, the shell expands \\n to
    a literal 0x0a *inside* the JSON string, splitting one object across
    multiple lines.

    Strategy: read byte-by-byte, track brace depth (ignoring braces inside
    string literals), and return as soon as depth reaches zero.  This is
    O(n) and handles both cases correctly.

    Returns None on EOF.
    """
    buf = bytearray()
    depth = 0          # net { minus }
    in_string = False
    escape_next = False
    started = False    # have we seen the opening '{'?

    while True:
        byte = stdin.read(1)
        if not byte:
            return None  # EOF

        ch = byte[0]
        buf.append(ch)

        if escape_next:
            escape_next = False
            continue

        if in_string:
            if ch == ord("\\"):
                escape_next = True
            elif ch == ord('"'):
                in_string = False
            continue

        # Outside a string
        if ch == ord('"'):
            in_string = True
        elif ch == ord("{"):
            depth += 1
            started = True
        elif ch == ord("}"):
            depth -= 1
            if started and depth == 0:
                # Complete object
                try:
                    raw_str = buf.decode("utf-8", errors="replace")
                    # json.loads rejects literal control characters (0x00–0x1f)
                    # inside strings — e.g. 0x0a produced by shell printf \n.
                    # Re-encode them as proper JSON escape sequences.
                    sanitized = re.sub(
                        r'[\x00-\x1f]',
                        lambda m: f"\\u{ord(m.group()):04x}",
                        raw_str,
                    )
                    return json.loads(sanitized)
                except json.JSONDecodeError:
                    # Malformed — reset and keep reading for the next object
                    buf.clear()
                    depth = 0
                    started = False
                    in_string = False
                    escape_next = False
        # Whitespace / other chars outside braces before the first '{' — skip
        elif not started:
            buf.clear()


def main() -> None:
    """Read JSON-RPC messages from stdin, write responses to stdout."""
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer

    while True:
        try:
            req = _read_one_object(stdin)
            if req is None:
                break  # EOF

            response = handle_request(req)
            if response is not None:
                stdout.write((json.dumps(response) + "\n").encode("utf-8"))
                stdout.flush()

        except KeyboardInterrupt:
            break
        except Exception as exc:
            try:
                resp = _jsonrpc_error(None, -32603, f"Internal error: {exc}")
                stdout.write((json.dumps(resp) + "\n").encode("utf-8"))
                stdout.flush()
            except Exception:
                pass


if __name__ == "__main__":
    main()
