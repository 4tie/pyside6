"""
cache_log_analyzer.py — Standalone maintenance script.

Performs three sequential phases:
  1. Cache Cleanup  — removes __pycache__ dirs and .pyc files (skips .venv/.git)
  2. Log Scanning   — collects ERROR/CRITICAL/WARNING lines and anomaly keywords
  3. AI Analysis    — sends events to a local Ollama model and writes a Markdown report
"""

import datetime
import os
import shutil

import requests

try:
    from dotenv import load_dotenv as _load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

# Module-level constants — populated by load_env()
OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_MODEL: str = "llama3"

ANOMALY_KEYWORDS: list[str] = [
    "Traceback", "Exception", "exit code",
    "failed", "timeout", "connection refused",
]


def load_env() -> None:
    """Load .env file (if present) and resolve Ollama configuration into module constants."""
    global OLLAMA_BASE_URL, OLLAMA_MODEL

    if _HAS_DOTENV:
        _load_dotenv()

    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


def clean_cache(root: str) -> list[str]:
    """
    Recursively removes __pycache__ dirs and .pyc files under root,
    skipping .venv/ and .git/ subtrees.
    Returns list of deleted paths.
    """
    deleted: list[str] = []

    for dirpath, dirs, files in os.walk(root, topdown=True):
        # Prune .venv and .git subtrees in-place
        dirs[:] = [d for d in dirs if d not in (".venv", ".git")]

        # Delete __pycache__ directories
        for d in list(dirs):
            if d == "__pycache__":
                full_path = os.path.join(dirpath, d)
                try:
                    shutil.rmtree(full_path)
                    print(f"  Removed: {full_path}")
                    deleted.append(full_path)
                    dirs.remove(d)
                except PermissionError as e:
                    print(f"  Warning: could not remove {full_path}: {e}")

        # Delete .pyc files
        for f in files:
            if f.endswith(".pyc"):
                full_path = os.path.join(dirpath, f)
                try:
                    os.remove(full_path)
                    print(f"  Removed: {full_path}")
                    deleted.append(full_path)
                except PermissionError as e:
                    print(f"  Warning: could not remove {full_path}: {e}")

    return deleted


def scan_logs(log_dir: str, keywords: list[str]) -> list[str]:
    """
    Opens every file in log_dir, collects lines matching level markers
    (ERROR, CRITICAL, WARNING) or any keyword (case-insensitive).
    Returns collected event lines.
    """
    LEVEL_MARKERS = ("ERROR", "CRITICAL", "WARNING")
    events: list[str] = []
    file_count = 0

    try:
        entries = list(os.scandir(log_dir))
    except OSError as e:
        print(f"  Warning: could not read log directory {log_dir}: {e}")
        return events

    for entry in entries:
        if not entry.is_file():
            continue
        file_count += 1
        try:
            with open(entry.path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line_stripped = line.rstrip("\n")
                    if any(marker in line_stripped for marker in LEVEL_MARKERS):
                        events.append(line_stripped)
                    elif any(kw.lower() in line_stripped.lower() for kw in keywords):
                        events.append(line_stripped)
        except OSError as e:
            print(f"  Warning: could not read {entry.path}: {e}")

    print(f"Found {len(events)} event(s) across {file_count} file(s).")
    return events


def analyze_with_ollama(events: list[str], base_url: str, model: str) -> str | None:
    """
    Sends collected event lines to a local Ollama /api/chat endpoint.
    Returns the assistant message content on success, None on any error.
    """
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior developer analysing application log events. "
                    "Produce a structured Markdown report explaining each issue in "
                    "plain language and providing numbered fix instructions for each problem."
                ),
            },
            {
                "role": "user",
                "content": "\n".join(events),
            },
        ],
    }

    url = f"{base_url.rstrip('/')}/api/chat"
    try:
        response = requests.post(url, json=payload)
    except requests.exceptions.ConnectionError as e:
        print(f"  Error: could not connect to Ollama at {base_url}: {e}")
        return None
    except requests.exceptions.Timeout as e:
        print(f"  Error: request to Ollama timed out: {e}")
        return None

    if response.status_code != 200:
        print(f"  Error: Ollama returned HTTP {response.status_code}: {response.text}")
        return None

    return response.json()["message"]["content"]


def write_report(content: str, report_path: str) -> bool:
    """
    Writes the AI analysis content to report_path with a header.
    Creates parent directories if needed. Returns True on success, False on OSError.
    """
    header = f"# App Event Analysis Report\nGenerated: {datetime.date.today()}\n\n"
    full_content = header + content

    try:
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(full_content)
    except OSError as e:
        print(f"  Error: could not write report to {report_path}: {e}")
        return False

    return True


def main() -> None:
    """Orchestrate the three phases in order."""
    load_env()

    print("=== Phase 1: Cache Cleanup ===")
    deleted = clean_cache(os.getcwd())
    if deleted:
        print(f"Cache cleanup complete: {len(deleted)} items removed.")
    else:
        print("No cache files found.")

    print("=== Phase 2: Log Scanning ===")
    log_dir = os.path.join(os.getcwd(), "data", "log")
    if not os.path.isdir(log_dir):
        print(f"Warning: Log directory not found: {log_dir}")
        events: list[str] = []
    else:
        events = scan_logs(log_dir, ANOMALY_KEYWORDS)

    if not events:
        print("No events found. Skipping AI analysis.")
        return

    print("=== Phase 3: AI Analysis ===")
    result = analyze_with_ollama(events, OLLAMA_BASE_URL, OLLAMA_MODEL)
    if result is not None:
        report_path = os.path.join(os.getcwd(), "data", "app_event_analysis.md")
        if write_report(result, report_path):
            print(os.path.abspath(report_path))
            print(result)


if __name__ == "__main__":
    main()
