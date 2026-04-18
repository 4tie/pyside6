"""Run pytest directly using pytest.main() to avoid subprocess hanging."""
import sys
import io

# Redirect stdout/stderr to a file
with open('T:/ae/pyside6/pytest_output.txt', 'w') as f:
    import pytest
    
    # Run the bug condition tests
    result = pytest.main([
        'tests/ui/test_ui_rendering_bugs.py::test_bug1_stale_layout_children',
        'tests/ui/test_ui_rendering_bugs.py::test_bug1_opacity_effect_not_removed',
        '-v',
        '--tb=short',
        '--no-header',
    ], plugins=[])
    
    f.write(f"\npytest.main() returned: {result}\n")

print(f"Done, exit code: {result}")
sys.exit(int(result))
