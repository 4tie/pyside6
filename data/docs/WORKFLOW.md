# WORKFLOW.md — Change Policy

## THE POLICY

```
ANY code change MUST follow this exact order:

  1. ANALYZE    — understand the request fully, read relevant files
  2. IDENTIFY   — name the minimal set of files to change
  3. APPLY      — make the smallest correct patch
  4. VALIDATE   — run checks, confirm nothing broke
  5. SUMMARIZE  — write an update summary (via script)
  6. WAIT       — present summary, wait for explicit user approval
  7. COMMIT     — only after approval (via script)

NO EXCEPTIONS. NO SHORTCUTS.
```

This policy is enforced by:
- Scripts in `data/tools/` that must be called at steps 4, 5, 7
- MCP tools that wrap those scripts
- CI that rejects any push that skips validation

---

## Step-by-Step

### Step 1 — ANALYZE
- Read every file that will be touched before writing any code
- For bugs: identify root cause, not just symptoms
- For features: confirm scope — what is in/out of bounds (see `PRODUCT.md`)
- If the request is ambiguous → ask, don't guess

### Step 2 — IDENTIFY
- List exact files to change before touching anything
- If more than 3 files → pause and find a simpler approach
- Never create a new file if the change fits an existing one
- State the plan explicitly: "I will change X in file Y because Z"

### Step 3 — APPLY
- Smallest correct patch only
- No style/formatting changes mixed with logic changes
- No unrequested features added
- No rewriting of working code

### Step 4 — VALIDATE
```bash
python data/tools/run_checks.py
```
- Must pass before proceeding
- If tests fail → fix first, do not skip

### Step 5 — SUMMARIZE
```bash
python data/tools/post_change_report.py --feature "<name>" --type <fix|feat|refactor>
```
- Generates: changed files, diff stat, test result, timestamp
- Output goes to `data/docs/updates/` or appended to `CHANGELOG.md`
- Do NOT write the summary manually — use the script

### Step 6 — WAIT
- Present the summary to the user
- State clearly: what changed, why, any side effects
- **Do not proceed to commit without explicit "yes" or "approved"**
- If user requests changes → go back to Step 3

### Step 7 — COMMIT
```bash
python data/tools/make_commit_message.py
# → copy the suggested message
git add <files>
git commit -m "<suggested message>"
```
- Never commit without running `make_commit_message.py` first
- Never bundle unrelated changes in one commit

---

## Tool Bindings

| Step | Tool | Command |
|------|------|---------|
| 4 — Validate | `run_checks` (MCP) | `python data/tools/run_checks.py` |
| 5 — Summarize | `write_update_summary` (MCP) | `python data/tools/post_change_report.py` |
| 5 — Changelog | `update_changelog` (MCP) | `python data/tools/update_changelog.py` |
| 7 — Commit msg | `generate_commit_message` (MCP) | `python data/tools/make_commit_message.py` |

---

## Quick Rules

| Change type | Rule |
|-------------|------|
| Bug fix | Smallest patch, don't rewrite the function |
| New feature | Service layer first, then UI |
| Refactor | No behavior change, structure only |
| Docs only | No tests needed, but still needs approval |
| Breaking change | Must be flagged in summary and CHANGELOG |
