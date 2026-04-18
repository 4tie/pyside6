"""Test what hangs during import of the test file."""
import sys
print("Step 1: importing pytest")
import pytest
print("Step 2: importing PySide6")
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QGraphicsOpacityEffect
print("Step 3: importing QCore")
from PySide6.QtCore import QCoreApplication, QEvent, QPropertyAnimation, QEasingCurve
print("Step 4: importing hypothesis given")
from hypothesis import given
print("Step 5: importing hypothesis settings")
from hypothesis import settings as h_settings
print("Step 6: importing hypothesis strategies")
from hypothesis import strategies as st
print("All imports OK")
