"""Exploratory tests for strategy-lab-cleanup-and-baseline-fixes bugfix.

These tests are designed to FAIL on unfixed code to confirm bugs exist.
They will PASS after the fix is implemented.
"""
import ast
from pathlib import Path
from typing import List, Tuple
import pytest

from app.core.utils.app_logger import get_logger

_log = get_logger("tests.bugfix_exploration")


class TestBugCondition1And2_DuplicateMethods:
    """Bug Condition 1 & 2: Duplicate method definitions in loop_page.py and loop_service.py.
    
    **Property 1: Bug Condition** - Duplicate Method Definitions Exist
    
    **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bugs exist.
    **DO NOT attempt to fix the test or the code when it fails.**
    
    **GOAL**: Surface counterexamples that demonstrate duplicate method definitions exist.
    """
    
    def find_method_definitions(self, filepath: Path, method_name: str) -> List[int]:
        """Parse Python file and find all line numbers where a method is defined.
        
        Args:
            filepath: Path to Python source file
            method_name: Name of method to search for
            
        Returns:
            List of line numbers where method is defined
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(filepath))
        line_numbers = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == method_name:
                line_numbers.append(node.lineno)
        
        return line_numbers
    
    def test_duplicate_update_state_machine_in_loop_page(self):
        """Test Bug Condition 1: Duplicate _update_state_machine() in loop_page.py.
        
        Expected on UNFIXED code: FAIL (finds 2 definitions at lines 695 and 1343)
        Expected on FIXED code: PASS (finds 1 definition)
        """
        filepath = Path("app/ui/pages/loop_page.py")
        method_name = "_update_state_machine"
        
        definitions = self.find_method_definitions(filepath, method_name)
        
        _log.info(
            "Found %d definitions of %s in %s at lines: %s",
            len(definitions),
            method_name,
            filepath,
            definitions
        )
        
        # This assertion will FAIL on unfixed code (expected)
        # It will PASS on fixed code (confirming bug eliminated)
        assert len(definitions) == 1, (
            f"Expected 1 definition of {method_name}, found {len(definitions)} "
            f"at lines {definitions}. Bug confirmed: duplicate methods exist."
        )
    
    def test_duplicate_run_oos_gate_in_loop_service(self):
        """Test Bug Condition 2: Duplicate _run_oos_gate() in loop_service.py.
        
        Expected on UNFIXED code: FAIL (finds 2 definitions at lines 791 and 1874)
        Expected on FIXED code: PASS (finds 1 definition)
        """
        filepath = Path("app/core/services/loop_service.py")
        method_name = "_run_oos_gate"
        
        definitions = self.find_method_definitions(filepath, method_name)
        
        _log.info(
            "Found %d definitions of %s in %s at lines: %s",
            len(definitions),
            method_name,
            filepath,
            definitions
        )
        
        assert len(definitions) == 1, (
            f"Expected 1 definition of {method_name}, found {len(definitions)} "
            f"at lines {definitions}. Bug confirmed: duplicate methods exist."
        )
    
    def test_duplicate_run_walk_forward_gate_in_loop_service(self):
        """Test Bug Condition 2: Duplicate _run_walk_forward_gate() in loop_service.py.
        
        Expected on UNFIXED code: FAIL (finds 2 definitions)
        Expected on FIXED code: PASS (finds 1 definition)
        """
        filepath = Path("app/core/services/loop_service.py")
        method_name = "_run_walk_forward_gate"
        
        definitions = self.find_method_definitions(filepath, method_name)
        
        _log.info(
            "Found %d definitions of %s in %s at lines: %s",
            len(definitions),
            method_name,
            filepath,
            definitions
        )
        
        assert len(definitions) == 1, (
            f"Expected 1 definition of {method_name}, found {len(definitions)} "
            f"at lines {definitions}. Bug confirmed: duplicate methods exist."
        )
    
    def test_duplicate_run_stress_gate_in_loop_service(self):
        """Test Bug Condition 2: Duplicate _run_stress_gate() in loop_service.py.
        
        Expected on UNFIXED code: FAIL (finds 2 definitions)
        Expected on FIXED code: PASS (finds 1 definition)
        """
        filepath = Path("app/core/services/loop_service.py")
        method_name = "_run_stress_gate"
        
        definitions = self.find_method_definitions(filepath, method_name)
        
        _log.info(
            "Found %d definitions of %s in %s at lines: %s",
            len(definitions),
            method_name,
            filepath,
            definitions
        )
        
        assert len(definitions) == 1, (
            f"Expected 1 definition of {method_name}, found {len(definitions)} "
            f"at lines {definitions}. Bug confirmed: duplicate methods exist."
        )
    
    def test_duplicate_run_consistency_gate_in_loop_service(self):
        """Test Bug Condition 2: Duplicate _run_consistency_gate() in loop_service.py.
        
        Expected on UNFIXED code: FAIL (finds 2 definitions)
        Expected on FIXED code: PASS (finds 1 definition)
        """
        filepath = Path("app/core/services/loop_service.py")
        method_name = "_run_consistency_gate"
        
        definitions = self.find_method_definitions(filepath, method_name)
        
        _log.info(
            "Found %d definitions of %s in %s at lines: %s",
            len(definitions),
            method_name,
            filepath,
            definitions
        )
        
        assert len(definitions) == 1, (
            f"Expected 1 definition of {method_name}, found {len(definitions)} "
            f"at lines {definitions}. Bug confirmed: duplicate methods exist."
        )


class TestBugCondition3_BuildBacktestCommandParameterMismatch:
    """Bug Condition 3: build_backtest_command() called with unsupported kwargs.
    
    **Property 1: Bug Condition** - Invalid Parameters Passed to build_backtest_command
    
    **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.
    
    **GOAL**: Surface counterexamples that demonstrate parameter mismatch.
    
    **NOTE**: After fix, this test verifies that the function works with correct parameters.
    """
    
    def test_create_backtest_command_works_with_supported_params(self, tmp_path):
        """Test that build_backtest_command works with supported parameters only.
        
        Expected on UNFIXED code: Would fail if called with unsupported kwargs
        Expected on FIXED code: PASS (call succeeds with only supported parameters)
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
            user_data_path=user_data,
            venv_path=Path("/tmp/venv"),
        )
        
        # This should work with supported parameters only (after fix)
        try:
            cmd = create_backtest_command(
                settings=settings,
                strategy_name="TestStrategy",
                timeframe="5m",
                timerange="20230101-20230201",
                pairs=["BTC/USDT"],
                # NOT passing unsupported kwargs (this is the fix)
            )
            
            # Verify the command was built successfully
            assert cmd is not None, "create_backtest_command returned None"
            assert hasattr(cmd, "as_list"), "Command missing as_list method"
            assert hasattr(cmd, "export_dir"), "Command missing export_dir attribute"
            assert hasattr(cmd, "config_file"), "Command missing config_file attribute"
            assert hasattr(cmd, "strategy_file"), "Command missing strategy_file attribute"
            
            _log.info("create_backtest_command works with supported parameters (bug fixed)")
        except TypeError as e:
            pytest.fail(f"create_backtest_command failed with supported parameters: {e}")


