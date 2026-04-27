# Tasks

## Task List

- [x] 1. Create script skeleton and environment loading
  - [x] 1.1 Create `sc/` directory and `sc/cache_log_analyzer.py` with module docstring and `if __name__ == "__main__"` guard
  - [x] 1.2 Implement `load_env()`: call `dotenv.load_dotenv()`, read `OLLAMA_BASE_URL` and `OLLAMA_MODEL` with fallbacks into module-level constants
  - [x] 1.3 Implement `main()` stub that calls `load_env()` and prints the three phase headers in order

- [x] 2. Implement cache cleanup phase
  - [x] 2.1 Implement `clean_cache(root: str) -> list[str]`: walk tree, skip paths containing `.venv` or `.git`, delete `__pycache__` dirs (with `shutil.rmtree`) and `.pyc` files, collect deleted paths
  - [x] 2.2 Print confirmation for each deleted path; print "no cache files found" when list is empty
  - [x] 2.3 Wire `clean_cache` into `main()` as Phase 1

- [x] 3. Implement log scanning phase
  - [x] 3.1 Define `ANOMALY_KEYWORDS` list with the six default keywords
  - [x] 3.2 Implement `scan_logs(log_dir: str, keywords: list[str]) -> list[str]`: iterate files in `log_dir`, collect lines matching level markers or keywords (case-insensitive for keywords), handle unreadable files with a printed warning
  - [x] 3.3 Wire `scan_logs` into `main()` as Phase 2; handle empty Event_Collection by printing message and returning early

- [x] 4. Implement AI analysis phase
  - [x] 4.1 Implement `analyze_with_ollama(events, base_url, model) -> str | None`: build `/api/chat` POST payload with system prompt and joined event lines, send with `requests.post(..., stream=False)`, extract assistant content; return `None` and print error on connection error or non-200 status
  - [x] 4.2 Implement `write_report(content: str, report_path: str) -> bool`: prepend timestamp header, write to file, return `True`/`False`, print confirmation or error
  - [x] 4.3 Wire `analyze_with_ollama` and `write_report` into `main()` as Phase 3

- [x] 5. Unit tests
  - [x] 5.1 Write example-based tests for `clean_cache`: empty tree returns `[]`; tree with targets returns correct list; `.venv`/`.git` paths are skipped
  - [x] 5.2 Write example-based tests for `scan_logs`: no matching lines returns `[]`; unreadable file prints warning and continues; all three level markers are matched
  - [x] 5.3 Write example-based tests for `analyze_with_ollama`: mocked 200 returns content; mocked connection error returns `None`; mocked 500 returns `None`
  - [x] 5.4 Write example-based tests for `write_report`: successful write returns `True` and file contains header + content; write failure returns `False`
  - [x] 5.5 Write example-based test for phase ordering: stdout contains the three phase headers in correct sequence

- [x] 6. Property-based tests (Hypothesis)
  - [x] 6.1 P1 — Cache cleanup removes all targets and respects exclusions: generate random temp trees, assert no targets remain outside exclusions after `clean_cache`
  - [x] 6.2 P2 — Deleted paths are reported: assert returned list equals actually-deleted paths
  - [x] 6.3 P3 — Event collection completeness: generate random log lines, assert `scan_logs` result contains exactly the matching lines
  - [x] 6.4 P4 — All log files are scanned: generate multiple temp log files, assert events from every file appear in result
  - [x] 6.5 P5 — Event collection forwarded completely to Ollama: generate random event lists, mock `requests.post`, assert all events appear in captured payload
  - [x] 6.6 P6 — Report content round-trip: generate random assistant messages, write via `write_report`, read back, assert content is present
  - [x] 6.7 P7 — Report header always present: generate random assistant messages, assert report file starts with correct header
  - [x] 6.8 P8 — Environment variable fallback correctness: test all four combinations of env var presence/absence, assert resolved values match expected
