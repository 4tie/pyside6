"""
issue_badge.py — IssueBadge widget for displaying a single DiagnosedIssue.
"""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from app.core.models.improve_models import DiagnosedIssue

# Color palette (mirrors theme.py)
_C_GREEN = "#4ec9a0"
_C_RED = "#f44747"
_C_ORANGE = "#ce9178"
_C_YELLOW = "#dcdcaa"
_C_TEAL = "#4ec9a0"
_C_TEXT = "#d4d4d4"
_C_TEXT_DIM = "#9d9d9d"


class IssueBadge(QFrame):
    """A colored badge widget for a single diagnosed issue.

    Args:
        issue: The DiagnosedIssue to display.
        parent: Optional parent widget.
    """

    SEVERITY_COLORS = {
        "stoploss_too_wide": (_C_RED, "🔴"),
        "drawdown_high": (_C_RED, "🔴"),
        "negative_profit": (_C_RED, "🔴"),
        "weak_win_rate": (_C_ORANGE, "🟠"),
        "trades_too_low": (_C_YELLOW, "🟡"),
        "poor_pair_concentration": (_C_TEAL, "🔵"),
        "profit_factor_low": (_C_ORANGE, "🟠"),
        "expectancy_negative": (_C_ORANGE, "🟠"),
    }

    def __init__(self, issue: DiagnosedIssue, parent=None):
        super().__init__(parent)
        color, icon = self.SEVERITY_COLORS.get(issue.issue_id, (_C_TEXT_DIM, "⚪"))
        self.setStyleSheet(f"""
            IssueBadge {{
                background: {color}22;
                border: 1px solid {color}66;
                border-left: 3px solid {color};
                border-radius: 4px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(18)
        layout.addWidget(icon_lbl)

        text_lbl = QLabel(issue.description)
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet(
            f"color: {_C_TEXT}; font-size: 12px; background: transparent; border: none;"
        )
        layout.addWidget(text_lbl, 1)
