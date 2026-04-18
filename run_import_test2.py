"""Test what hangs during import of the test file."""
import sys
print("Step 1: importing hypothesis first")
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st
print("Step 2: importing pytest")
import pytest
print("Step 3: importing PySide6")
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QGraphicsOpacityEffect
print("Step 4: importing QCore")
from PySide6.QtCore import QCoreApplication, QEvent, QPropertyAnimation, QEasingCurve
print("All imports OK")
