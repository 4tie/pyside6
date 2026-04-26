# Implementation Plan: web-mobile-tailscale

## Overview

Implement Tailscale remote-access support in `run_web.py` and full iPhone/mobile UI support in the React SPA. The backend changes are confined to `run_web.py` and `.env.example`; the frontend changes are confined to `index.html`, `package.json`, `AppShell.tsx`, and `app.css`. All tests live in `tests/web/`.

---

## Tasks

### A — Backend: Tailscale detection and env-var support

- [x] A1. Add `_detect_tailscale_ip()` and `_in_tailscale_range()` to `run_web.py`
  - Add `_in_tailscale_range(addr: str) -> bool` helper using integer arithmetic on the second octet (64–127) to check the Tailscale CGNAT range `100.64.0.0/10`
  - Add `_detect_tailscale_ip() -> str | None` with two-step detection:
    1. `subprocess.run(["tailscale", "ip", "--4"], capture_output=True, text=True, timeout=2)` — return address if exit code 0 and result passes `_in_tailscale_range`
    2. Socket fallback: `socket.getaddrinfo(socket.gethostname(), None)` — return first address passing `_in_tailscale_range`
  - Wrap each step in broad `except Exception: pass` so any `FileNotFoundError`, `TimeoutExpired`, or `OSError` falls through silently
  - Add `import subprocess` and `import socket` at the top of the file (stdlib, no new packages)
  - _Requirements: 1.1_

- [x] A2. Update `_parse_args()` to support `--tailscale`, `WEB_HOST`, and `WEB_PORT`
  - Change `--host` default to `os.environ.get("WEB_HOST", "0.0.0.0")`
  - Read `WEB_PORT` from env before building the parser; validate it is an integer in 1–65535; print error to `sys.stderr` and call `sys.exit(1)` on invalid value; use validated value as `--port` default (fallback `8000`)
  - Add `--tailscale` flag: `action="store_true"`, default `False`, help text `"Print Tailscale URL in banner (auto-detects 100.x.x.x address)"`
  - _Requirements: 1.5, 2.1, 2.2, 2.3, 2.4_

- [x] A3. Update `_banner()` to show Tailscale and Network lines
  - Change signature to `_banner(host: str, port: int, log_file: Path, reload: bool, tailscale_ip: str | None = None) -> None`
  - Add Tailscale line (only when `tailscale_ip is not None`): label `Tailscale`, URL `http://<tailscale_ip>:<port>/app`
  - Add Network line (only when `host` is not `"0.0.0.0"` and not `"::"`): label `Network`, URL `http://<host>:<port>/app`
  - Keep existing Local, API docs, React app, Log file, and Reload lines unchanged
  - _Requirements: 1.2, 3.1, 3.2, 3.3, 3.4_

- [x] A4. Update `main()` to call detection and pass result to banner
  - After `_setup_logging`, call `_detect_tailscale_ip()` when `args.tailscale` is `True`; assign result to `tailscale_ip`
  - If `args.tailscale` is `True` and `tailscale_ip is None`, print a warning to stdout: `"Warning: --tailscale set but no Tailscale IP detected. Starting normally."`
  - Pass `tailscale_ip=tailscale_ip` (or `None` when `--tailscale` not set) to `_banner()`
  - _Requirements: 1.2, 1.3, 1.4_

- [x] A5. Update `.env.example` to document `WEB_HOST` and `WEB_PORT`
  - Add two lines near the top of the server-configuration section (or at the end if no such section exists):
    ```
    WEB_HOST=0.0.0.0   # Bind address for run_web.py (default: 0.0.0.0)
    WEB_PORT=8000      # TCP port for run_web.py (default: 8000)
    ```
  - _Requirements: 2.4_

---

### B — Frontend foundations: viewport and dev-server binding

- [x] B1. Update viewport meta in `app/re_web/index.html`
  - Change `<meta name="viewport" content="width=device-width, initial-scale=1.0" />` to `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />`
  - _Requirements: 4.1_

- [x] B2. Update `dev` and `preview` scripts in `app/re_web/package.json`
  - Change `"dev": "vite --host 127.0.0.1"` to `"dev": "vite --host 0.0.0.0"`
  - Change `"preview": "vite preview --host 127.0.0.1"` to `"preview": "vite preview --host 0.0.0.0"`
  - Leave all other scripts and dependencies unchanged
  - _Requirements: 9.1, 9.3_

---

### C — Frontend: mobile navigation bar

