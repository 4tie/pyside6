#!/usr/bin/env python3
"""
post_change_report.py — Generate a change report from git diff and test results.

Usage:
    python tools/post_change_report.py --feature "backtest widget cleanup"
    python tools/post_change_report.py --feature "fix zip path" --append-changelog
    python tools/post_change_report.py --feature "fix zip path" --type fix
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / "data" / "docs"
UPDATES_DIR = DOCS_DIR / "updates"
CHANGELOG = DOCS_DIR / "CHANGELOG.md"


def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=str(ROOT)
    )
    return result.stdout.strip()


def _run_tests() -> tuple[bool, str]:
    result = subprocess.run(
        ["pytest", "tests/", "--tb=short", "-q"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    ok = result.returncode == 0
    output = (result.stdout + result.stderr).strip()
    return ok, output


def _changed_files() -> list[str]:
    # staged + unstaged tracked changes
    staged = _git(["diff", "--cached", "--name-only"])
    unstaged = _git(["diff", "--name-only"])
    files = set()
    for line in (staged + "\n" + unstaged).splitlines():
        line = line.strip()
        if line:
            files.add(line)
    return sorted(files)


def _diff_summary(files: list[str]) -> str:
    if not files:
        return "_No changes detected._"
    result = subprocess.run(
        ["git", "diff", "HEAD", "--stat"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    stat = result.stdout.strip()
    if not stat:
        result = subprocess.run(
            ["git", "diff", "--stat"] + files,
            capture_output=True, text=True, cwd=str(ROOT),
        )
        stat = result.stdout.strip()
    return stat or "\n".join(f"- `{f}`" for f in files)


def _build_report(feature: str, change_type: str, tests_ok: bool, test_output: str,
                  files: list[str], diff_stat: str) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")
    test_status = "✓ passed" if tests_ok else "✗ failed"

    files_md = "\n".join(f"- `{f}`" for f in files) if files else "_none detected_"

    test_block = ""
    if not tests_ok:
        last_lines = "\n".join(test_output.splitlines()[-15:])
        test_block = f"\n**Test output (last 15 lines):**\n```\n{last_lines}\n```\n"

    return f"""## [{date} {time_str}] — {feature}

**نوع:** {change_type}

**الملفات المعدّلة:**
{files_md}

**Diff summary:**
```
{diff_stat}
```

**Tests:** {test_status}{test_block}

**Breaking change:** لا
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a change report.")
    parser.add_argument("--feature", required=True, help="Short feature/fix name")
    parser.add_argument(
        "--type", dest="change_type", default="feat",
        choices=["fix", "feat", "refactor", "docs", "chore"],
        help="Change type"
    )
    parser.add_argument(
        "--append-changelog", action="store_true",
        help="Append report to CHANGELOG.md instead of creating a separate file"
    )
    parser.add_argument(
        "--skip-tests", action="store_true",
        help="Skip running tests"
    )
    args = parser.parse_args()

    print(f"\nGenerating report for: {args.feature}")

    # Gather data
    files = _changed_files()
    diff_stat = _diff_summary(files)

    if args.skip_tests:
        tests_ok, test_output = True, "skipped"
        print("  Tests: skipped")
    else:
        print("  Running tests...")
        tests_ok, test_output = _run_tests()
        print(f"  Tests: {'passed' if tests_ok else 'FAILED'}")

    report = _build_report(
        feature=args.feature,
        change_type=args.change_type,
        tests_ok=tests_ok,
        test_output=test_output,
        files=files,
        diff_stat=diff_stat,
    )

    if args.append_changelog:
        # Prepend to CHANGELOG.md (newest first)
        existing = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else "# CHANGELOG.md\n"
        header, _, rest = existing.partition("\n## ")
        new_content = header + "\n" + report + ("\n## " + rest if rest else "")
        CHANGELOG.write_text(new_content, encoding="utf-8")
        print(f"\n  Appended to {CHANGELOG.relative_to(ROOT)}")
    else:
        # Write to updates/
        UPDATES_DIR.mkdir(parents=True, exist_ok=True)
        slug = args.feature.lower().replace(" ", "-").replace("/", "-")
        date = datetime.now().strftime("%Y-%m-%d")
        out_file = UPDATES_DIR / f"{date}-{slug}.md"
        out_file.write_text(f"# {args.feature}\n\n" + report, encoding="utf-8")
        print(f"\n  Report written to {out_file.relative_to(ROOT)}")

    if not tests_ok and not args.skip_tests:
        print("\n  ⚠ Tests failed — fix before committing.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
