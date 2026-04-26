# Design Document — web-mobile-tailscale

## Overview

This feature extends the Freqtrade strategy workstation in two complementary directions:

1. **Tailscale / remote-access** — `run_web.py` gains a `--tailscale` flag that auto-detects the host's Tailscale IP (`100.x.x.x`) and prints it in the startup banner. `WEB_HOST` and `WEB_PORT` environment variables become supported defaults so the server can be configured via `.env` without repeating CLI flags.

2. **iPhone / mobile UI** — the React SPA (`app/re_web/`) becomes fully usable on a 390 px-wide iPhone screen. Changes are confined to the existing pure-CSS custom-property system and the `AppShell.tsx` component; no new runtime dependencies are introduced.

Both halves are independent: the backend changes are pure Python with no new packages; the frontend changes are CSS + one component edit with no new npm packages.

---

## Architecture

### Backend — `run_web.py`

The existing module is a self-contained launcher. The changes stay within the same file and follow the existing patterns:

```
run_web.py
  ├── _detect_tailscale_ip() → str | None   [NEW]
  ├── _parse_args()                          [MODIFIED]
  ├── _banner()                              [MODIFIED]
  └── main()                                 [MODIFIED — calls detect, passes result to banner]
```

No new modules, no new packages. `subprocess` and `socket` are already in the standard library.

### Frontend — `app/re_web/`

```
app/re_web/
  ├── index.html                             [MODIFIED — viewport meta]
  ├── package.json                           [MODIFIED — dev/preview host binding]
  ├── vite.config.ts                         [NO CHANGE — proxy already correct]
  └── src/
      ├── components/
      │   ├── AppShell.tsx                   [MODIFIED — add mobile-nav markup]
      │   └── MobileNav.tsx                  [NEW only if AppShell.tsx > 150 lines]
      └── styles/
          └── app.css                        [MODIFIED — mobile CSS additions]
```

---

## Components and Interfaces

### `_detect_tailscale_ip() -> str | None`

A pure function with no side effects beyond subprocess execution and socket queries. Returns the first `100.x.x.x` address found, or `None`.

**Detection strategy (two-step, no new dependencies):**

1. **Tailscale CLI** — `subprocess.run(["tailscale", "ip", "--4"], capture_output=True, text=True, timeout=2)`. If the process exits 0 and stdout contains a `100.x.x.x` address, return it.
2. **Socket fallback** — `socket.getaddrinfo(socket.gethostname(), None)`. Iterate the returned addresses and return the first one matching the Tailscale CGNAT range `100.64.0.0/10` (i.e. `100.64.0.0` – `100.127.255.255`).
3. If neither step yields an address, return `None`.

The CGNAT range check is done with integer arithmetic to avoid importing `ipaddress` (though `ipaddress` is stdlib and acceptable if preferred):

```python
def _in_tailscale_range(addr: str) -> bool:
    parts = addr.split(".")
    if len(parts) != 4 or parts[0] != "100":
        return False
    second = int(parts[1])
    return 64 <= second <= 127
```

### `_parse_args()` — changes

| Addition | Detail |
|---|---|
| `--tailscale` | `action="store_true"`, default `False` |
| `--host` default | `os.environ.get("WEB_HOST", "0.0.0.0")` |
| `--port` default | Read `WEB_PORT` from env; validate 1–65535; `sys.exit(1)` with message on invalid |

Port validation happens inside `_parse_args()` before returning, so `main()` never sees an invalid port:

```python
_env_port = os.environ.get("WEB_PORT")
_default_port = 8000
if _env_port is not None:
    try:
        _default_port = int(_env_port)
        if not (1 <= _default_port <= 65535):
            raise ValueError
    except ValueError:
        print(f"ERROR: WEB_PORT={_env_port!r} is not a valid port (1–65535)", file=sys.stderr)
        sys.exit(1)
```

### `_banner()` — changes

Signature becomes:

```python
def _banner(host: str, port: int, log_file: Path, reload: bool,
            tailscale_ip: str | None = None) -> None:
```

New lines added to the output:
- **Tailscale line** — printed only when `tailscale_ip is not None`: `Tailscale     http://<tailscale_ip>:<port>/app`
- **Network line** — printed when `host` is not `"0.0.0.0"` and not `"::"`: `Network       http://<host>:<port>/app`

The existing Local and API docs lines are unchanged.

### `AppShell.tsx` — mobile nav

