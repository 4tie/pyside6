"""
Run the bug condition tests using pytest.main() directly.
This avoids the subprocess hanging issue on Windows.
"""
import sys
import os

# Change to the project directory
os.chdir('T:/ae/pyside6')

import pytest

result = pytest.main([
    'tests/ui/test_ui_rendering_bugs.py::test_bug1_stale_layout_children',
    'tests/ui/test_ui_rendering_bugs.py::test_bug1_opacity_effect_not_removed',
    '-v',
    '--tb=short',
    '--no-header',
    '-p', 'no:cacheprovider',
])
print(f"\npytest.main() returned: {result}")
sys.exit(int(result))
