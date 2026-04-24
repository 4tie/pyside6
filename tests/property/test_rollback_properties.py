"""Property-based tests for RollbackService using Hypothesis.

Each test creates its own isolated temporary directory via tempfile.TemporaryDirectory
so that Hypothesis can generate multiple examples without fixture state leaking
between runs.

Feature: strategy-rollback
"""
import contextlib
import json
import logging
import logging.handlers
import re
import tempfile
from pathlib import Path

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic
from app.core.services.rollback_service import RollbackService

# ---------------------------------------------------------------------------
# Shared Hypothesis strategies
# ---------------------------------------------------------------------------

_dict_strategy = st.dictionaries(
    st.text(
        min_size=1,
        max_size=10,
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
    ),
    st.text(max_size=20),
    max_size=5,
)

_name_strategy = st.text(
    min_size=1,
    max_size=20,
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_dirs(base: Path, run_name: str = "run_20240315T143022_abc123"):
    """Return (run_dir, user_data) with required subdirectories created."""
    run_dir = base / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    user_data = base / "user_data"
    (user_data / "strategies").mkdir(parents=True, exist_ok=True)
    return run_dir, user_data


def _params_dest(user_data: Path, strategy_name: str) -> Path:
    return user_data / "strategies" / f"{strategy_name}.json"


def _config_dest(user_data: Path) -> Path:
    return user_data / "config.json"


# ---------------------------------------------------------------------------
# Property 1: Params restore round-trip
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 1: Params restore round-trip
@given(content=_dict_strategy)
@settings(max_examples=50)
def test_params_restore_round_trip(content):
    """Validates: Requirements 4.1

    For any valid params content, after rollback with restore_params=True,
    the active params file must contain exactly the same data as the source.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir, user_data = _setup_dirs(base)
        write_json_file_atomic(run_dir / "params.json", content)

        svc = RollbackService()
        result = svc.rollback(
            run_dir, user_data, "TestStrategy",
            restore_params=True, restore_config=False,
        )

        assert result.params_restored is True
        restored = parse_json_file(_params_dest(user_data, "TestStrategy"))
        assert restored == content


# ---------------------------------------------------------------------------
# Property 2: Config restore round-trip
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 2: Config restore round-trip
@given(content=_dict_strategy)
@settings(max_examples=50)
def test_config_restore_round_trip(content):
    """Validates: Requirements 4.2

    For any valid config content, after rollback with restore_config=True,
    the active config file must contain exactly the same data as the source.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir, user_data = _setup_dirs(base)
        write_json_file_atomic(run_dir / "config.snapshot.json", content)

        svc = RollbackService()
        result = svc.rollback(
            run_dir, user_data, "TestStrategy",
            restore_params=False, restore_config=True,
        )

        assert result.config_restored is True
        restored = parse_json_file(_config_dest(user_data))
        assert restored == content


# ---------------------------------------------------------------------------
# Property 3: Backup is created before overwrite
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 3: Backup is created before overwrite
@given(
    active_content=_dict_strategy,
    source_content=_dict_strategy,
)
@settings(max_examples=50)
def test_backup_created_before_overwrite(active_content, source_content):
    """Validates: Requirements 3.1, 3.2

    When an active params file exists and rollback is confirmed, at least one
    .bak_* file must exist in the strategies directory after rollback.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir, user_data = _setup_dirs(base)

        # Write the active params file (the one that will be backed up)
        active_path = _params_dest(user_data, "TestStrategy")
        write_json_file_atomic(active_path, active_content)

        # Write the source params in the run dir
        write_json_file_atomic(run_dir / "params.json", source_content)

        svc = RollbackService()
        svc.rollback(
            run_dir, user_data, "TestStrategy",
            restore_params=True, restore_config=False,
        )

        strategies_dir = user_data / "strategies"
        bak_files = list(strategies_dir.glob("*.bak_*"))
        assert len(bak_files) >= 1, (
            "Expected at least one .bak_* file after rollback"
        )


# ---------------------------------------------------------------------------
# Property 4: Backup filename matches ISO-8601 format
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 4: Backup filename matches ISO-8601 format
@given(dummy=st.just(None))
@settings(max_examples=50)
def test_backup_filename_iso8601_format(dummy):
    """Validates: Requirements 3.4

    The backup filename suffix must match the pattern .bak_YYYYMMDDTHHMMSS.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _, user_data = _setup_dirs(base)
        active_path = _params_dest(user_data, "TestStrategy")
        write_json_file_atomic(active_path, {"key": "value"})

        svc = RollbackService()
        backup_path = svc._backup_file(active_path)

        assert re.search(r"\.bak_\d{8}T\d{6}$", backup_path.name), (
            f"Backup filename '{backup_path.name}' does not match .bak_YYYYMMDDTHHMMSS"
        )


# ---------------------------------------------------------------------------
# Property 5: Backup pruning keeps at most 5 files
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 5: Backup pruning keeps at most 5 files
@given(n=st.integers(min_value=0, max_value=20))
@settings(max_examples=50)
def test_backup_pruning_keeps_at_most_5(n):
    """Validates: Requirements 8.1, 8.2

    For any N pre-existing .bak_* files, after a rollback the total count of
    .bak_* files for the active file must be at most MAX_BACKUPS (5).
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir, user_data = _setup_dirs(base)
        strategies_dir = user_data / "strategies"

        # Create N pre-existing backup files with ascending timestamps
        for i in range(n):
            ts = f"20240101T{i:06d}"
            bak_path = strategies_dir / f"TestStrategy.json.bak_{ts}"
            bak_path.write_text(json.dumps({"backup": i}), encoding="utf-8")

        # Write the active params file and source
        active_path = _params_dest(user_data, "TestStrategy")
        write_json_file_atomic(active_path, {"current": "params"})
        write_json_file_atomic(run_dir / "params.json", {"restored": "params"})

        svc = RollbackService()
        svc.rollback(
            run_dir, user_data, "TestStrategy",
            restore_params=True, restore_config=False,
        )

        bak_files = list(strategies_dir.glob("TestStrategy.json.bak_*"))
        assert len(bak_files) <= RollbackService.MAX_BACKUPS, (
            f"Expected at most {RollbackService.MAX_BACKUPS} backups, got {len(bak_files)}"
        )


# ---------------------------------------------------------------------------
# Property 6: Backup pruning independence
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 6: Backup pruning independence
@given(
    params_count=st.integers(0, 10),
    config_count=st.integers(0, 10),
)
@settings(max_examples=50)
def test_backup_pruning_independence(params_count, config_count):
    """Validates: Requirements 8.4

    Pruning params backups must not affect config backup count, and vice versa.
    Both counts must independently be at most MAX_BACKUPS after rollback.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir, user_data = _setup_dirs(base)
        strategies_dir = user_data / "strategies"

        # Create pre-existing params backups
        for i in range(params_count):
            ts = f"20240101T{i:06d}"
            bak = strategies_dir / f"TestStrategy.json.bak_{ts}"
            bak.write_text(json.dumps({"p": i}), encoding="utf-8")

        # Create pre-existing config backups
        for i in range(config_count):
            ts = f"20240101T{i:06d}"
            bak = user_data / f"config.json.bak_{ts}"
            bak.write_text(json.dumps({"c": i}), encoding="utf-8")

        # Write active files and source files
        write_json_file_atomic(_params_dest(user_data, "TestStrategy"), {"current": "params"})
        write_json_file_atomic(_config_dest(user_data), {"current": "config"})
        write_json_file_atomic(run_dir / "params.json", {"restored": "params"})
        write_json_file_atomic(run_dir / "config.snapshot.json", {"restored": "config"})

        svc = RollbackService()
        svc.rollback(
            run_dir, user_data, "TestStrategy",
            restore_params=True, restore_config=True,
        )

        params_baks = list(strategies_dir.glob("TestStrategy.json.bak_*"))
        config_baks = list(user_data.glob("config.json.bak_*"))

        assert len(params_baks) <= RollbackService.MAX_BACKUPS, (
            f"Params backups exceeded MAX_BACKUPS: {len(params_baks)}"
        )
        assert len(config_baks) <= RollbackService.MAX_BACKUPS, (
            f"Config backups exceeded MAX_BACKUPS: {len(config_baks)}"
        )

        # Independence: params bak names and config bak names must not overlap
        params_bak_names = {p.name for p in params_baks}
        config_bak_names = {p.name for p in config_baks}
        assert params_bak_names.isdisjoint(config_bak_names), (
            "Params and config backup files should not overlap"
        )


# ---------------------------------------------------------------------------
# Property 7: Unchecked params scope leaves active params unchanged
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 7: Unchecked params scope leaves active params unchanged
@given(active_content=_dict_strategy)
@settings(max_examples=50)
def test_unchecked_params_leaves_active_unchanged(active_content):
    """Validates: Requirements 6.3

    When restore_params=False, the active params file must be byte-for-byte
    identical after the rollback as it was before.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir, user_data = _setup_dirs(base)

        # Write active params
        active_path = _params_dest(user_data, "TestStrategy")
        write_json_file_atomic(active_path, active_content)
        original_bytes = active_path.read_bytes()

        # Write both source files so rollback has something to do (restore_config=True)
        write_json_file_atomic(run_dir / "params.json", {"different": "content"})
        write_json_file_atomic(run_dir / "config.snapshot.json", {"config": "data"})

        svc = RollbackService()
        svc.rollback(
            run_dir, user_data, "TestStrategy",
            restore_params=False, restore_config=True,
        )

        assert active_path.read_bytes() == original_bytes, (
            "Active params file was modified despite restore_params=False"
        )


# ---------------------------------------------------------------------------
# Property 8: Unchecked config scope leaves active config unchanged
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 8: Unchecked config scope leaves active config unchanged
@given(active_content=_dict_strategy)
@settings(max_examples=50)
def test_unchecked_config_leaves_active_unchanged(active_content):
    """Validates: Requirements 6.4

    When restore_config=False, the active config file must be byte-for-byte
    identical after the rollback as it was before.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir, user_data = _setup_dirs(base)

        # Write active config
        active_config = _config_dest(user_data)
        write_json_file_atomic(active_config, active_content)
        original_bytes = active_config.read_bytes()

        # Write both source files so rollback has something to do (restore_params=True)
        write_json_file_atomic(run_dir / "params.json", {"restored": "params"})
        write_json_file_atomic(run_dir / "config.snapshot.json", {"different": "config"})

        svc = RollbackService()
        svc.rollback(
            run_dir, user_data, "TestStrategy",
            restore_params=True, restore_config=False,
        )

        assert active_config.read_bytes() == original_bytes, (
            "Active config file was modified despite restore_config=False"
        )


# ---------------------------------------------------------------------------
# Property 9: RollbackResult accuracy
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 9: RollbackResult accurately reflects what was restored
@given(
    restore_params=st.booleans(),
    restore_config=st.booleans(),
    run_id=_name_strategy,
    strategy_name=_name_strategy,
)
@settings(max_examples=50)
def test_rollback_result_accuracy(restore_params, restore_config, run_id, strategy_name):
    """Validates: Requirements 4.5

    The returned RollbackResult must accurately reflect which files were
    restored, the run ID, and the strategy name.
    """
    # Skip cases where both flags are False — service raises ValueError
    assume(restore_params or restore_config)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir, user_data = _setup_dirs(base, run_name=run_id)

        # Write both source files so the service can restore either
        write_json_file_atomic(run_dir / "params.json", {"param": "value"})
        write_json_file_atomic(run_dir / "config.snapshot.json", {"config": "value"})

        svc = RollbackService()
        result = svc.rollback(
            run_dir, user_data, strategy_name,
            restore_params=restore_params, restore_config=restore_config,
        )

        assert result.params_restored == restore_params, (
            f"Expected params_restored={restore_params}, got {result.params_restored}"
        )
        assert result.config_restored == restore_config, (
            f"Expected config_restored={restore_config}, got {result.config_restored}"
        )
        assert result.rolled_back_to == run_id, (
            f"Expected rolled_back_to='{run_id}', got '{result.rolled_back_to}'"
        )
        assert result.strategy_name == strategy_name, (
            f"Expected strategy_name='{strategy_name}', got '{result.strategy_name}'"
        )


# ---------------------------------------------------------------------------
# Helpers for log capture (app logger has propagate=False)
# ---------------------------------------------------------------------------

import contextlib

@contextlib.contextmanager
def _capture_rollback_logs():
    """Capture INFO+ records from the rollback service logger.

    The app logger (freqtrade_gui) has propagate=False, so pytest's caplog
    cannot intercept its records via the root logger. We attach a temporary
    MemoryHandler directly to the rollback logger for the duration of the
    context, then detach it.
    """
    rollback_logger = logging.getLogger("freqtrade_gui.services.rollback")
    handler = logging.handlers.MemoryHandler(capacity=1000, flushLevel=logging.CRITICAL)
    handler.setLevel(logging.DEBUG)
    rollback_logger.addHandler(handler)
    try:
        yield handler.buffer
    finally:
        rollback_logger.removeHandler(handler)
        handler.close()


# ---------------------------------------------------------------------------
# Property 10: Rollback info log contains strategy name and run ID
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 10: Rollback info log contains strategy name and run ID
@given(
    strategy_name=_name_strategy,
    run_id=_name_strategy,
)
@settings(max_examples=20)
def test_rollback_log_contains_strategy_and_run_id(strategy_name, run_id):
    """Validates: Requirements 7.1

    Initiating a rollback must produce at least one INFO-level log entry
    containing both the strategy name and the run ID as substrings.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir = base / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        user_data = base / "user_data"
        (user_data / "strategies").mkdir(parents=True, exist_ok=True)
        write_json_file_atomic(run_dir / "params.json", {"param": "value"})

        svc = RollbackService()
        with _capture_rollback_logs() as records:
            svc.rollback(
                run_dir, user_data, strategy_name,
                restore_params=True, restore_config=False,
            )

        info_records = [r for r in records if r.levelno >= logging.INFO]
        matching = [
            r for r in info_records
            if strategy_name in r.getMessage() and run_id in r.getMessage()
        ]
        assert len(matching) >= 1, (
            f"No INFO log record found containing both '{strategy_name}' and '{run_id}'. "
            f"Records: {[r.getMessage() for r in info_records]}"
        )


# ---------------------------------------------------------------------------
# Property 11: Restore log contains source and destination paths
# ---------------------------------------------------------------------------

# Feature: strategy-rollback, Property 11: Restore log contains source and destination paths
@given(strategy_name=_name_strategy)
@settings(max_examples=20)
def test_restore_log_contains_paths(strategy_name):
    """Validates: Requirements 7.3

    After a successful file restore, the service must emit at least one
    INFO-level log entry containing both the source path and destination path.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_dir = base / "run_20240315T143022_abc123"
        run_dir.mkdir(parents=True, exist_ok=True)
        user_data = base / "user_data"
        (user_data / "strategies").mkdir(parents=True, exist_ok=True)
        write_json_file_atomic(run_dir / "params.json", {"param": "value"})

        params_src = run_dir / "params.json"
        params_dest = user_data / "strategies" / f"{strategy_name}.json"

        svc = RollbackService()
        with _capture_rollback_logs() as records:
            svc.rollback(
                run_dir, user_data, strategy_name,
                restore_params=True, restore_config=False,
            )

        info_records = [r for r in records if r.levelno >= logging.INFO]
        matching = [
            r for r in info_records
            if str(params_src) in r.getMessage() and str(params_dest) in r.getMessage()
        ]
        assert len(matching) >= 1, (
            f"No INFO log record found containing both source '{params_src}' "
            f"and destination '{params_dest}'. "
            f"Records: {[r.getMessage() for r in info_records]}"
        )