- [x] C1. Add `<nav className="mobile-nav">` to `AppShell.tsx`
  - After the closing `</main>` tag, insert a `<nav className="mobile-nav" aria-label="Mobile navigation">` element
  - Inside the nav, map over the existing `routes` array to render one `<button>` per route with:
    - `type="button"`, `className={active ? 'mobile-nav-item active' : 'mobile-nav-item'}`
    - `onClick={() => onNavigate(route.path)}`
    - `aria-label={route.label}`, `aria-current={active ? 'page' : undefined}`
    - Active logic: `currentPath === route.path || (route.path !== '/app' && currentPath.startsWith(route.path))`
    - Children: `{route.icon}` and `<span>{route.label}</span>`
  - If `AppShell.tsx` exceeds 150 lines after this addition, extract the nav markup and its props interface to `app/re_web/src/components/MobileNav.tsx` and import it; the `routes` array and `RouteItem` type are already in scope
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

---

### D — Frontend: mobile CSS

- [x] D1. Add `.mobile-nav` and `.mobile-nav-item` base rules to `app/re_web/src/styles/app.css`
  - Add outside any media query (hidden by default on desktop):
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
  - _Requirements: 5.1, 5.2, 5.3, 4.3_

- [x] D2. Add all mobile-specific rules inside `@media (max-width: 680px)` in `app.css`
  - Navigation swap — sidebar hidden, mobile nav shown:
    ```css
    .sidebar { display: none; }
    .mobile-nav { display: flex; }
    ```
  - Content padding to avoid overlap with fixed nav:
    ```css
    .content { padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
    ```
  - Safe-area insets:
    ```css
    body { padding-top: env(safe-area-inset-top); }
    ```
  - Touch targets (44 px minimum):
    ```css
    .button, .icon-button, .nav-link, .tab {
      min-height: 44px;
      min-width: 44px;
    }
    ```
  - Typography:
    ```css
    body { font-size: 15px; }
    input, select, textarea { font-size: 16px; }
    .metric-value { font-size: 20px; }
    ```
  - Layout — update existing `.metric-grid` rule from `1fr` to `repeat(2, 1fr)`, and add:
    ```css
    .split-layout, .optimizer-layout { grid-template-columns: 1fr; }
    .form-grid { grid-template-columns: 1fr; }
    .page-header { flex-direction: column; align-items: stretch; }
    .page-header .button { width: 100%; justify-content: center; }
    ```
  - Overflow containment:
    ```css
    body { overflow-x: hidden; }
    .table-wrap { overflow-x: auto; max-width: 100%; }
    ```
  - Tab scrollbar hiding:
    ```css
    .tab-list { scrollbar-width: none; }
    .tab-list::-webkit-scrollbar { display: none; }
    ```
  - Note: the existing `@media (max-width: 680px)` block already has `.metric-grid { grid-template-columns: 1fr; }` and `.metric-value { font-size: 20px; }` — update the metric-grid rule in place and keep or override metric-value as needed
  - _Requirements: 4.2, 4.3, 4.4, 5.1, 5.6, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

---

### E — Tests

- [x] E1. Write `tests/web/test_run_web_tailscale.py` — example-based tests
  - Import `run_web` module functions directly; use `unittest.mock.patch` for subprocess and socket
  - `test_detect_tailscale_ip_returns_none_when_no_tailscale`: mock subprocess raises `FileNotFoundError`; mock `socket.getaddrinfo` returns no `100.x` addresses → assert return is `None`
  - `test_detect_tailscale_ip_from_cli`: mock subprocess returns `returncode=0`, `stdout="100.64.0.1\n"` → assert return is `"100.64.0.1"`
  - `test_detect_tailscale_ip_from_socket_fallback`: mock subprocess returns non-zero exit; mock `socket.getaddrinfo` returns entry with address `"100.64.0.1"` → assert return is `"100.64.0.1"`
  - `test_web_host_env_default`: set `WEB_HOST=192.168.1.10` in env, call `_parse_args([])` → assert `args.host == "192.168.1.10"`
  - `test_banner_no_tailscale_when_not_passed`: capture stdout from `_banner("0.0.0.0", 8000, Path("/tmp/web.log"), False, tailscale_ip=None)` → assert `"Tailscale"` not in output
  - `test_tailscale_flag_registered`: call `_parse_args(["--tailscale"])` → assert `args.tailscale is True`
  - _Requirements: 1.1, 1.2, 1.4, 2.1_

