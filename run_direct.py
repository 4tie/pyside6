"""Run pytest directly using pytest.main() to avoid subprocess hanging."""
import sys
import pytest

# Run the bug condition tests
result = pytest.main([
    'tests/ui/test_ui_rendering_bugs.py::test_bug1_stale_layout_children',
    'tests/ui/test_ui_rendering_bugs.py::test_bug1_opacity_effect_not_removed',
    '-v',
    '--tb=short',
    '--no-header',
])
print(f"\npytest.main() returned: {result}")
sys.exit(int(result))
