# AGENTS.md — AI Execution Rules

## MANDATORY STARTUP SEQUENCE

Before touching any file, call these MCP tools in order:

```
1. get_workflow_rules()        → load enforced rules
2. get_paths()                 → load project paths
3. read_doc("WORKFLOW.md")     → load the change policy
4. read_rule("guidelines.md")  → load coding standards
5. read_rule("structure.md")   → load project layout
```

If any of these fail → stop and report the error. Do not proceed.

---

## THE 7-STEP POLICY (non-negotiable)

```
1. ANALYZE   → read files first, understand fully
2. IDENTIFY  → name exact files to change, state the plan
3. APPLY     → minimal patch only
4. VALIDATE  → call run_checks() MCP tool
5. SUMMARIZE → call write_update_summary() MCP tool
6. WAIT      → present to user, wait for explicit approval
7. COMMIT    → call generate_commit_message() MCP tool, then commit
```

**NEVER skip step 6. NEVER commit without step 7.**

---

## MCP Tool Reference

### Workflow tools (steps 4–7)
```python
run_checks()
# → runs pytest + ruff lint + ruff format + structure checks
# → returns: {"passed": bool, "output": str}

write_update_summary(feature, change_type)
# → runs post_change_report.py
# → writes to data/docs/updates/ or CHANGELOG.md
# → returns: path to written file

update_changelog(change_type, description, files, why, verified, breaking)
# → adds entry to data/docs/CHANGELOG.md
# → returns: confirmation

generate_commit_message()
# → runs make_commit_message.py on staged files
# → returns: suggested commit message string
```

### Memory tools (startup)
```python
get_workflow_rules()     → list of enforced rules
get_paths()              → project path map
get_assumptions()        → saved project assumptions
save_fact(cat, key, val) → persist a new fact
```

### Knowledge tools
```python
read_doc("WORKFLOW.md")       → change policy
read_doc("ARCHITECTURE.md")   → system layers + flows
read_doc("STRUCTURE.md")      → folder map + protected files
read_rule("guidelines.md")    → coding standards
read_rule("tech.md")          → tech stack
list_docs()                   → all available docs
list_rules()                  → all available rules
```

---

## Code Rules (enforced by CI)

### No UI imports in services
```python
# FORBIDDEN in app/core/**
from app.ui import ...
import app.ui
```

### No hardcoded paths
```python
# FORBIDDEN
path = "T:/ae/pyside6/user_data"
sys.path.insert(0, "T:/ae/pyside6")

# CORRECT
ROOT = Path(__file__).parent.parent
path = ROOT / "user_data"
```

### Process execution
```python
# CORRECT — spaces-safe
process_service.execute_command([cmd.program] + cmd.args, ...)

# FORBIDDEN — breaks paths with spaces
command_list = f"{cmd.program} {' '.join(cmd.args)}".split()
```

### No duplicate logic
- `CommandRunner` builds commands → don't build commands in UI
- `ProcessService` runs processes → don't use `subprocess` in UI
- `RunStore` saves runs → don't write JSON directly from UI

### Minimal changes only
- Don't rewrite working code
- Don't reorganize imports unless that's the task
- Don't change `@staticmethod` to instance method without reason
- Don't change Pydantic fields without a migration plan

---

## Logging Pattern

```python
from app.core.utils.app_logger import get_logger
_log = get_logger("module_name")

_log.debug("...")    # data details
_log.info("...")     # lifecycle events
_log.cmd("...")      # command execution → green in console
_log.warning("...")  # recoverable issues
_log.error("...")    # failures
```

| Logger prefix | File |
|---------------|------|
| `ui.*` | `data/log/ui.log` |
| `services.*`, `backtest`, `settings`, `download` | `data/log/services.log` |
| `process` | `data/log/process.log` |
| everything | `data/log/app.log` |

---

## Freqtrade-Specific Rules

- freqtrade writes zip to `backtest_results/*.zip` — ignores `--export-filename`
- `_try_load_results` uses timestamp filter — do not change this logic
- Strategy JSON must have `strategy_name` + `params` wrapper — enforced by CI
- Never pass `--export-filename` to freqtrade backtesting command

---

## NEVER DO

- Commit without user approval
- Skip `run_checks()` after a code change
- Skip `write_update_summary()` before presenting to user
- Import `app.ui` from `app.core`
- Use `string.split()` to build a command list
- Use hardcoded absolute paths
- Use `sys.path.insert` in app code
- Delete or rewrite existing test cases
- Add unrequested features in the same patch
