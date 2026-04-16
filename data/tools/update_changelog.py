#!/usr/bin/env python3
"""
update_changelog.py — Add a new entry to CHANGELOG.md interactively or via args.

Usage:
    python tools/update_changelog.py
    python tools/update_changelog.py --type fix --desc "Fixed zip path in backtest"
    python tools/update_changelog.py --type feat --desc "Added run picker" --files "backtest_page.py,run_store.py"
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHANGELOG = ROOT / "data" / "docs" / "CHANGELOG.md"


def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=str(ROOT)
    )
    return result.stdout.strip()


def _changed_files_since_last_commit() -> list[str]:
    out = _git(["diff", "HEAD", "--name-only"])
    staged = _git(["diff", "--cached", "--name-only"])
    files = set()
    for line in (out + "\n" + staged).splitlines():
        line = line.strip()
        if line:
            files.add(line)
    return sorted(files)


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {label}{suffix}: ").strip()
    return val or default


def _build_entry(change_type: str, desc: str, files: list[str],
                 why: str, verified: str, breaking: bool, breaking_desc: str) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")

    files_md = "\n".join(f"- `{f}`" for f in files) if files else "- (not specified)"
    breaking_line = f"\n**Breaking change:** نعم — {breaking_desc}" if breaking else "**Breaking change:** لا"

    return f"""## [{date} {time_str}] — {desc}

**نوع:** {change_type}

**ماذا تغيّر:**
{desc}

**لماذا:**
{why}

**الملفات المعدّلة:**
{files_md}

**كيف تم التحقق:**
{verified}

{breaking_line}

"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Add entry to CHANGELOG.md")
    parser.add_argument("--type", dest="change_type", default=None,
                        choices=["fix", "feat", "refactor", "docs", "chore", "test"])
    parser.add_argument("--desc", default=None, help="Short description")
    parser.add_argument("--files", default=None, help="Comma-separated file list")
    parser.add_argument("--why", default=None, help="Reason for change")
    parser.add_argument("--verified", default=None, help="How it was verified")
    parser.add_argument("--breaking", action="store_true")
    parser.add_argument("--breaking-desc", default="")
    args = parser.parse_args()

    interactive = not all([args.change_type, args.desc])

    if interactive:
        print("\n=== Update CHANGELOG.md ===\n")
        change_type = _prompt("Type (fix/feat/refactor/docs/chore)", args.change_type or "feat")
        desc = _prompt("Description", args.desc or "")
        auto_files = _changed_files_since_last_commit()
        if auto_files:
            print(f"  Auto-detected files: {', '.join(auto_files)}")
            use_auto = _prompt("Use these files? (y/n)", "y")
            files = auto_files if use_auto.lower() == "y" else []
        else:
            files = []
        if not files:
            raw = _prompt("Files (comma-separated, or leave blank)", args.files or "")
            files = [f.strip() for f in raw.split(",") if f.strip()]
        why = _prompt("Why", args.why or "")
        verified = _prompt("Verified by", args.verified or "manual test")
        breaking_input = _prompt("Breaking change? (y/n)", "n")
        breaking = breaking_input.lower() == "y"
        breaking_desc = _prompt("Breaking change description", args.breaking_desc) if breaking else ""
    else:
        change_type = args.change_type
        desc = args.desc
        files = [f.strip() for f in (args.files or "").split(",") if f.strip()]
        if not files:
            files = _changed_files_since_last_commit()
        why = args.why or ""
        verified = args.verified or "manual test"
        breaking = args.breaking
        breaking_desc = args.breaking_desc

    entry = _build_entry(change_type, desc, files, why, verified, breaking, breaking_desc)

    # Prepend to CHANGELOG (newest first)
    if CHANGELOG.exists():
        existing = CHANGELOG.read_text(encoding="utf-8")
        # Insert after the first line (# CHANGELOG.md header)
        lines = existing.split("\n", 1)
        new_content = lines[0] + "\n\n" + entry + (lines[1] if len(lines) > 1 else "")
    else:
        new_content = "# CHANGELOG.md\n\n" + entry

    CHANGELOG.write_text(new_content, encoding="utf-8")
    print(f"\n  ✓ Entry added to {CHANGELOG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