- [x] E2. Write `tests/web/test_run_web_tailscale.py` — Hypothesis property-based tests
  - Add to the same file as E1; import `hypothesis` strategies and `settings`
  - `test_banner_includes_tailscale_url` — Property 1: use `st.from_regex(r"100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}", fullmatch=True)` for `tailscale_ip`; assert captured stdout contains the IP and `"Tailscale"`; `@settings(max_examples=200)`
    - **Property 1: Banner includes Tailscale URL when IP is provided**
    - **Validates: Requirements 1.2, 3.2**
  - `test_banner_omits_tailscale_when_none` — Property 2: `st.integers(1, 65535)` for port, `st.text()` for host; call `_banner` with `tailscale_ip=None`; assert `"Tailscale"` not in output; `@settings(max_examples=200)`
    - **Property 2: Banner omits Tailscale section when no IP is provided**
    - **Validates: Requirements 1.4, 3.2**
  - `test_banner_always_has_loopback_and_docs` — Property 3: `st.integers(1, 65535)` for port; assert output contains `f"http://127.0.0.1:{port}"` and `f"http://127.0.0.1:{port}/docs"`; `@settings(max_examples=200)`
    - **Property 3: Banner always contains loopback URL and docs URL**
    - **Validates: Requirements 3.1, 3.4**
  - `test_banner_network_line_for_nonloopback_host` — Property 4: `st.ip_addresses(v=4).map(str)` filtered to exclude `"127.0.0.1"`, `"0.0.0.0"`, `"::"` ; assert output contains the host string and `"Network"`; `@settings(max_examples=200)`
    - **Property 4: Banner includes Network URL for non-loopback host**
    - **Validates: Requirements 3.3**
  - `test_web_port_env_valid` — Property 5: `st.integers(1, 65535)` for port value; set as `WEB_PORT` env var; call `_parse_args([])` inside `monkeypatch`; assert no `SystemExit` and `args.port == port`; `@settings(max_examples=300)`
    - **Property 5: WEB_PORT env var accepted for any valid port 1–65535**
    - **Validates: Requirements 2.2**
  - `test_web_port_env_invalid_exits` — Property 6: `st.one_of(st.integers(max_value=0), st.integers(min_value=65536), st.text().filter(lambda s: not s.strip().lstrip("-").isdigit()))` for invalid values; set as `WEB_PORT`; assert `pytest.raises(SystemExit)` with non-zero code; `@settings(max_examples=300)`
    - **Property 6: WEB_PORT env var rejected for any invalid port**
    - **Validates: Requirements 2.3**
  - `test_detect_tailscale_ip_return_type` — Property 7: mock subprocess and socket with `st.one_of(st.just(None), st.from_regex(r"100\.\d{1,3}\.\d{1,3}\.\d{1,3}"))` to control what the mocks return; assert result is either `None` or matches `r"^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}$"`; `@settings(max_examples=200)`
    - **Property 7: _detect_tailscale_ip returns None or a valid Tailscale address**
    - **Validates: Requirements 1.1**
  - _Requirements: 1.1, 1.2, 1.4, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4_

- [x] E3. Write `tests/web/test_mobile_css.py` — static file smoke tests
  - All tests read static files from the workspace root using `pathlib.Path`; no browser or build step required
  - `test_viewport_fit_cover`: read `app/re_web/index.html` → assert `"viewport-fit=cover"` in content
  - `test_safe_area_inset_bottom`: read `app/re_web/src/styles/app.css` → assert `"env(safe-area-inset-bottom)"` in content
  - `test_safe_area_inset_top`: read `app/re_web/src/styles/app.css` → assert `"env(safe-area-inset-top)"` in content
  - `test_touch_target_min_height`: read `app.css` → assert `"min-height: 44px"` appears inside the `@media (max-width: 680px)` block
  - `test_input_font_size_16px`: read `app.css` → assert `"font-size: 16px"` appears inside the `@media (max-width: 680px)` block
  - `test_mobile_nav_display_flex`: read `app.css` → assert `.mobile-nav` with `display: flex` appears inside the `@media (max-width: 680px)` block
  - `test_sidebar_hidden_mobile`: read `app.css` → assert `.sidebar` with `display: none` appears inside the `@media (max-width: 680px)` block
  - `test_metric_grid_two_column`: read `app.css` → assert `"repeat(2, 1fr)"` appears inside the `@media (max-width: 680px)` block
  - `test_tab_list_scrollbar_hidden`: read `app.css` → assert `"scrollbar-width: none"` appears inside the `@media (max-width: 680px)` block
  - `test_dev_script_binds_0000`: read `app/re_web/package.json` → parse JSON; assert `scripts["dev"]` contains `"--host 0.0.0.0"`
  - `test_preview_script_binds_0000`: read `app/re_web/package.json` → parse JSON; assert `scripts["preview"]` contains `"--host 0.0.0.0"`
  - `test_vite_proxy_intact`: read `app/re_web/vite.config.ts` → assert `"http://127.0.0.1:8000"` in content
  - _Requirements: 4.1, 4.3, 4.4, 5.1, 5.6, 6.1, 7.2, 8.1, 8.6, 9.1, 9.2, 9.3_

