"""
Unit tests for ImproveService.resolve_candidate_artifact().

Tests:
  - Exactly one zip → returns its path
  - Zero zips → raises FileNotFoundError with export_dir in message
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.services.improve_service import ImproveService


def _make_service() -> ImproveService:
    """Create an ImproveService with mocked dependencies."""
    settings_service = MagicMock()
    backtest_service = MagicMock()
    return ImproveService(settings_service, backtest_service)


class TestResolveCandidateArtifact:
    """Unit tests for ImproveService.resolve_candidate_artifact."""

    def test_exactly_one_zip_returns_path(self, tmp_path: Path) -> None:
        """Returns the path when exactly one .zip file is found."""
        export_dir = tmp_path / "backtest_output"
        export_dir.mkdir()
        zip_file = export_dir / "result.zip"
        zip_file.write_bytes(b"fake zip content")

        service = _make_service()
        result = service.resolve_candidate_artifact(export_dir)

        assert result == zip_file

    def test_zero_zips_raises_file_not_found(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError with export_dir in message when no zip found."""
        export_dir = tmp_path / "backtest_output"
        export_dir.mkdir()
        # No zip files

        service = _make_service()
        with pytest.raises(FileNotFoundError) as exc_info:
            service.resolve_candidate_artifact(export_dir)

        assert str(export_dir) in str(exc_info.value), (
            f"Expected export_dir path '{export_dir}' in error message, "
            f"got: '{exc_info.value}'"
        )

    def test_multiple_zips_returns_most_recent(self, tmp_path: Path) -> None:
        """Returns the most recently modified zip when multiple are found."""
        import time
        export_dir = tmp_path / "backtest_output"
        export_dir.mkdir()

        zip1 = export_dir / "result1.zip"
        zip1.write_bytes(b"zip1")
        time.sleep(0.01)  # ensure different mtime
        zip2 = export_dir / "result2.zip"
        zip2.write_bytes(b"zip2")

        service = _make_service()
        result = service.resolve_candidate_artifact(export_dir)

        assert result == zip2

    def test_non_zip_files_ignored(self, tmp_path: Path) -> None:
        """Non-.zip files in export_dir are ignored."""
        export_dir = tmp_path / "backtest_output"
        export_dir.mkdir()
        (export_dir / "result.json").write_text("{}")
        (export_dir / "result.txt").write_text("log")
        zip_file = export_dir / "result.zip"
        zip_file.write_bytes(b"fake zip")

        service = _make_service()
        result = service.resolve_candidate_artifact(export_dir)

        assert result == zip_file

    def test_empty_directory_raises_file_not_found(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for an empty directory."""
        export_dir = tmp_path / "empty_output"
        export_dir.mkdir()

        service = _make_service()
        with pytest.raises(FileNotFoundError) as exc_info:
            service.resolve_candidate_artifact(export_dir)

        assert str(export_dir) in str(exc_info.value)
