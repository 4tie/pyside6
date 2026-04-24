"""
iteration_history_row.py — IterationHistoryRow widget.

Displays a single LoopIteration as a compact row with status icon,
metrics, gate progress, and border/badge styling.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel,
)

from app.core.models.loop_models import LoopIteration

# Border colour constants
_BORDER_GREEN  = "#1a7f37"
_BORDER_RED    = "#cf222e"
_BORDER_AMBER  = "#bf8700"
_BORDER_ORANGE = "#d1242f"
_BORDER_DEFAULT = "#444444"

# Badge background colours
_BADGE_GREEN  = "#1a7f37"
_BADGE_AMBER  = "#bf8700"
_BADGE_ORANGE = "#e36209"
_BADGE_GREY   = "#555555"


def _badge(text: str, bg: str) -> QLabel:
    """Return a small coloured badge label."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background:{bg}; color:#ffffff; font-size:9px; font-weight:bold;"
        "padding:1px 4px; border-radius:3px;"
    )
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def _metric(value: str, muted: bool = False) -> QLabel:
    """Return a compact metric label."""
    lbl = QLabel(value)
    colour = "#888888" if muted else "#cccccc"
    lbl.setStyleSheet(f"color:{colour}; font-size:10px;")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


class IterationHistoryRow(QFrame):
    """Compact row widget for a single LoopIteration in the history list.

    Args:
        iteration: The LoopIteration to display.
        total_gates: Total gate count for the current validation mode
            (5 for Full Ladder, 2 for Quick mode).
        parent: Optional parent widget.
    """

    def __init__(
        self,
        iteration: LoopIteration,
        total_gates: int = 5,
        parent: Optional[object] = None,
    ) -> None:
        super().__init__(parent)
        self.iteration = iteration
        self._total_gates = total_gates
        self._build_ui()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_style(self) -> tuple[str, Optional[str], Optional[str]]:
        """Return (border_colour, badge_text, badge_bg) for this iteration."""
        it = self.iteration

        if it.is_improvement:
            return _BORDER_GREEN, "BEST", _BADGE_GREEN

        if it.status == "error":
            return _BORDER_RED, None, None

        if it.status == "hard_filter_rejected":
            return _BORDER_ORANGE, "FILTERED", _BADGE_ORANGE

        # Amber: passed Gate 1 but overall gate validation failed
        gate1_passed = any(
            gr.gate_name in ("in_sample", "gate_1") and gr.passed
            for gr in it.gate_results
        )
        if gate1_passed and not it.validation_gate_passed and it.status != "hard_filter_rejected":
            return _BORDER_AMBER, "PARTIAL", _BADGE_AMBER

        return _BORDER_DEFAULT, None, None

    def _status_icon(self) -> str:
        """Return a unicode status icon for the iteration status."""
        if self.iteration.is_improvement:
            return "✅"
        if self.iteration.status == "error":
            return "❌"
        if self.iteration.status in ("hard_filter_rejected", "gate_failed", "zero_trades"):
            return "❌"
        if self.iteration.validation_gate_passed:
            return "✅"
        return "➡"

    def _gates_passed_count(self) -> int:
        """Return the number of gates that passed."""
        return sum(1 for gr in self.iteration.gate_results if gr.passed)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        it = self.iteration
        border_colour, badge_text, badge_bg = self._resolve_style()

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"IterationHistoryRow {{ border: 1px solid {border_colour};"
            "border-radius:4px; background:#1e1e1e; margin:1px; }}"
        )
        self.setFixedHeight(44)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 2, 6, 2)
        outer.setSpacing(6)

        # --- Iteration number badge ---
        num_lbl = _badge(f"#{it.iteration_number}", _BADGE_GREY)
        num_lbl.setFixedWidth(30)
        outer.addWidget(num_lbl)

        # --- Status icon ---
        icon_lbl = QLabel(self._status_icon())
        icon_lbl.setStyleSheet("font-size:14px;")
        icon_lbl.setFixedWidth(20)
        outer.addWidget(icon_lbl)

        # --- Changes summary ---
        changes_text = ", ".join(it.changes_summary) if it.changes_summary else "—"
        changes_lbl = QLabel(changes_text)
        changes_lbl.setStyleSheet("color:#aaaaaa; font-size:10px;")
        changes_lbl.setMaximumWidth(200)
        changes_lbl.setToolTip(changes_text)
        # Elide long text
        changes_lbl.setWordWrap(False)
        outer.addWidget(changes_lbl, 1)

        # --- Metrics row ---
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(8)

        if it.summary is not None:
            profit_colour = "#1a7f37" if it.summary.total_profit >= 0 else "#cf222e"
            profit_lbl = QLabel(f"{it.summary.total_profit:+.1f}%")
            profit_lbl.setStyleSheet(
                f"color:{profit_colour}; font-size:10px; font-weight:bold;"
            )
            metrics_layout.addWidget(profit_lbl)

            metrics_layout.addWidget(_metric(f"WR:{it.summary.win_rate:.0f}%"))
            metrics_layout.addWidget(_metric(f"DD:{it.summary.max_drawdown:.1f}%"))
            metrics_layout.addWidget(_metric(f"T:{it.summary.total_trades}"))
            sharpe = it.summary.sharpe_ratio
            if sharpe is not None:
                metrics_layout.addWidget(_metric(f"SR:{sharpe:.2f}"))
        elif it.error_message:
            err_lbl = QLabel(it.error_message[:40])
            err_lbl.setStyleSheet("color:#cf222e; font-size:10px;")
            metrics_layout.addWidget(err_lbl)
        else:
            metrics_layout.addWidget(_metric("—", muted=True))

        outer.addLayout(metrics_layout)

        # --- Gate progress ---
        gates_passed = self._gates_passed_count()
        gate_lbl = _metric(f"{gates_passed}/{self._total_gates} gates")
        gate_lbl.setFixedWidth(60)
        outer.addWidget(gate_lbl)

        # --- Last gate name ---
        gate_name = it.validation_gate_reached or "—"
        gate_name_lbl = QLabel(gate_name)
        gate_name_lbl.setStyleSheet("color:#888888; font-size:9px;")
        gate_name_lbl.setFixedWidth(80)
        gate_name_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        outer.addWidget(gate_name_lbl)

        # --- Gate pass/fail indicator ---
        gate_pass_icon = "✔" if it.validation_gate_passed else "✘"
        gate_pass_colour = "#1a7f37" if it.validation_gate_passed else "#cf222e"
        gate_pass_lbl = QLabel(gate_pass_icon)
        gate_pass_lbl.setStyleSheet(f"color:{gate_pass_colour}; font-size:11px;")
        gate_pass_lbl.setFixedWidth(14)
        outer.addWidget(gate_pass_lbl)

        # --- Status badge (BEST / PARTIAL / FILTERED) ---
        if badge_text and badge_bg:
            outer.addWidget(_badge(badge_text, badge_bg))

            # For FILTERED: append filter names
            if badge_text == "FILTERED" and it.hard_filter_failures:
                names = ", ".join(f.filter_name for f in it.hard_filter_failures)
                filter_lbl = QLabel(names)
                filter_lbl.setStyleSheet("color:#e36209; font-size:9px;")
                filter_lbl.setToolTip(names)
                outer.addWidget(filter_lbl)