A `<nav className="mobile-nav" aria-label="Mobile navigation">` element is added after `<main className="content">`. It renders the same `routes` array as icon + label buttons:

```tsx
<nav className="mobile-nav" aria-label="Mobile navigation">
  {routes.map((route) => {
    const active = currentPath === route.path ||
      (route.path !== '/app' && currentPath.startsWith(route.path));
    return (
      <button
        key={route.path}
        type="button"
        className={active ? 'mobile-nav-item active' : 'mobile-nav-item'}
        onClick={() => onNavigate(route.path)}
        aria-label={route.label}
        aria-current={active ? 'page' : undefined}
      >
        {route.icon}
        <span>{route.label}</span>
      </button>
    );
  })}
</nav>
```

If `AppShell.tsx` exceeds 150 lines after this addition, the nav markup and its types are extracted to `MobileNav.tsx` and imported. The `routes` array and `RouteItem` type are already exported, so the extraction is straightforward.

### `app.css` — mobile additions

All additions go into the existing `@media (max-width: 680px)` block or as new base rules for `.mobile-nav`:

**Base rules (outside media query — hidden by default on desktop):**
```css
.mobile-nav {
  display: none;
  position: fixed;
  bottom: 0; left: 0; right: 0;
  background: var(--surface);
  border-top: 1px solid var(--border);
  z-index: 100;
  padding-bottom: env(safe-area-inset-bottom);
}

.mobile-nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  min-height: 56px;
  padding: 6px 4px;
  color: var(--muted);
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 10px;
}

.mobile-nav-item.active {
  color: var(--accent);
}
```

**Inside `@media (max-width: 680px)` additions:**
```css
/* Navigation swap */
.sidebar { display: none; }
.mobile-nav { display: flex; }

/* Content padding to avoid overlap with fixed nav */
.content { padding-bottom: calc(64px + env(safe-area-inset-bottom)); }

/* Safe-area insets */
body { padding-top: env(safe-area-inset-top); }

/* Touch targets */
.button, .icon-button, .nav-link, .tab {
  min-height: 44px;
  min-width: 44px;
}

/* Typography */
body { font-size: 15px; }
input, select, textarea { font-size: 16px; }
.metric-value { font-size: 20px; }

/* Layout */
.metric-grid { grid-template-columns: repeat(2, 1fr); }
.split-layout, .optimizer-layout { grid-template-columns: 1fr; }
.form-grid { grid-template-columns: 1fr; }
.page-header { flex-direction: column; align-items: stretch; }
.page-header .button { width: 100%; justify-content: center; }

/* Overflow */
body { overflow-x: hidden; }
.table-wrap { overflow-x: auto; max-width: 100%; }

/* Tab scrollbar hiding */
.tab-list { scrollbar-width: none; }
.tab-list::-webkit-scrollbar { display: none; }
```

Note: the existing `@media (max-width: 680px)` block already has `.metric-grid { grid-template-columns: 1fr; }` and `.metric-value { font-size: 20px; }` — the new rules override or replace these. The `.page-header` flex-direction rule already exists; the `.button` width rule is new.

### `index.html` — viewport meta

