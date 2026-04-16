"""
Unit tests for strategy_tools.py.

Covers:
  - read_strategy_code with a missing file returns an error
  - read_strategy_code truncates files larger than 50 KB
  - list_strategies returns only .py filenames (without extension)
  - list_strategies with no user_data_path returns an error
"""
import pytest

from app.core.ai.tools.strategy_tools import list_strategies, read_strategy_code


def _make_settings(tmp_path):
    """Return a minimal settings-like object with user_data_path set."""
    return type("S", (), {"user_data_path": str(tmp_path)})()


# ---------------------------------------------------------------------------
# read_strategy_code
# ---------------------------------------------------------------------------

def test_read_strategy_code_missing_file(tmp_path):
    settings = _make_settings(tmp_path)
    result = read_strategy_code("NonExistent", settings)
    assert result.get("error") == "Strategy file not found: NonExistent"


def test_read_strategy_code_truncates_large_file(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    strategy_file = strategies_dir / "BigStrategy.py"
    # Write slightly more than 50 KB
    strategy_file.write_bytes(b"x" * (50 * 1024 + 512))

    settings = _make_settings(tmp_path)
    result = read_strategy_code("BigStrategy", settings)

    assert "error" not in result
    code = result["code"]
    assert "[Note: file truncated at 50 KB]" in code
    assert len(code) <= 50 * 1024 + 100


# ---------------------------------------------------------------------------
# list_strategies
# ---------------------------------------------------------------------------

def test_list_strategies_returns_py_filenames(tmp_path):
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir()
    (strategies_dir / "MyStrategy.py").write_text("# strategy")
    (strategies_dir / "OtherStrategy.py").write_text("# strategy")
    (strategies_dir / "not_a_strategy.txt").write_text("ignored")

    settings = _make_settings(tmp_path)
    result = list_strategies(settings)

    assert "error" not in result
    assert result["strategies"] == ["MyStrategy", "OtherStrategy"]


def test_list_strategies_no_user_data_path():
    result = list_strategies(settings=None)
    assert result.get("error") == "user_data_path not configured"