- [x] E4. Checkpoint — ensure all tests pass
  - Run `pytest tests/web/test_run_web_tailscale.py tests/web/test_mobile_css.py -v`
  - Ensure all example-based and property-based tests pass with no errors or warnings
  - Ask the user if any questions arise before proceeding

---

### F — Mobile enhancements: navigation overflow

- [x] F1. Add overflow "More" button and sheet to `AppShell.tsx`
  - Add `import { MoreHorizontal } from 'lucide-react'` to the existing lucide imports
  - Add `const [moreOpen, setMoreOpen] = useState(false)` state (import `useState` if not already imported)
  - Define `const PRIMARY_COUNT = 4` and split `routes` into `primaryRoutes = routes.slice(0, PRIMARY_COUNT)` and `moreRoutes = routes.slice(PRIMARY_COUNT)`
  - Compute `moreIsActive = moreRoutes.some(r => currentPath === r.path || (r.path !== '/app' && currentPath.startsWith(r.path)))`
  - In the `.mobile-nav`, render only `primaryRoutes` as `.mobile-nav-item` buttons (same logic as before), then add a fifth button with `className={moreIsActive ? 'mobile-nav-item active' : 'mobile-nav-item'}` containing `<MoreHorizontal size={20} />` and `<span>More</span>`, with `onClick={() => setMoreOpen((o) => !o)}`
  - After the `.mobile-nav`, render conditionally when `moreOpen`:
    - A `<div className="mobile-more-backdrop" onClick={() => setMoreOpen(false)} />`
    - A `<div className="mobile-more-sheet">` containing `moreRoutes.map(...)` as `.mobile-nav-item` buttons with the same active logic and `onClick` that calls `onNavigate(route.path)` then `setMoreOpen(false)`
  - If `AppShell.tsx` exceeds 150 lines, extract the mobile nav (primary + more button + sheet) to `MobileNav.tsx`
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] F2. Add `.mobile-more-backdrop` and `.mobile-more-sheet` CSS to `app.css`
  - Add base rules (outside media query, hidden on desktop):
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
  - Inside `@media (max-width: 680px)`:
    ```css
    .mobile-more-backdrop { display: block; }
    .mobile-more-sheet    { display: flex; flex-direction: column; }
    ```
  - _Requirements: 10.1, 10.2, 10.5_

---

### G — Mobile enhancements: RunTable card layout

- [x] G1. Add card layout markup to `RunTable.tsx`
  - After the existing `<div className="table-wrap">…</div>`, add `className="run-table-desktop"` to that wrapper div
  - After the table wrapper, add a `<div className="run-card-list">` containing `runs.map((run) => ...)` with each run rendered as:
    ```tsx
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
    ```
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] G2. Add `.run-card-list` and `.run-card` CSS to `app.css`
  - Add base rule (outside media query):
    ```css
    .run-card-list { display: none; }
    ```
  - Inside `@media (max-width: 680px)`:
    ```css
    .run-table-desktop { display: none; }
    .run-card-list { display: grid; gap: 8px; }
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
  - _Requirements: 11.1, 11.2, 11.3, 11.5_

---

### H — Mobile enhancements: equity chart touch

- [x] H1. Add touch event handlers to `EquityChart` in `RunDetailPage.tsx`
  - Add a `getTouchX` helper inside the `EquityChart` component:
    ```tsx
    function getTouchX(e: React.TouchEvent<SVGSVGElement>): number {
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect || !e.touches.length) return 0;
      return ((e.touches[0].clientX - rect.left) / rect.width) * W;
    }
    ```
  - Add `onTouchMove`, `onTouchEnd`, and `style={{ touchAction: 'none' }}` to the `<svg>` element:
    ```tsx
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
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

---

### I — Mobile enhancements: iOS polish and layout fixes

- [x] I1. Add `-webkit-overflow-scrolling: touch` to scrollable containers in `app.css`
  - Add outside any media query (applies globally):
    ```css
    .terminal,
    .json-block,
    .param-list,
    .table-wrap,
    .tab-list,
    .nav-list {
      -webkit-overflow-scrolling: touch;
    }
    ```
  - _Requirements: 13.1_

- [x] I2. Add `@media (hover: none)` hover-reset block to `app.css`
  - Add a new `@media (hover: none)` block:
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
  - _Requirements: 13.2, 13.3_