Change:
```html
<!-- before -->
<meta name="viewport" content="width=device-width, initial-scale=1.0" />

<!-- after -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

### `package.json` — host binding

```json
"dev": "vite --host 0.0.0.0",
"preview": "vite preview --host 0.0.0.0"
```

### `.env.example` — documentation

Add two lines:
```
WEB_HOST=0.0.0.0   # Bind address for run_web.py (default: 0.0.0.0)
WEB_PORT=8000      # TCP port for run_web.py (default: 8000)
```

### `AppShell.tsx` — mobile nav overflow (Requirement 10)

The `routes` array has 7 items. On a 390 px bar that gives ~55 px per item — workable but tight. The overflow strategy caps visible items at 4 and adds a "More" button as the fifth slot.

State additions to `AppShell`:
```tsx
const [moreOpen, setMoreOpen] = useState(false);
const PRIMARY_COUNT = 4;
const primaryRoutes = routes.slice(0, PRIMARY_COUNT);
const moreRoutes    = routes.slice(PRIMARY_COUNT);
const moreIsActive  = moreRoutes.some(
  (r) => currentPath === r.path || (r.path !== '/app' && currentPath.startsWith(r.path))
);
```

The "More" button renders as a fifth `.mobile-nav-item` with a `MoreHorizontal` icon from lucide-react. When `moreOpen` is true, a `.mobile-more-sheet` div is rendered above the nav bar containing the overflow routes. Tapping outside the sheet closes it via a transparent `.mobile-more-backdrop` overlay.

```tsx
{moreOpen && (
  <>
    <div className="mobile-more-backdrop" onClick={() => setMoreOpen(false)} />
    <div className="mobile-more-sheet">
      {moreRoutes.map((route) => { /* same button structure as primary items */ })}
    </div>
  </>
)}
```

CSS additions (outside media query — hidden on desktop):
```css
.mobile-more-backdrop {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 99;
}
.mobile-more-sheet {
  display: none;
  position: fixed;
  bottom: calc(56px + env(safe-area-inset-bottom));
  right: 0;
  min-width: 180px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius) var(--radius) 0 0;
  z-index: 101;
  padding: 8px 0;
}
.mobile-more-sheet .mobile-nav-item {
  flex-direction: row;
  justify-content: flex-start;
  gap: 12px;
  padding: 0 16px;
  font-size: 14px;
  min-height: 48px;
}
```

Inside `@media (max-width: 680px)`:
```css
.mobile-more-backdrop { display: block; }
.mobile-more-sheet    { display: flex; flex-direction: column; }
```

### `RunTable.tsx` — mobile card layout (Requirement 11)

A `useMediaQuery` hook (or a CSS-only approach using `display: contents` / `display: none`) switches the render. The simplest approach that avoids a new hook is to render both the table and the card list, toggling visibility via CSS:

```tsx
<div className="table-wrap run-table-desktop">
  <table>…existing table…</table>
</div>
<div className="run-card-list">
  {runs.map((run) => (
    <div key={run.run_id} className="run-card">
      <div className="run-card-main">
        <strong>{run.strategy}</strong>
        <span className="muted">{run.run_id}</span>
      </div>
      <div className="run-card-stats">
        <span className={run.profit_total_pct >= 0 ? 'positive' : 'negative'}>
          {formatPct(run.profit_total_pct)}
        </span>
        <span className="muted">WR {formatPct(run.win_rate_pct)}</span>
        <span className="muted">DD {formatPct(run.max_drawdown_pct)}</span>
        <span className="muted">{run.trades_count} trades</span>
      </div>
      <button className="button ghost run-card-open" type="button" onClick={() => onOpen(run)}>
        Open
      </button>
    </div>
  ))}
