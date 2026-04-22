"""
animated_metric_card.py — AnimatedMetricCard widget for displaying a metric with animation.
"""
from typing import Optional

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import QPropertyAnimation, QEasingCurve

# Color palette (mirrors theme.py)
_C_TEAL = "#4ec9a0"
_C_CARD_BG = "#333337"
_C_BORDER = "#3e3e42"
_C_TEXT = "#d4d4d4"
_C_TEXT_DIM = "#9d9d9d"


class AnimatedMetricCard(QFrame):
    """A card widget showing a metric with a color-coded value and animated bar.

    Args:
        label: The metric label displayed at the top of the card.
        parent: Optional parent widget.
    """

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._target_pct = 0.0
        self._anim: Optional[QPropertyAnimation] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(140)
        self.setMaximumWidth(200)
        self.setStyleSheet(f"""
            AnimatedMetricCard {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self._lbl = QLabel(self._label)
        self._lbl.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 10px; font-weight: 600; letter-spacing: 1px;"
        )
        from PySide6.QtCore import Qt
        self._lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl)

        self._value_lbl = QLabel("—")
        self._value_lbl.setStyleSheet(
            f"color: {_C_TEXT}; font-size: 18px; font-weight: bold;"
        )
        self._value_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._value_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background: {_C_BORDER};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {_C_TEAL};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self._bar)

        self._sub_lbl = QLabel("")
        self._sub_lbl.setStyleSheet(f"color: {_C_TEXT_DIM}; font-size: 9px;")
        self._sub_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._sub_lbl)

    def set_value(
        self,
        text: str,
        color: str = _C_TEXT,
        bar_pct: float = 0.0,
        bar_color: str = _C_TEAL,
        sub_text: str = "",
    ) -> None:
        """Update the card value, bar fill, and optional sub-label with animation.

        Args:
            text: The value text to display.
            color: Hex color for the value label.
            bar_pct: Target bar fill percentage (0–100).
            bar_color: Hex color for the progress bar chunk.
            sub_text: Optional sub-label text below the bar.
        """
        self._value_lbl.setText(text)
        self._value_lbl.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: bold;"
        )
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background: {_C_BORDER};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {bar_color};
                border-radius: 2px;
            }}
        """)
        self._sub_lbl.setText(sub_text)

        # Animate bar from current to target
        if self._anim:
            self._anim.stop()
        self._anim = QPropertyAnimation(self._bar, b"value")
        self._anim.setDuration(600)
        self._anim.setStartValue(self._bar.value())
        self._anim.setEndValue(int(min(max(bar_pct, 0), 100)))
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()
