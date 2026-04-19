"""
suggestion_row.py — SuggestionRow widget for displaying a single ParameterSuggestion.
"""
from typing import Callable

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from PySide6.QtCore import Qt

from app.core.models.improve_models import ParameterSuggestion

# Color palette (mirrors improve_page.py / theme.py)
_C_GREEN = "#4ec9a0"
_C_GREEN_LIGHT = "#6ad4b0"
_C_YELLOW = "#dcdcaa"
_C_TEAL = "#4ec9a0"
_C_TEAL_HOVER = "#6ad4b0"
_C_CARD_BG = "#252526"
_C_BORDER = "#3e3e42"
_C_TEXT = "#d4d4d4"
_C_TEXT_DIM = "#9d9d9d"


class SuggestionRow(QFrame):
    """A styled row for a single parameter suggestion with Apply button.

    Args:
        suggestion: The ParameterSuggestion to display.
        on_apply: Callback invoked when the Apply button is clicked.
        parent: Optional parent widget.
    """

    PARAM_ICONS = {
        "stoploss": "🛑",
        "max_open_trades": "📊",
        "minimal_roi": "🎯",
        "pairlist": "💱",
    }

    def __init__(
        self,
        suggestion: ParameterSuggestion,
        on_apply: Callable[[ParameterSuggestion], None],
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet(f"""
            SuggestionRow {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                border-radius: 6px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        icon = self.PARAM_ICONS.get(suggestion.parameter, "⚙️")
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(22)
        icon_lbl.setStyleSheet("font-size: 14px; background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        value_text = "Advisory" if suggestion.is_advisory else str(suggestion.proposed_value)
        param_color = _C_YELLOW if suggestion.is_advisory else _C_GREEN_LIGHT
        header = QLabel(
            f"<b style='color:{param_color}'>{suggestion.parameter}</b>: {value_text}"
        )
        header.setStyleSheet(
            f"color: {_C_TEXT}; font-size: 12px; background: transparent; border: none;"
        )
        text_col.addWidget(header)

        detail = QLabel(
            f"{suggestion.reason} → "
            f"<i style='color:{_C_TEAL}'>{suggestion.expected_effect}</i>"
        )
        detail.setWordWrap(True)
        detail.setStyleSheet(
            f"color: {_C_TEXT_DIM}; font-size: 11px; background: transparent; border: none;"
        )
        text_col.addWidget(detail)

        layout.addLayout(text_col, 1)

        if not suggestion.is_advisory:
            apply_btn = QPushButton("Apply")
            apply_btn.setFixedWidth(70)
            apply_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_C_TEAL};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background: {_C_TEAL_HOVER};
                }}
                QPushButton:pressed {{
                    background: #3aaa84;
                }}
            """)
            apply_btn.clicked.connect(lambda: on_apply(suggestion))
            layout.addWidget(apply_btn)
        else:
            adv_lbl = QLabel("Advisory")
            adv_lbl.setFixedWidth(70)
            adv_lbl.setAlignment(Qt.AlignCenter)
            adv_lbl.setStyleSheet(f"""
                color: {_C_YELLOW};
                background: {_C_YELLOW}22;
                border: 1px solid {_C_YELLOW}66;
                border-radius: 4px;
                padding: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
            layout.addWidget(adv_lbl)