</div>
```

CSS (base — card list hidden on desktop):
```css
.run-card-list { display: none; }
```

Inside `@media (max-width: 680px)`:
```css
.run-table-desktop { display: none; }
.run-card-list {
  display: grid;
  gap: 8px;
}
.run-card {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  gap: 6px 12px;
  padding: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.run-card-main { grid-column: 1; display: grid; gap: 2px; }
.run-card-open { grid-column: 2; grid-row: 1 / 3; align-self: center; min-height: 44px; }
.run-card-stats {
  grid-column: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 13px;
}
```

### `RunDetailPage.tsx` — equity chart touch (Requirement 12)

Add touch handlers to the SVG element alongside the existing mouse handlers:

```tsx
function getTouchX(e: React.TouchEvent<SVGSVGElement>): number {
  const rect = svgRef.current?.getBoundingClientRect();
  if (!rect) return 0;
  return ((e.touches[0].clientX - rect.left) / rect.width) * W;
}

// On the SVG element:
onTouchMove={(e) => {
  e.preventDefault();
  const svgX = getTouchX(e);
  const relX = svgX - PAD.left;
  const idx = Math.round((relX / innerW) * (points.length - 1));
  const clamped = Math.max(0, Math.min(points.length - 1, idx));
  const pt = points[clamped];
  setHover({ x: toX(clamped), y: toY(pt.balance), balance: pt.balance, idx: clamped });
}}
onTouchEnd={() => setHover(null)}
style={{ touchAction: 'none' }}
```

### `app.css` — iOS scroll momentum and hover suppression (Requirement 13)

Base additions (outside media query):
```css
/* iOS momentum scrolling for all scrollable containers */
.terminal,
.json-block,
.param-list,
.table-wrap,
.tab-list,
.nav-list {
  -webkit-overflow-scrolling: touch;
}
```

New `@media (hover: none)` block:
```css
@media (hover: none) {
  .button:hover,
  .icon-button:hover { background: var(--surface-2); }
  .button.primary:hover { background: var(--accent); }
  .button.ghost:hover { background: transparent; }
  .nav-link:hover { color: var(--muted); background: transparent; }
  .tab:hover { color: var(--muted); background: transparent; }
  .chip:hover { background: var(--surface-2); color: var(--muted); }
  .chip.active:hover { background: var(--accent); color: #06110f; }
  .table-row-hover:hover td { background: transparent; }
}
```

### `app.css` — dense-data and layout fixes (Requirement 14)

Inside `@media (max-width: 680px)`:
```css
/* Param rows and trial tiles: 2-column on mobile */
.param-row,
.trial-tile {
  grid-template-columns: 1fr 1fr;
}
.param-row > span:nth-child(3),
.param-row > span:nth-child(4),
.trial-tile > span:nth-child(3),
.trial-tile > span:nth-child(4) {
  display: none;
}

/* Run selector full-width */
.run-selector-wrap { min-width: 0; width: 100%; max-width: 100%; }

/* Comparison controls full-width selects */
.comparison-controls label { flex: 1 1 100%; }
.comparison-controls select { width: 100%; }

/* Chip tap targets */
.chip { min-height: 36px; padding: 0 10px; }
```

---

## Data Models

No new persistent data models are introduced. The only new data flowing through the system:

| Value | Type | Source | Consumer |
|---|---|---|---|
| `tailscale_ip` | `str \| None` | `_detect_tailscale_ip()` | `_banner()`, `main()` |
| `WEB_HOST` | `str` | `os.environ` / `.env` | `_parse_args()` default |
| `WEB_PORT` | `int` (1–65535) | `os.environ` / `.env` | `_parse_args()` default |

The Tailscale IP is never persisted; it is detected at startup and used only for banner output.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

PBT applies here because several functions (`_detect_tailscale_ip`, `_banner`, `_parse_args`) are pure or near-pure with clear input/output behavior and large input spaces. The CSS and static-file checks are not suitable for PBT and are covered by smoke tests instead.

**Property reflection:** Requirements 1.2 and 3.2 both describe the same banner behavior (Tailscale IP appears in output) — they are consolidated into Property 1. Requirements 3.1 and 3.4 both describe invariants of the banner output — they are consolidated into Property 3. Requirements 2.1 and 2.2 describe the same env-var-to-default mapping pattern — they are kept separate because the types and validation rules differ. Requirement 5.5 (mobile nav tap calls onNavigate) is a property over the routes array.

---

### Property 1: Banner includes Tailscale URL when IP is provided

*For any* string matching the Tailscale CGNAT format `100.x.x.x` passed as `tailscale_ip` to `_banner()`, the printed output SHALL contain that IP address and the label `Tailscale`.

**Validates: Requirements 1.2, 3.2**

---

### Property 2: Banner omits Tailscale section when no IP is provided

*For any* call to `_banner()` with `tailscale_ip=None`, the printed output SHALL NOT contain the string `Tailscale`.

**Validates: Requirements 1.4, 3.2**

---

### Property 3: Banner always contains loopback URL and docs URL

*For any* valid port number (1–65535) and any host string, `_banner()` SHALL always include `http://127.0.0.1:<port>` and `http://127.0.0.1:<port>/docs` in its output.

**Validates: Requirements 3.1, 3.4**

---

### Property 4: Banner includes Network URL for non-loopback host

*For any* host string that is not `"0.0.0.0"`, `"::"`, or `"127.0.0.1"`, `_banner()` SHALL include that host string and the label `Network` in its output.

**Validates: Requirements 3.3**

---

### Property 5: WEB_PORT env var is accepted for any valid port

*For any* integer in the range 1–65535 set as the `WEB_PORT` environment variable, `_parse_args()` SHALL return that integer as the port without raising `SystemExit`.

**Validates: Requirements 2.2**

---

### Property 6: WEB_PORT env var is rejected for any invalid port

*For any* value set as `WEB_PORT` that is not a valid integer in the range 1–65535 (including out-of-range integers, zero, negative numbers, and non-numeric strings), `_parse_args()` SHALL raise `SystemExit` with a non-zero code.

**Validates: Requirements 2.3**

---

### Property 7: _detect_tailscale_ip returns None or a valid Tailscale address

*For any* mocked environment, `_detect_tailscale_ip()` SHALL return either `None` or a string matching the pattern `100\.\d{1,3}\.\d{1,3}\.\d{1,3}` where the second octet is in the range 64–127.

**Validates: Requirements 1.1**

---

### Property 8: Mobile nav calls onNavigate for any route

*For any* route defined in the `routes` array in `AppShell.tsx`, clicking its corresponding `.mobile-nav-item` button SHALL invoke the `onNavigate` callback with exactly that route's `path` string.

**Validates: Requirements 5.5**

---

### Property 9: Mobile nav overflow — primary routes always visible

*For any* `routes` array with more than `PRIMARY_COUNT` items, the rendered `.mobile-nav` SHALL contain exactly `PRIMARY_COUNT` primary `.mobile-nav-item` buttons plus one "More" button, totalling `PRIMARY_COUNT + 1` direct children.

**Validates: Requirements 10.1**

---

### Property 10: Mobile nav overflow — More button active state when hidden route is current

*For any* route in `moreRoutes`, when `currentPath` matches that route's path, the "More" button SHALL have the `active` class applied to it.

**Validates: Requirements 10.3**

---

### Property 11: RunTable renders cards on mobile, table on desktop

*For any* non-empty `runs` array, the `RunTable` component SHALL render a `.run-card-list` element (for mobile) and a `.run-table-desktop` element (for desktop), with CSS controlling which is visible. The number of `.run-card` elements SHALL equal the number of runs.

**Validates: Requirements 11.1, 11.4**

---

### Property 12: Chart touch handler maps X position to nearest trade index

*For any* touch X position within the chart SVG bounds and any non-empty `points` array, the computed trade index SHALL be clamped to `[0, points.length - 1]` and SHALL equal `Math.round((relX / innerW) * (points.length - 1))` clamped to that range.

**Validates: Requirements 12.2**

---

## Error Handling

### Tailscale detection failures

`_detect_tailscale_ip()` is wrapped in broad exception handling. Any `FileNotFoundError` (CLI not installed), `subprocess.TimeoutExpired`, `OSError`, or `ValueError` during detection is caught silently and causes the function to fall through to the socket fallback or return `None`. The caller (`main()`) prints a user-visible warning when `None` is returned and `--tailscale` was requested.

```python
def _detect_tailscale_ip() -> str | None:
    # Step 1: CLI
    try:
        result = subprocess.run(
            ["tailscale", "ip", "--4"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            addr = result.stdout.strip()
            if _in_tailscale_range(addr):
                return addr
    except Exception:
        pass

    # Step 2: Socket fallback
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            addr = info[4][0]
            if _in_tailscale_range(addr):
                return addr
    except Exception:
        pass

    return None
```

### Invalid `WEB_PORT`

Detected in `_parse_args()` before any server startup. Prints a clear error to `stderr` and calls `sys.exit(1)`. This is the standard argparse error pattern already used in the project.

### CSS / mobile nav

No error handling needed — CSS failures degrade gracefully (the desktop layout remains functional). The mobile nav uses `<button>` elements with `onClick` handlers; if `onNavigate` throws, the error propagates normally through React's error boundary (if one exists) or to the console.

---

## Testing Strategy

### Unit tests — `tests/web/test_run_web_tailscale.py`

Uses `pytest` with `unittest.mock` (already available in the project). Uses `hypothesis` for property-based tests (already present — `.hypothesis/` directory exists in the repo).

**Example-based tests:**

| Test | What it verifies |
|---|---|
| `test_detect_tailscale_ip_returns_none_when_no_tailscale` | Mock subprocess raises `FileNotFoundError`; mock socket returns no 100.x addresses → returns `None` |
| `test_detect_tailscale_ip_from_cli` | Mock subprocess returns `"100.64.0.1\n"` → returns `"100.64.0.1"` |
| `test_detect_tailscale_ip_from_socket_fallback` | Mock subprocess fails; mock socket returns `"100.64.0.1"` → returns `"100.64.0.1"` |
| `test_web_host_env_default` | Set `WEB_HOST=192.168.1.10` → parsed host is `"192.168.1.10"` |
| `test_banner_no_tailscale_when_not_passed` | `_banner(..., tailscale_ip=None)` → output does not contain `"Tailscale"` |
| `test_tailscale_flag_registered` | `_parse_args(["--tailscale"])` → `args.tailscale is True` |

**Property-based tests (Hypothesis):**

Each property test runs a minimum of 100 iterations. Tag format: `# Feature: web-mobile-tailscale, Property N: <text>`

| Test | Property | Hypothesis strategy |
|---|---|---|
| `test_banner_includes_tailscale_url` | Property 1 | `st.from_regex(r"100\.(6[4-9]\|[7-9]\d\|1[01]\d\|12[0-7])\.\d{1,3}\.\d{1,3}", fullmatch=True)` |
| `test_banner_omits_tailscale_when_none` | Property 2 | `st.integers(1, 65535)` for port, `st.text()` for host |
| `test_banner_always_has_loopback_and_docs` | Property 3 | `st.integers(1, 65535)` for port |
| `test_banner_network_line_for_nonloopback_host` | Property 4 | `st.ip_addresses(v=4).map(str)` filtered to non-loopback, non-0.0.0.0 |
| `test_web_port_env_valid` | Property 5 | `st.integers(1, 65535)` |
| `test_web_port_env_invalid_exits` | Property 6 | `st.one_of(st.integers(max_value=0), st.integers(min_value=65536), st.text().filter(lambda s: not s.isdigit()))` |
| `test_detect_tailscale_ip_return_type` | Property 7 | `st.one_of(st.just(None), st.from_regex(r"100\.\d{1,3}\.\d{1,3}\.\d{1,3}"))` via mock |

### Static / smoke tests — `tests/web/test_mobile_css.py`

These tests read static files and assert the presence of required strings. They run in milliseconds and require no browser.

| Test | File checked | Assertion |
|---|---|---|
| `test_viewport_fit_cover` | `app/re_web/index.html` | Contains `viewport-fit=cover` |
| `test_safe_area_inset_bottom` | `app/re_web/src/styles/app.css` | Contains `env(safe-area-inset-bottom)` |
| `test_safe_area_inset_top` | `app/re_web/src/styles/app.css` | Contains `env(safe-area-inset-top)` |
| `test_touch_target_min_height` | `app/re_web/src/styles/app.css` | Contains `min-height: 44px` inside 680px block |
| `test_input_font_size_16px` | `app/re_web/src/styles/app.css` | Contains `font-size: 16px` for inputs inside 680px block |
| `test_mobile_nav_display_flex` | `app/re_web/src/styles/app.css` | Contains `.mobile-nav` with `display: flex` inside 680px block |
| `test_sidebar_hidden_mobile` | `app/re_web/src/styles/app.css` | Contains `.sidebar` with `display: none` inside 680px block |
| `test_metric_grid_two_column` | `app/re_web/src/styles/app.css` | Contains `repeat(2, 1fr)` for `.metric-grid` inside 680px block |
| `test_tab_list_scrollbar_hidden` | `app/re_web/src/styles/app.css` | Contains `scrollbar-width: none` inside 680px block |
| `test_dev_script_binds_0000` | `app/re_web/package.json` | `dev` script contains `--host 0.0.0.0` |
| `test_preview_script_binds_0000` | `app/re_web/package.json` | `preview` script contains `--host 0.0.0.0` |
| `test_vite_proxy_intact` | `app/re_web/vite.config.ts` | Contains proxy to `http://127.0.0.1:8000` |
| `test_mobile_more_sheet_css` | `app/re_web/src/styles/app.css` | Contains `.mobile-more-sheet` with `display: flex` inside 680px block |
| `test_run_card_list_css` | `app/re_web/src/styles/app.css` | Contains `.run-card-list` with `display: grid` inside 680px block |
| `test_run_table_desktop_hidden` | `app/re_web/src/styles/app.css` | Contains `.run-table-desktop` with `display: none` inside 680px block |
| `test_hover_none_button_reset` | `app/re_web/src/styles/app.css` | Contains `.button:hover` reset inside `@media (hover: none)` block |
| `test_webkit_overflow_scrolling` | `app/re_web/src/styles/app.css` | Contains `-webkit-overflow-scrolling: touch` applied to `.terminal` |
| `test_param_row_mobile_two_col` | `app/re_web/src/styles/app.css` | Contains `.param-row` with `grid-template-columns: 1fr 1fr` inside 680px block |
| `test_run_selector_full_width` | `app/re_web/src/styles/app.css` | Contains `.run-selector-wrap` with `width: 100%` inside 680px block |
| `test_chip_min_height` | `app/re_web/src/styles/app.css` | Contains `.chip` with `min-height: 36px` inside 680px block |

### Dual testing rationale

Unit + property tests cover the Python logic exhaustively. Static file tests cover the CSS and config changes without requiring a browser or build step. End-to-end Playwright tests (already scaffolded in `package.json`) can be added later for visual regression, but are not required for this feature.