- [x] I3. Add dense-data and layout fix rules inside `@media (max-width: 680px)` in `app.css`
  - Param rows and trial tiles — 2-column on mobile:
    ```css
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
    ```
  - Run selector full-width:
    ```css
    .run-selector-wrap { min-width: 0; width: 100%; max-width: 100%; }
    ```
  - Comparison controls full-width selects:
    ```css
    .comparison-controls label { flex: 1 1 100%; }
    .comparison-controls select { width: 100%; }
    ```
  - Chip tap targets:
    ```css
    .chip { min-height: 36px; padding: 0 10px; }
    ```
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

---

### J — Tests: enhancement smoke and property tests

- [x] J1. Extend `tests/web/test_mobile_css.py` with enhancement smoke tests
  - `test_mobile_more_sheet_css`: read `app.css` → assert `.mobile-more-sheet` with `display: flex` appears inside `@media (max-width: 680px)` block
  - `test_run_card_list_css`: read `app.css` → assert `.run-card-list` with `display: grid` appears inside `@media (max-width: 680px)` block
  - `test_run_table_desktop_hidden`: read `app.css` → assert `.run-table-desktop` with `display: none` appears inside `@media (max-width: 680px)` block
  - `test_hover_none_button_reset`: read `app.css` → assert `.button:hover` reset appears inside `@media (hover: none)` block
  - `test_webkit_overflow_scrolling`: read `app.css` → assert `-webkit-overflow-scrolling: touch` appears and `.terminal` is in the same rule block
  - `test_param_row_mobile_two_col`: read `app.css` → assert `.param-row` with `grid-template-columns: 1fr 1fr` appears inside `@media (max-width: 680px)` block
  - `test_run_selector_full_width`: read `app.css` → assert `.run-selector-wrap` with `width: 100%` appears inside `@media (max-width: 680px)` block
  - `test_chip_min_height`: read `app.css` → assert `.chip` with `min-height: 36px` appears inside `@media (max-width: 680px)` block
  - _Requirements: 10.1, 11.1, 13.2, 13.1, 14.1, 14.2, 14.4_

- [x] J2. Add property-based tests for enhancement properties to `tests/web/test_run_web_tailscale.py`
  - These are TypeScript/React component properties; since no React test runner is configured, implement them as static analysis tests that parse the TSX source files using Python string matching
  - `test_appshell_primary_count_constant`: read `AppShell.tsx` → assert `PRIMARY_COUNT` constant is defined and equals `4`
    - **Property 9: Mobile nav overflow — primary routes always visible**
    - **Validates: Requirements 10.1**
  - `test_appshell_more_routes_sliced`: read `AppShell.tsx` → assert `routes.slice(PRIMARY_COUNT)` or equivalent appears in the file
    - **Property 10: Mobile nav overflow — More button active state**
    - **Validates: Requirements 10.3**
  - `test_run_table_has_card_list`: read `RunTable.tsx` → assert `run-card-list` className appears in the file
    - **Property 11: RunTable renders cards on mobile**
    - **Validates: Requirements 11.1**
  - `test_equity_chart_has_touch_move`: read `RunDetailPage.tsx` → assert `onTouchMove` appears in the file
    - **Property 12: Chart touch handler maps X position to nearest trade index**
    - **Validates: Requirements 12.1**
  - `test_equity_chart_touch_action_none`: read `RunDetailPage.tsx` → assert `touchAction: 'none'` or `touch-action: none` appears in the file
    - **Property 12 (continued)**
    - **Validates: Requirements 12.5**
  - _Requirements: 10.1, 10.3, 11.1, 12.1, 12.5_

- [x] J3. Checkpoint — run all tests
  - Run `pytest tests/web/ -v`
  - Ensure all tests pass including the new J1 and J2 tests
  - Ask the user if any questions arise before proceeding

---

## Notes

- Tasks A–E are complete (all marked `[x]`). Tasks F–J are the new enhancement work.
- Tasks are ordered: nav overflow (F) → RunTable cards (G) → chart touch (H) → iOS polish (I) → tests (J)
- F1 and F2 are coupled — implement both before testing the overflow sheet
- G1 and G2 are coupled — the card list is invisible until G2 CSS is added
- H1 is self-contained; it only touches `RunDetailPage.tsx`
- I1, I2, I3 are all CSS-only changes to `app.css`; they can be done in any order
- The `MobileNav.tsx` extraction condition from C1 still applies — check line count after F1
- Property tests in J2 use Python string matching on TSX source files as a lightweight substitute for a React test runner; they verify structural presence, not runtime behaviour
- `vite.config.ts` requires no changes (proxy already correct per design)
