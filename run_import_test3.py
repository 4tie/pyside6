"""Test what hangs during import of the test file."""
import sys
print("Step 1: importing hypothesis")
import hypothesis
print("Step 2: hypothesis imported OK")
print("Step 3: importing given")
from hypothesis import given
print("Step 4: given imported OK")
