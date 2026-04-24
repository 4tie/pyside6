"""Preservation tests for strategy-lab-cleanup-and-baseline-fixes bugfix.

These tests verify that non-baseline flows remain unchanged after the fix.
They should PASS on both unfixed and fixed code.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from app.core.utils.app_logger import get_logger

_log = get_logger("tests.bugfix_preservation")


class TestPreservation_NonBaselineFlows:
    """Property 2: Preservation - Non-Baseline Flows Unchanged.
    
    **IMPORTANT**: Follow observation-first methodology.
    
    These tests verify that non-baseline functionality remains unchanged:
    - Regular loop iterations (non-baseline)
    - Manual backtest runs
    - Strategy Lab UI state management
    - ProcessService command execution for non-baseline commands
    
    These tests should PASS on both UNFIXED and FIXED code.
    """
    
    def test_loop_service_gate_methods_are_callable(self):
        """Test that gate runner methods exist and are callable.
        
        This verifies that the canonical (second) definitions are preserved
        and functional after removing duplicates.
        """
        from app.core.services.loop_service import LoopService
        from app.core.models.settings_models import AppSettings
        
        # Create service instance
        settings = AppSettings(
            python_executable=Path("/usr/bin/python3"),
            freqtrade_executable=Path("/usr/bin/freqtrade"),
            user_data_path=Path("/tmp/user_data"),  # Correct field name
            venv_path=Path("/tmp/venv"),
        )
        service = LoopService(settings)
        
        # Verify all gate runner methods exist and are callable
        assert hasattr(service, "_run_oos_gate"), "_run_oos_gate method missing"
        assert callable(service._run_oos_gate), "_run_oos_gate not callable"
        
        assert hasattr(service, "_run_walk_forward_gate"), "_run_walk_forward_gate method missing"
        assert callable(service._run_walk_forward_gate), "_run_walk_forward_gate not callable"
        
        assert hasattr(service, "_run_stress_gate"), "_run_stress_gate method missing"
        assert callable(service._run_stress_gate), "_run_stress_gate not callable"
        
        assert hasattr(service, "_run_consistency_gate"), "_run_consistency_gate method missing"
        assert callable(service._run_consistency_gate), "_run_consistency_gate not callable"
        
        _log.info("All gate runner methods are present and callable")
    
    def test_loop_page_state_machine_is_callable(self):
        """Test that _update_state_machine method exists and is callable.
        
        This verifies that the canonical (second) definition is preserved
        and functional after removing the duplicate.
        """
        from app.ui.pages.loop_page import LoopPage
        
        # Verify method exists and is callable
        assert hasattr(LoopPage, "_update_state_machine"), "_update_state_machine method missing"
        assert callable(getattr(LoopPage, "_update_state_machine")), "_update_state_machine not callable"
        
        _log.info("_update_state_machine method is present and callable")
    
    def test_process_service_execute_command_with_correct_params(self):
        """Test that ProcessService.execute_command works with correct parameter names.
        
        This verifies that the correct parameter names (working_directory, on_output, on_error)
        work correctly and will continue to work after the fix.
        """
        from app.core.services.process_service import ProcessService
        
        process_service = ProcessService()
        
        # Mock callbacks
        on_output_called = []
        on_error_called = []
        on_finished_called = []
        
        def on_output(line: str):
            on_output_called.append(line)
        
        def on_error(line: str):
            on_error_called.append(line)
        
        def on_finished(exit_code: int):
            on_finished_called.append(exit_code)
        
        # This should work with correct parameter names
        try:
            process_service.execute_command(
                ["echo", "test"],
                working_directory=None,  # Correct parameter name
                on_output=on_output,     # Correct parameter name
                on_error=on_error,       # Correct parameter name
                on_finished=on_finished,
            )
            _log.info("execute_command accepted correct parameter names")
        except TypeError as e:
            pytest.fail(f"execute_command rejected correct parameter names: {e}")
    
    def test_create_backtest_command_with_supported_params(self, tmp_path):
        """Test that build_backtest_command works with supported parameters.
        
        This verifies that the function works correctly with its actual signature
        and will continue to work after the fix.
        """
        from app.core.freqtrade.runners.backtest_runner import create_backtest_command
        from app.core.models.settings_models import AppSettings
        import json
        
        # Create temporary user_data directory structure
        user_data = tmp_path / "user_data"
        user_data.mkdir()
        strategies_dir = user_data / "strategies"
        strategies_dir.mkdir()
        (user_data / "data").mkdir()
        
        # Create a dummy strategy file
        strategy_file = strategies_dir / "TestStrategy.py"
        strategy_file.write_text("# Dummy strategy\nclass TestStrategy:\n    pass\n")
        
        # Create a dummy config file
        config_file = user_data / "config.json"
        config_file.write_text(json.dumps({"exchange": {"name": "binance"}}))
        
        settings = AppSettings(
            python_executable=Path("/usr/bin/python3"),
            freqtrade_executable=Path("/usr/bin/freqtrade"),
            user_data_path=user_data,  # Use temp directory
            venv_path=Path("/tmp/venv"),
        )
        
        # This should work with supported parameters only
        try:
            cmd = create_backtest_command(
                settings=settings,
                strategy_name="TestStrategy",
                timeframe="5m",
                timerange="20230101-20230201",
                pairs=["BTC/USDT"],
                # NOT passing unsupported kwargs
            )
            
            # Verify the command was built successfully
            assert cmd is not None, "create_backtest_command returned None"
            assert hasattr(cmd, "as_list"), "Command missing as_list method"
            assert hasattr(cmd, "export_dir"), "Command missing export_dir attribute"
            assert hasattr(cmd, "config_file"), "Command missing config_file attribute"
            assert hasattr(cmd, "strategy_file"), "Command missing strategy_file attribute"
            
            _log.info("create_backtest_command works with supported parameters")
        except TypeError as e:
            pytest.fail(f"create_backtest_command failed with supported parameters: {e}")
    
    def test_gate_result_building_methods_exist(self):
        """Test that gate result building helper methods exist.
        
        These are the refactored helper methods that the canonical gate runners use.
        They should exist and be callable.
        """
        from app.core.services.loop_service import LoopService
        from app.core.models.settings_models import AppSettings
        
        settings = AppSettings(
            python_executable=Path("/usr/bin/python3"),
            freqtrade_executable=Path("/usr/bin/freqtrade"),
            user_data_path=Path("/tmp/user_data"),  # Correct field name
            venv_path=Path("/tmp/venv"),
        )
        service = LoopService(settings)
        
        # Verify helper methods exist
        assert hasattr(service, "build_in_sample_gate_result"), "build_in_sample_gate_result missing"
        assert hasattr(service, "build_oos_gate_result"), "build_oos_gate_result missing"
        assert hasattr(service, "build_walk_forward_gate_result"), "build_walk_forward_gate_result missing"
        assert hasattr(service, "build_stress_gate_result"), "build_stress_gate_result missing"
        assert hasattr(service, "build_consistency_gate_result"), "build_consistency_gate_result missing"
        
        _log.info("All gate result building helper methods are present")
    
    def test_timerange_computation_methods_exist(self):
        """Test that timerange computation helper methods exist.
        
        These are the refactored helper methods that the canonical gate runners use.
        They should exist and be callable.
        """
        from app.core.services.loop_service import LoopService
        from app.core.models.settings_models import AppSettings
        
        settings = AppSettings(
            python_executable=Path("/usr/bin/python3"),
            freqtrade_executable=Path("/usr/bin/freqtrade"),
            user_data_path=Path("/tmp/user_data"),  # Correct field name
            venv_path=Path("/tmp/venv"),
        )
        service = LoopService(settings)
        
        # Verify helper methods exist
        assert hasattr(service, "compute_in_sample_timerange"), "compute_in_sample_timerange missing"
        assert hasattr(service, "compute_oos_timerange"), "compute_oos_timerange missing"
        assert hasattr(service, "compute_walk_forward_timeranges"), "compute_walk_forward_timeranges missing"
        
        _log.info("All timerange computation helper methods are present")