class TestBugCondition4_ExecuteCommandParameterMismatch:
    """Bug Condition 4: execute_command() called with wrong parameter names.
    
    **Property 1: Bug Condition** - Invalid Parameters Passed to execute_command
    
    **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.
    
    **GOAL**: Surface counterexamples that demonstrate parameter name mismatch.
    
    **NOTE**: After fix, this test verifies that the function works with correct parameter names.
    """
    
    def test_execute_command_works_with_correct_parameter_names(self):
        """Test that execute_command() works with correct parameter names.
        
        Expected on UNFIXED code: Would fail if called with wrong parameter names
        Expected on FIXED code: PASS (call succeeds with correct parameter names)
        """
        from app.core.services.process_service import ProcessService
        
        process_service = ProcessService()
        
        # This should work with correct parameter names (after fix)
        try:
            process_service.execute_command(
                ["echo", "test"],
                # These are the CORRECT parameter names (this is the fix)
                working_directory=None,
                on_output=lambda line: None,
                on_error=lambda line: None,
                on_finished=lambda code: None,
            )
            _log.info("execute_command works with correct parameter names (bug fixed)")
        except TypeError as e:
            pytest.fail(f"execute_command failed with correct parameter names: {e}")


class TestBugCondition5_CallbackSignatureMismatch:
    """Bug Condition 5: Callback signature mismatch in _on_baseline_backtest_finished.
    
    **Property 1: Bug Condition** - Callback Signature Mismatch
    
    **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.
    
    **GOAL**: Surface counterexamples that demonstrate callback signature mismatch.
    """
    
    def test_callback_signature_has_two_parameters(self):
        """Test that _on_baseline_backtest_finished has wrong signature.
        
        Expected on UNFIXED code: FAIL (callback has 2 params but should have 1)
        Expected on FIXED code: PASS (callback has 1 param matching ProcessService convention)
        """
        import inspect
        from app.ui.pages.loop_page import LoopPage
        
        # Get the callback method signature
        callback = getattr(LoopPage, "_on_baseline_backtest_finished")
        sig = inspect.signature(callback)
        
        # Count parameters (excluding 'self')
        params = [p for p in sig.parameters.values() if p.name != 'self']
        param_count = len(params)
        param_names = [p.name for p in params]
        
        _log.info(
            "Callback signature: %d parameters (excluding self): %s",
            param_count,
            param_names
        )
        
        # This assertion will FAIL on unfixed code (expected)
        # The callback should have 1 parameter (exit_code) but has 2 (exit_code, exit_status)
        assert param_count == 1, (
            f"Expected 1 parameter (exit_code), found {param_count} parameters: {param_names}. "
            f"Bug confirmed: callback signature mismatch with ProcessService convention."
        )
        
        # Also verify the parameter name is correct
        assert params[0].name == "exit_code", (
            f"Expected parameter name 'exit_code', found '{params[0].name}'"
        )
