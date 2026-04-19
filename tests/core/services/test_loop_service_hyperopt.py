"""
test_loop_service_hyperopt.py — Unit tests for hyperopt mode in LoopService:
- _parse_hyperopt_result() extracts best params from a sample .fthypt file
- Non-zero exit code records error and does not stop the loop
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.services.loop_service import LoopService
from app.core.services.improve_service import ImproveService
from app.core.models.loop_models import LoopConfig, LoopIteration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service() -> LoopService:
    return LoopService(MagicMock(spec=ImproveService))


def _iteration() -> LoopIteration:
    return LoopIteration(
        iteration_number=1,
        params_before={"stoploss": -0.10},
        params_after={"stoploss": -0.10},
        changes_summary=[],
        sandbox_path=Path("."),
    )


def _write_fthypt(directory: Path, entries: list) -> Path:
    """Write a .fthypt JSON-lines file with the given entries."""
    fthypt_path = directory / "results.fthypt"
    lines = [json.dumps(e) for e in entries]
    fthypt_path.write_text("\n".join(lines), encoding="utf-8")
    return fthypt_path


# ---------------------------------------------------------------------------
# _parse_hyperopt_result
# ---------------------------------------------------------------------------

class TestParseHyperoptResult:
    def test_extracts_best_params_from_fthypt(self, tmp_path):
        """Best params must be extracted from the entry with the lowest loss."""
        entries = [
            {"loss": 0.5, "params_dict": {"stoploss": -0.08, "max_open_trades": 3}},
            {"loss": 0.3, "params_dict": {"stoploss": -0.06, "max_open_trades": 4}},  # best
            {"loss": 0.7, "params_dict": {"stoploss": -0.12, "max_open_trades": 2}},
        ]
        _write_fthypt(tmp_path, entries)
        svc = _make_service()
        result = svc._parse_hyperopt_result(tmp_path)
        assert result["stoploss"] == -0.06
        assert result["max_open_trades"] == 4

    def test_raises_file_not_found_when_no_fthypt(self, tmp_path):
        svc = _make_service()
        with pytest.raises(FileNotFoundError):
            svc._parse_hyperopt_result(tmp_path)

    def test_raises_value_error_when_no_valid_entries(self, tmp_path):
        """If no valid entries exist, ValueError must be raised."""
        fthypt_path = tmp_path / "results.fthypt"
        fthypt_path.write_text("not json\n{}\n", encoding="utf-8")
        svc = _make_service()
        with pytest.raises(ValueError):
            svc._parse_hyperopt_result(tmp_path)

    def test_skips_malformed_lines(self, tmp_path):
        """Malformed JSON lines must be skipped; valid entries must still be parsed."""
        entries_text = (
            "not json\n"
            + json.dumps({"loss": 0.4, "params_dict": {"stoploss": -0.09}}) + "\n"
            + "also not json\n"
        )
        fthypt_path = tmp_path / "results.fthypt"
        fthypt_path.write_text(entries_text, encoding="utf-8")
        svc = _make_service()
        result = svc._parse_hyperopt_result(tmp_path)
        assert result["stoploss"] == -0.09

    def test_uses_params_key_as_fallback(self, tmp_path):
        """If params_dict is absent, fall back to 'params' key."""
        entries = [
            {"loss": 0.4, "params": {"stoploss": -0.07}},
        ]
        _write_fthypt(tmp_path, entries)
        svc = _make_service()
        result = svc._parse_hyperopt_result(tmp_path)
        assert result["stoploss"] == -0.07


# ---------------------------------------------------------------------------
# record_hyperopt_candidate — non-zero exit code
# ---------------------------------------------------------------------------

class TestRecordHyperoptCandidate:
    def test_non_zero_exit_records_error_and_does_not_stop_loop(self, tmp_path):
        """Non-zero exit code must record error status but NOT stop the loop."""
        svc = _make_service()
        # Start the loop so _result is initialised
        from app.core.backtests.results_models import BacktestSummary
        config = LoopConfig(strategy="TestStrategy")
        svc.start(config, {"stoploss": -0.10})

        iteration = _iteration()
        result = svc.record_hyperopt_candidate(iteration, tmp_path, exit_code=1)

        assert result is None
        assert iteration.status == "error"
        assert "1" in iteration.error_message
        # Loop should still be running (not stopped by error)
        assert svc.is_running is True

    def test_zero_exit_with_valid_fthypt_returns_params(self, tmp_path):
        """Zero exit code with valid .fthypt must return best params dict."""
        entries = [
            {"loss": 0.3, "params_dict": {"stoploss": -0.05, "max_open_trades": 5}},
        ]
        _write_fthypt(tmp_path, entries)

        svc = _make_service()
        config = LoopConfig(strategy="TestStrategy")
        svc.start(config, {"stoploss": -0.10, "max_open_trades": 3})

        iteration = _iteration()
        result = svc.record_hyperopt_candidate(iteration, tmp_path, exit_code=0)

        assert result is not None
        assert result["stoploss"] == -0.05
        assert result["max_open_trades"] == 5

    def test_zero_exit_with_missing_fthypt_records_error(self, tmp_path):
        """Zero exit code but missing .fthypt must record error and not stop loop."""
        svc = _make_service()
        config = LoopConfig(strategy="TestStrategy")
        svc.start(config, {"stoploss": -0.10})

        iteration = _iteration()
        result = svc.record_hyperopt_candidate(iteration, tmp_path, exit_code=0)

        assert result is None
        assert iteration.status == "error"
        assert svc.is_running is True
