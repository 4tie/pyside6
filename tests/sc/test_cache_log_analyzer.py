"""
Unit tests for sc/cache_log_analyzer.py
"""
import os
import sys
import io
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure sc/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import sc.cache_log_analyzer as cla


# ---------------------------------------------------------------------------
# 5.1  clean_cache
# ---------------------------------------------------------------------------

class TestCleanCache:
    def test_empty_dir_returns_empty_list(self, tmp_path):
        result = cla.clean_cache(str(tmp_path))
        assert result == []

    def test_pycache_dir_deleted_and_reported(self, tmp_path):
        pycache = tmp_path / "pkg" / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "mod.cpython-311.pyc").write_text("bytecode")

        result = cla.clean_cache(str(tmp_path))

        assert str(pycache) in result
        assert not pycache.exists()

    def test_pyc_file_deleted_and_reported(self, tmp_path):
        pyc = tmp_path / "module.pyc"
        pyc.write_text("bytecode")

        result = cla.clean_cache(str(tmp_path))

        assert str(pyc) in result
        assert not pyc.exists()

    def test_both_pycache_and_pyc_deleted(self, tmp_path):
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        pyc = tmp_path / "foo.pyc"
        pyc.write_text("x")

        result = cla.clean_cache(str(tmp_path))

        assert len(result) == 2
        assert not pycache.exists()
        assert not pyc.exists()

    def test_venv_paths_not_deleted(self, tmp_path):
        venv_pycache = tmp_path / ".venv" / "lib" / "__pycache__"
        venv_pycache.mkdir(parents=True)
        venv_pyc = tmp_path / ".venv" / "lib" / "mod.pyc"
        venv_pyc.write_text("x")

        result = cla.clean_cache(str(tmp_path))

        assert result == []
        assert venv_pycache.exists()
        assert venv_pyc.exists()

    def test_git_paths_not_deleted(self, tmp_path):
        git_pycache = tmp_path / ".git" / "hooks" / "__pycache__"
        git_pycache.mkdir(parents=True)
        git_pyc = tmp_path / ".git" / "hooks" / "pre-commit.pyc"
        git_pyc.write_text("x")

        result = cla.clean_cache(str(tmp_path))

        assert result == []
        assert git_pycache.exists()
        assert git_pyc.exists()

    def test_nested_pycache_outside_exclusions_deleted(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "__pycache__"
        nested.mkdir(parents=True)

        result = cla.clean_cache(str(tmp_path))

        assert str(nested) in result
        assert not nested.exists()


# ---------------------------------------------------------------------------
# 5.2  scan_logs
# ---------------------------------------------------------------------------

class TestScanLogs:
    def test_only_debug_lines_returns_empty(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("DEBUG starting up\nDEBUG loaded config\n")

        result = cla.scan_logs(str(tmp_path), cla.ANOMALY_KEYWORDS)

        assert result == []

    def test_error_line_returned(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("INFO ok\nERROR something broke\nDEBUG done\n")

        result = cla.scan_logs(str(tmp_path), cla.ANOMALY_KEYWORDS)

        assert any("ERROR something broke" in line for line in result)

    def test_critical_line_returned(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("CRITICAL disk full\n")

        result = cla.scan_logs(str(tmp_path), cla.ANOMALY_KEYWORDS)

        assert any("CRITICAL disk full" in line for line in result)

    def test_warning_line_returned(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("WARNING low memory\n")

        result = cla.scan_logs(str(tmp_path), cla.ANOMALY_KEYWORDS)

        assert any("WARNING low memory" in line for line in result)

    def test_keyword_match_case_insensitive(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("INFO process FAILED with exit code 1\n")

        result = cla.scan_logs(str(tmp_path), ["failed"])

        assert len(result) == 1
        assert "FAILED" in result[0]

    def test_keyword_match_lowercase_in_line(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("INFO connection refused by server\n")

        result = cla.scan_logs(str(tmp_path), ["connection refused"])

        assert len(result) == 1

    def test_unreadable_file_prints_warning_and_continues(self, tmp_path, capsys):
        good_log = tmp_path / "good.log"
        good_log.write_text("ERROR real error\n")

        bad_log = tmp_path / "bad.log"
        bad_log.write_text("ERROR should not appear\n")

        with patch("builtins.open", side_effect=lambda path, **kw: (
            open.__wrapped__(path, **kw) if "good.log" in str(path)
            else (_ for _ in ()).throw(OSError("permission denied"))
        )):
            pass  # just verify the logic below works via os.scandir mock

        # Simpler approach: mock open to raise for bad.log
        original_open = open

        def selective_open(path, **kwargs):
            if "bad.log" in str(path):
                raise OSError("permission denied")
            return original_open(path, **kwargs)

        with patch("builtins.open", side_effect=selective_open):
            result = cla.scan_logs(str(tmp_path), [])

        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert any("ERROR real error" in line for line in result)

    def test_no_matching_lines_returns_empty(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("INFO all good\nDEBUG verbose\n")

        result = cla.scan_logs(str(tmp_path), [])

        assert result == []


# ---------------------------------------------------------------------------
# 5.3  analyze_with_ollama
# ---------------------------------------------------------------------------

class TestAnalyzeWithOllama:
    def test_200_response_returns_content(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Here is the analysis."}
        }

        with patch("requests.post", return_value=mock_response):
            result = cla.analyze_with_ollama(
                ["ERROR foo"], "http://localhost:11434", "llama3"
            )

        assert result == "Here is the analysis."

    def test_connection_error_returns_none(self):
        with patch("requests.post", side_effect=cla.requests.exceptions.ConnectionError("refused")):
            result = cla.analyze_with_ollama(
                ["ERROR foo"], "http://localhost:11434", "llama3"
            )

        assert result is None

    def test_500_response_returns_none(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("requests.post", return_value=mock_response):
            result = cla.analyze_with_ollama(
                ["ERROR foo"], "http://localhost:11434", "llama3"
            )

        assert result is None

    def test_connection_error_does_not_raise(self):
        with patch("requests.post", side_effect=cla.requests.exceptions.ConnectionError("x")):
            try:
                cla.analyze_with_ollama(["line"], "http://localhost:11434", "llama3")
            except Exception as exc:
                pytest.fail(f"Unexpected exception raised: {exc}")

    def test_500_does_not_raise(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "err"

        with patch("requests.post", return_value=mock_response):
            try:
                cla.analyze_with_ollama(["line"], "http://localhost:11434", "llama3")
            except Exception as exc:
                pytest.fail(f"Unexpected exception raised: {exc}")


# ---------------------------------------------------------------------------
# 5.4  write_report
# ---------------------------------------------------------------------------

class TestWriteReport:
    def test_successful_write_returns_true(self, tmp_path):
        report_path = str(tmp_path / "reports" / "report.md")
        result = cla.write_report("Some analysis content.", report_path)
        assert result is True

    def test_file_contains_header(self, tmp_path):
        report_path = str(tmp_path / "report.md")
        cla.write_report("Content here.", report_path)
        text = Path(report_path).read_text(encoding="utf-8")
        assert "# App Event Analysis Report" in text

    def test_file_contains_content(self, tmp_path):
        report_path = str(tmp_path / "report.md")
        cla.write_report("My analysis result.", report_path)
        text = Path(report_path).read_text(encoding="utf-8")
        assert "My analysis result." in text

    def test_oserror_returns_false(self, tmp_path):
        report_path = str(tmp_path / "report.md")
        with patch("builtins.open", side_effect=OSError("permission denied")):
            result = cla.write_report("content", report_path)
        assert result is False

    def test_oserror_does_not_raise(self, tmp_path):
        report_path = str(tmp_path / "report.md")
        with patch("builtins.open", side_effect=OSError("permission denied")):
            try:
                cla.write_report("content", report_path)
            except Exception as exc:
                pytest.fail(f"Unexpected exception raised: {exc}")


# ---------------------------------------------------------------------------
# 5.5  Phase ordering
# ---------------------------------------------------------------------------

class TestPhaseOrdering:
    def test_phase_headers_appear_in_order(self, tmp_path, capsys):
        with (
            patch.object(cla, "clean_cache", return_value=[]),
            patch.object(cla, "scan_logs", return_value=[]),
            patch("os.getcwd", return_value=str(tmp_path)),
            patch("os.path.isdir", return_value=True),
        ):
            cla.main()

        captured = capsys.readouterr()
        phase1_pos = captured.out.find("Phase 1")
        phase2_pos = captured.out.find("Phase 2")

        assert phase1_pos != -1, "Phase 1 header not found"
        assert phase2_pos != -1, "Phase 2 header not found"
        assert phase1_pos < phase2_pos, "Phase 1 must appear before Phase 2"

    def test_phase3_header_appears_after_phase2_when_events_exist(self, tmp_path, capsys):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "analysis"}
        }

        with (
            patch.object(cla, "clean_cache", return_value=[]),
            patch.object(cla, "scan_logs", return_value=["ERROR something"]),
            patch("os.getcwd", return_value=str(tmp_path)),
            patch("os.path.isdir", return_value=True),
            patch("requests.post", return_value=mock_response),
            patch.object(cla, "write_report", return_value=True),
        ):
            cla.main()

        captured = capsys.readouterr()
        phase2_pos = captured.out.find("Phase 2")
        phase3_pos = captured.out.find("Phase 3")

        assert phase2_pos != -1
        assert phase3_pos != -1
        assert phase2_pos < phase3_pos
