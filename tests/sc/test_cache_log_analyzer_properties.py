"""
Property-based tests for sc/cache_log_analyzer.py using Hypothesis.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Ensure sc/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import sc.cache_log_analyzer as cla


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LEVEL_MARKERS = ("ERROR", "CRITICAL", "WARNING")


def _line_should_match(line: str, keywords: list) -> bool:
    if any(m in line for m in LEVEL_MARKERS):
        return True
    if any(kw.lower() in line.lower() for kw in keywords):
        return True
    return False


# ---------------------------------------------------------------------------
# P1 — Cache cleanup removes all targets and respects exclusions
# Feature: cache-log-analyzer, Property 1: Cache cleanup removes all targets and respects exclusions
# ---------------------------------------------------------------------------

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    depths=st.lists(st.integers(min_value=0, max_value=3), min_size=1, max_size=6),
    n_venv=st.integers(min_value=0, max_value=3),
    n_git=st.integers(min_value=0, max_value=3),
)
def test_p1_clean_cache_removes_targets_respects_exclusions(tmp_path, depths, n_venv, n_git):
    # Feature: cache-log-analyzer, Property 1: Cache cleanup removes all targets and respects exclusions

    # Create __pycache__ dirs at various depths outside exclusions
    for i, depth in enumerate(depths):
        parts = [f"pkg{i}"] * depth
        parent = tmp_path.joinpath(*parts) if parts else tmp_path
        parent.mkdir(parents=True, exist_ok=True)
        pycache = parent / "__pycache__"
        pycache.mkdir(exist_ok=True)
        (pycache / f"mod{i}.pyc").write_text("bytecode")

    # Create .pyc files at root level
    (tmp_path / "root_module.pyc").write_text("bytecode")

    # Create items inside .venv (should be preserved)
    for i in range(n_venv):
        venv_dir = tmp_path / ".venv" / f"lib{i}" / "__pycache__"
        venv_dir.mkdir(parents=True, exist_ok=True)
        (venv_dir / f"venv_mod{i}.pyc").write_text("venv bytecode")

    # Create items inside .git (should be preserved)
    for i in range(n_git):
        git_dir = tmp_path / ".git" / f"hooks{i}" / "__pycache__"
        git_dir.mkdir(parents=True, exist_ok=True)
        (git_dir / f"git_mod{i}.pyc").write_text("git bytecode")

    cla.clean_cache(str(tmp_path))

    # Assert: no __pycache__ or .pyc outside exclusions
    for dirpath, dirnames, filenames in os.walk(str(tmp_path)):
        rel = os.path.relpath(dirpath, str(tmp_path))
        parts = Path(rel).parts
        if ".venv" in parts or ".git" in parts:
            continue
        assert "__pycache__" not in dirnames, f"__pycache__ still exists in {dirpath}"
        for f in filenames:
            assert not f.endswith(".pyc"), f".pyc file still exists: {os.path.join(dirpath, f)}"

    # Assert: .venv and .git contents are untouched
    for i in range(n_venv):
        venv_dir = tmp_path / ".venv" / f"lib{i}" / "__pycache__"
        assert venv_dir.exists(), f".venv pycache was incorrectly deleted: {venv_dir}"

    for i in range(n_git):
        git_dir = tmp_path / ".git" / f"hooks{i}" / "__pycache__"
        assert git_dir.exists(), f".git pycache was incorrectly deleted: {git_dir}"

    # Cleanup for next hypothesis iteration
    for item in list(tmp_path.iterdir()):
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


# ---------------------------------------------------------------------------
# P2 — Deleted paths are reported
# Feature: cache-log-analyzer, Property 2: Deleted paths are reported
# ---------------------------------------------------------------------------

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    n_pycache=st.integers(min_value=0, max_value=5),
    n_pyc=st.integers(min_value=0, max_value=5),
)
def test_p2_deleted_paths_reported(tmp_path, n_pycache, n_pyc):
    # Feature: cache-log-analyzer, Property 2: Deleted paths are reported

    expected_deleted = set()

    for i in range(n_pycache):
        d = tmp_path / f"pkg{i}" / "__pycache__"
        d.mkdir(parents=True, exist_ok=True)
        expected_deleted.add(str(d))

    for i in range(n_pyc):
        f = tmp_path / f"module{i}.pyc"
        f.write_text("bytecode")
        expected_deleted.add(str(f))

    result = cla.clean_cache(str(tmp_path))

    assert set(result) == expected_deleted

    # Cleanup for next hypothesis iteration
    for item in list(tmp_path.iterdir()):
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            try:
                item.unlink()
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# P3 — Event collection completeness
# Feature: cache-log-analyzer, Property 3: Event collection completeness
# ---------------------------------------------------------------------------

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    lines=st.lists(
        st.text(
            alphabet=st.characters(blacklist_characters="\n\r\x00"),
            min_size=0,
            max_size=100,
        ),
        min_size=0,
        max_size=20,
    )
)
def test_p3_event_collection_completeness(tmp_path, lines):
    # Feature: cache-log-analyzer, Property 3: Event collection completeness

    log_file = tmp_path / "app.log"
    log_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    keywords = cla.ANOMALY_KEYWORDS
    result = cla.scan_logs(str(tmp_path), keywords)

    expected = [line for line in lines if _line_should_match(line, keywords)]

    assert result == expected, (
        f"Expected {len(expected)} events, got {len(result)}.\n"
        f"Expected: {expected}\nGot: {result}"
    )

    # Cleanup for next hypothesis iteration
    log_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# P4 — All log files are scanned
# Feature: cache-log-analyzer, Property 4: All log files are scanned
# ---------------------------------------------------------------------------

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    file_events=st.lists(
        st.lists(
            st.sampled_from(["ERROR event_a", "CRITICAL event_b", "WARNING event_c"]),
            min_size=1,
            max_size=5,
        ),
        min_size=1,
        max_size=6,
    )
)
def test_p4_all_log_files_scanned(tmp_path, file_events):
    # Feature: cache-log-analyzer, Property 4: All log files are scanned

    for i, events in enumerate(file_events):
        log_file = tmp_path / f"service{i}.log"
        log_file.write_text("\n".join(events) + "\n", encoding="utf-8")

    result = cla.scan_logs(str(tmp_path), [])

    # Every event from every file must appear in result
    for events in file_events:
        for event_line in events:
            assert any(event_line in r for r in result), (
                f"Event '{event_line}' not found in scan result"
            )

    # Cleanup for next hypothesis iteration
    for item in list(tmp_path.iterdir()):
        item.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# P5 — Event collection forwarded completely to Ollama
# Feature: cache-log-analyzer, Property 5: Event collection forwarded completely to Ollama
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    events=st.lists(
        st.text(
            alphabet=st.characters(blacklist_characters="\n\r\x00"),
            min_size=1,
            max_size=80,
        ),
        min_size=1,
        max_size=20,
    )
)
def test_p5_events_forwarded_to_ollama(events):
    # Feature: cache-log-analyzer, Property 5: Event collection forwarded completely to Ollama

    captured_payload = {}

    def mock_post(url, json=None, **kwargs):
        captured_payload.update(json or {})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": "ok"}
        }
        return mock_resp

    with patch("requests.post", side_effect=mock_post):
        cla.analyze_with_ollama(events, "http://localhost:11434", "llama3")

    messages = captured_payload.get("messages", [])
    user_messages = [m for m in messages if m.get("role") == "user"]
    assert user_messages, "No user message found in payload"

    user_content = user_messages[0]["content"]
    for event_line in events:
        assert event_line in user_content, (
            f"Event line '{event_line}' not found in Ollama user message content"
        )


# ---------------------------------------------------------------------------
# P6 — Report content round-trip
# Feature: cache-log-analyzer, Property 6: Report content round-trip
# ---------------------------------------------------------------------------

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    content=st.text(
        # Exclude null bytes, surrogates (not valid UTF-8), and \r (universal newlines
        # mode translates \r -> \n on read, so round-trip would fail for bare \r)
        alphabet=st.characters(
            blacklist_characters="\x00\r",
            blacklist_categories=("Cs",),
        ),
        min_size=0,
        max_size=500,
    )
)
def test_p6_report_content_roundtrip(tmp_path, content):
    # Feature: cache-log-analyzer, Property 6: Report content round-trip

    report_path = tmp_path / "report.md"
    result = cla.write_report(content, str(report_path))

    assert result is True
    written = report_path.read_text(encoding="utf-8")
    assert content in written

    # Cleanup for next hypothesis iteration
    report_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# P7 — Report header always present
# Feature: cache-log-analyzer, Property 7: Report header always present
# ---------------------------------------------------------------------------

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    content=st.text(
        # Exclude null bytes and surrogates (not encodable as UTF-8)
        alphabet=st.characters(
            blacklist_characters="\x00",
            blacklist_categories=("Cs",),
        ),
        min_size=0,
        max_size=200,
    )
)
def test_p7_report_header_always_present(tmp_path, content):
    # Feature: cache-log-analyzer, Property 7: Report header always present

    report_path = tmp_path / "report.md"
    cla.write_report(content, str(report_path))

    written = report_path.read_text(encoding="utf-8")
    assert written.startswith("# App Event Analysis Report\nGenerated:"), (
        f"Report does not start with expected header. Got: {written[:80]!r}"
    )

    # Cleanup for next hypothesis iteration
    report_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# P8 — Environment variable fallback correctness
# Feature: cache-log-analyzer, Property 8: Environment variable fallback correctness
# ---------------------------------------------------------------------------

# Safe text for env vars: no null bytes
safe_env_text = st.text(
    alphabet=st.characters(blacklist_characters="\x00"),
    min_size=1,
    max_size=50,
)


@settings(max_examples=100)
@given(
    base_url=st.one_of(st.none(), safe_env_text),
    model=st.one_of(st.none(), safe_env_text),
)
def test_p8_env_var_fallback_correctness(base_url, model):
    # Feature: cache-log-analyzer, Property 8: Environment variable fallback correctness

    env_overrides = {}
    if base_url is not None:
        env_overrides["OLLAMA_BASE_URL"] = base_url
    if model is not None:
        env_overrides["OLLAMA_MODEL"] = model

    # Build a clean env without the two vars, then add overrides
    clean_env = {
        k: v for k, v in os.environ.items()
        if k not in ("OLLAMA_BASE_URL", "OLLAMA_MODEL")
    }
    clean_env.update(env_overrides)

    with patch.dict(os.environ, clean_env, clear=True):
        with patch.object(cla, "_HAS_DOTENV", False):
            cla.load_env()

    expected_url = base_url if base_url is not None else "http://localhost:11434"
    expected_model = model if model is not None else "llama3"

    assert cla.OLLAMA_BASE_URL == expected_url, (
        f"Expected URL {expected_url!r}, got {cla.OLLAMA_BASE_URL!r}"
    )
    assert cla.OLLAMA_MODEL == expected_model, (
        f"Expected model {expected_model!r}, got {cla.OLLAMA_MODEL!r}"
    )
