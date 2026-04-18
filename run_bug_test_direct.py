"""
Run the bug condition tests directly without pytest to verify they fail on unfixed code.
This avoids the pytest+hypothesis deadlock issue on Windows.
"""
import sys

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import QCoreApplication, QPropertyAnimation, QEasingCurve

# Create QApplication
_qapp = QApplication.instance() or QApplication(sys.argv[:1])


def _unfixed_clear_with_delete_later_no_takeat(layout, placeholder_widget):
    """
    Simulate the ACTUAL unfixed clear logic from _display_baseline_summary():
    
        if self._empty_baseline is not None:
            self._empty_baseline.deleteLater()
            self._empty_baseline = None
    
    The widget is NOT removed from the layout via takeAt() — it's just scheduled
    for deletion. The layout still holds a reference to it.
    """
    # This is the bug: deleteLater() without removing from layout first
    placeholder_widget.deleteLater()
    # The widget is still in the layout — layout.count() is still 1


def _unfixed_fade_in_widget(widget, duration=350):
    """Replicate the unfixed _fade_in_widget() from improve_page.py."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()
    # BUG: no anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._fade_anim = anim


def test_bug1_stale_layout_children():
    """
    Test that deleteLater() leaves stale children in the layout.
    
    The actual bug: _display_baseline_summary() calls deleteLater() on the
    placeholder widget WITHOUT removing it from the layout first. The layout
    still holds the widget as a child.
    """
    print("\n--- test_bug1_stale_layout_children ---")
    
    for n_analyze_calls in [1, 2, 3, 5]:
        parent = QWidget()
        layout = QVBoxLayout(parent)
        placeholder = QWidget(parent)
        layout.addWidget(placeholder)
        
        assert layout.count() == 1, f"Expected 1 child, got {layout.count()}"
        
        # Simulate the unfixed clear: deleteLater() without takeAt()
        _unfixed_clear_with_delete_later_no_takeat(layout, placeholder)
        
        # The widget is still in the layout because deleteLater() is deferred
        stale_child_count = layout.count()
        
        try:
            assert stale_child_count == 0, (
                f"Bug 1 confirmed: stale_child_count == {stale_child_count} after deleteLater() clear. "
                f"n_analyze_calls={n_analyze_calls}. "
                f"deleteLater() is asynchronous — widget remains in layout."
            )
            print(f"  n={n_analyze_calls}: UNEXPECTED PASS (count={stale_child_count})")
        except AssertionError as e:
            print(f"  n={n_analyze_calls}: EXPECTED FAIL (count={stale_child_count}) ✓")
            print(f"    Counterexample: {e}")
            return True  # Bug confirmed
    
    print("  WARNING: Bug not confirmed for any input!")
    return False


def test_bug1_opacity_effect_not_removed():
    """Test that QGraphicsOpacityEffect is not removed after animation completes."""
    print("\n--- test_bug1_opacity_effect_not_removed ---")
    
    for n_widgets in [1, 2, 3]:
        all_failed = True
        for _ in range(n_widgets):
            widget = QWidget()
            _unfixed_fade_in_widget(widget, duration=0)
            widget._fade_anim.finished.emit()
            QCoreApplication.processEvents()
            
            effect = widget.graphicsEffect()
            
            try:
                assert effect is None, (
                    f"Bug 1 confirmed: widget.graphicsEffect() is not None after "
                    f"animation finished signal fired. Got: {effect!r}"
                )
                print(f"  n_widgets={n_widgets}: UNEXPECTED PASS (effect={effect})")
                all_failed = False
            except AssertionError as e:
                print(f"  n_widgets={n_widgets}: EXPECTED FAIL (effect={effect!r}) ✓")
                print(f"    Counterexample: {e}")
        
        if all_failed:
            return True  # Bug confirmed
    
    print("  WARNING: Bug not confirmed for any input!")
    return False


if __name__ == '__main__':
    print("Running bug condition exploration tests on UNFIXED code...")
    print("Expected outcome: BOTH tests should FAIL (confirming bugs exist)")
    print("=" * 70)
    
    bug1_stale = test_bug1_stale_layout_children()
    bug1_effect = test_bug1_opacity_effect_not_removed()
    
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print(f"  Bug 1 (stale layout children): {'CONFIRMED ✓' if bug1_stale else 'NOT CONFIRMED ✗'}")
    print(f"  Bug 1 (opacity effect not removed): {'CONFIRMED ✓' if bug1_effect else 'NOT CONFIRMED ✗'}")
    
    if bug1_stale and bug1_effect:
        print("\nAll bugs confirmed on unfixed code. Tests are working correctly.")
        sys.exit(0)
    else:
        print("\nWARNING: Some bugs were not confirmed. Check the test logic.")
        sys.exit(1)
