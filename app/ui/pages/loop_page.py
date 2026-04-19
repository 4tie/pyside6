"""
loop_page.py - LoopPage: automated strategy optimization loop UI.

Runs iterative backtest -> diagnose -> suggest -> apply cycles automatically,
tracking every iteration and surfacing the best result for user review.
"""
import copy
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QScrollArea, QFormLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QProgressBar, QFrame, QSpinBox, QDoubleSpinBox, QCheckBox,
    QSplitter, QTextEdit, QGridLayout,
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QFont

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_models import BacktestResults
from app.core.models.loop_models import LoopConfig, LoopIteration, LoopResult
from app.core.services.backtest_service import BacktestService
from app.core.services.improve_service import ImproveService
from app.core.services.loop_service import LoopService
from app.core.utils.app_logger import get_logger
from app.ui.pages.improve_page import check_prerequisites
from app.ui.widgets.iteration_history_row import IterationHistoryRow
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.loop_page")

# ---------------------------------------------------------------------------
# Color palette (mirrors improve_page.py / theme.py)
# ---------------------------------------------------------------------------
_C_GREEN       = "#4ec9a0"
_C_GREEN_LIGHT = "#6ad4b0"
_C_RED         = "#f44747"
_C_RED_LIGHT   = "#f47070"
_C_ORANGE      = "#ce9178"
_C_YELLOW      = "#dcdcaa"
_C_TEAL        = "#4ec9a0"
_C_TEAL_HOVER  = "#6ad4b0"
_C_DARK_BG     = "#1e1e1e"
_C_CARD_BG     = "#252526"
_C_ELEVATED    = "#2d2d30"
_C_CARD_HIGH   = "#333337"
_C_BORDER      = "#3e3e42"
_C_TEXT        = "#d4d4d4"
_C_TEXT_DIM    = "#9d9d9d"


# ---------------------------------------------------------------------------
# Small helper widgets
# ---------------------------------------------------------------------------

def _btn(label: str, bg: str, fg: str = "white", min_w: int = 120) -> QPushButton:
    """Create a styled QPushButton."""
    btn = QPushButton(label)
    btn.setMinimumWidth(min_w)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg};
            color: {fg};
            border: 1px solid {bg};
            border-radius: 4px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: bold;
        }}
        QPushButton:hover {{ border-color: {_C_TEAL}; }}
        QPushButton:disabled {{
            background: {_C_BORDER};
            color: {_C_TEXT_DIM};
            border-color: {_C_BORDER};
        }}
    """)
    return btn


class _StatCard(QFrame):
    """Compact stat card: label + big value."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(110)
        self.setMaximumWidth(160)
        self.setStyleSheet(f"""
            _StatCard {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:9px;font-weight:600;letter-spacing:1px;")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)

        self._val = QLabel("—")
        self._val.setStyleSheet(f"color:{_C_TEXT};font-size:17px;font-weight:bold;")
        self._val.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._val)

    def set_value(self, text: str, color: str = _C_TEXT) -> None:
        self._val.setText(text)
        self._val.setStyleSheet(f"color:{color};font-size:17px;font-weight:bold;")


# ---------------------------------------------------------------------------
# LoopPage
# ---------------------------------------------------------------------------

class LoopPage(QWidget):
    """Automated strategy optimization loop page.

    Runs iterative backtest -> diagnose -> suggest -> apply cycles, tracking
    every iteration and surfacing the best result for the user to accept.

    Args:
        settings_state: Application settings state with Qt signals.
    """

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        self._settings_state = settings_state

        # Services
        _backtest_svc = BacktestService(settings_state.settings_service)
        self._improve_service = ImproveService(
            settings_state.settings_service, _backtest_svc
        )
        self._loop_service = LoopService(self._improve_service)

        # Loop state
        self._loop_result: Optional[LoopResult] = None
        self._current_iteration: Optional[LoopIteration] = None
        self._run_started_at: float = 0.0
        self._sandbox_dir: Optional[Path] = None
        self._export_dir: Optional[Path] = None
        self._initial_params: dict = {}
        self._initial_results: Optional[BacktestResults] = None

        # Terminal (created early)
        self._terminal = TerminalWidget()

        # Connect settings signal
        settings_state.settings_changed.connect(self._refresh_strategies)
        settings_state.settings_changed.connect(self._check_config_guard)

        self._init_ui()
        self._refresh_strategies()
        # Deferred stale sandbox cleanup — runs after the event loop starts
        QTimer.singleShot(0, self._cleanup_stale_sandboxes)

    # ------------------------------------------------------------------
    # terminal property (for MainWindow._all_terminals)
    # ------------------------------------------------------------------

    @property
    def terminal(self) -> TerminalWidget:
        return self._terminal

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{ background: {_C_DARK_BG}; color: {_C_TEXT}; }}
            QGroupBox {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                font-size: 12px;
                color: {_C_TEXT};
                padding-top: 6px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: {_C_TEXT_DIM};
                font-size: 11px;
                letter-spacing: 1px;
                text-transform: uppercase;
            }}
            QComboBox {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                color: {_C_TEXT};
            }}
            QComboBox:hover {{ border-color: {_C_TEAL}; }}
            QComboBox QAbstractItemView {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                selection-background-color: {_C_TEAL};
            }}
            QSpinBox, QDoubleSpinBox {{
                background: {_C_CARD_BG};
                border: 1px solid {_C_BORDER};
                border-radius: 4px;
                padding: 3px 6px;
                color: {_C_TEXT};
            }}
            QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {_C_TEAL}; }}
            QScrollArea {{ border: none; background: {_C_DARK_BG}; }}
            QScrollBar:vertical {{
                background: {_C_CARD_BG}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {_C_BORDER}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {_C_TEAL}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # No-config warning
        self._no_config_banner = QLabel(
            "Warning: User data path is not configured. "
            "Go to Settings and set your Freqtrade user_data directory."
        )
        self._no_config_banner.setWordWrap(True)
        self._no_config_banner.setStyleSheet(f"""
            QLabel {{
                background: {_C_ELEVATED};
                border-left: 3px solid {_C_ORANGE};
                border-radius: 4px;
                color: {_C_TEXT};
                font-size: 12px;
                padding: 8px 12px;
            }}
        """)
        self._no_config_banner.setVisible(False)
        root.addWidget(self._no_config_banner)

        # Page title
        title = QLabel("Strategy Auto-Optimization Loop")
        title.setStyleSheet(f"color:{_C_TEXT};font-size:15px;font-weight:bold;padding:2px 0;")
        root.addWidget(title)

        subtitle = QLabel(
            "Automatically runs backtest -> diagnose -> improve cycles until your "
            "profitability targets are met or the iteration limit is reached."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:11px;padding-bottom:4px;")
        root.addWidget(subtitle)

        # ---- Config panel ----
        config_group = QGroupBox("Loop Configuration")
        config_lay = QGridLayout()
        config_lay.setContentsMargins(12, 10, 12, 10)
        config_lay.setSpacing(8)

        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:11px;")
            return l

        # Row 0: strategy
        config_lay.addWidget(_lbl("Strategy:"), 0, 0)
        self._strategy_combo = QComboBox()
        self._strategy_combo.setMinimumWidth(200)
        config_lay.addWidget(self._strategy_combo, 0, 1)

        # Row 0 col 2-3: max iterations
        config_lay.addWidget(_lbl("Max Iterations:"), 0, 2)
        self._max_iter_spin = QSpinBox()
        self._max_iter_spin.setRange(1, 50)
        self._max_iter_spin.setValue(10)
        self._max_iter_spin.setToolTip("Maximum number of backtest-improve cycles to run")
        config_lay.addWidget(self._max_iter_spin, 0, 3)

        # Row 1: targets
        config_lay.addWidget(_lbl("Target Profit (%):"), 1, 0)
        self._target_profit_spin = QDoubleSpinBox()
        self._target_profit_spin.setRange(-100.0, 10000.0)
        self._target_profit_spin.setValue(5.0)
        self._target_profit_spin.setSingleStep(0.5)
        self._target_profit_spin.setToolTip("Stop when total profit exceeds this value")
        config_lay.addWidget(self._target_profit_spin, 1, 1)

        config_lay.addWidget(_lbl("Target Win Rate (%):"), 1, 2)
        self._target_wr_spin = QDoubleSpinBox()
        self._target_wr_spin.setRange(0.0, 100.0)
        self._target_wr_spin.setValue(55.0)
        self._target_wr_spin.setSingleStep(1.0)
        self._target_wr_spin.setToolTip("Stop when win rate exceeds this value")
        config_lay.addWidget(self._target_wr_spin, 1, 3)

        # Row 2: drawdown + min trades
        config_lay.addWidget(_lbl("Max Drawdown (%):"), 2, 0)
        self._target_dd_spin = QDoubleSpinBox()
        self._target_dd_spin.setRange(0.0, 100.0)
        self._target_dd_spin.setValue(20.0)
        self._target_dd_spin.setSingleStep(1.0)
        self._target_dd_spin.setToolTip("Stop when max drawdown is below this value")
        config_lay.addWidget(self._target_dd_spin, 2, 1)

        config_lay.addWidget(_lbl("Min Trades:"), 2, 2)
        self._target_trades_spin = QSpinBox()
        self._target_trades_spin.setRange(1, 10000)
        self._target_trades_spin.setValue(30)
        self._target_trades_spin.setToolTip("Minimum trades required to consider a result valid")
        config_lay.addWidget(self._target_trades_spin, 2, 3)

        # Row 3: stop on first profitable checkbox
        self._stop_on_target_chk = QCheckBox("Stop as soon as all targets are met")
        self._stop_on_target_chk.setChecked(True)
        self._stop_on_target_chk.setStyleSheet(f"color:{_C_TEXT};font-size:11px;")
        config_lay.addWidget(self._stop_on_target_chk, 3, 0, 1, 4)

        # Row 4: OOS split + Walk-forward folds
        config_lay.addWidget(_lbl("OOS Split (%):"), 4, 0)
        self._oos_split_spin = QDoubleSpinBox()
        self._oos_split_spin.setRange(5.0, 50.0)
        self._oos_split_spin.setValue(20.0)
        self._oos_split_spin.setToolTip("Percentage of date range held out for out-of-sample gate")
        config_lay.addWidget(self._oos_split_spin, 4, 1)

        config_lay.addWidget(_lbl("Walk-Forward Folds (K):"), 4, 2)
        self._wf_folds_spin = QSpinBox()
        self._wf_folds_spin.setRange(2, 10)
        self._wf_folds_spin.setValue(5)
        self._wf_folds_spin.setToolTip("Number of folds for walk-forward validation gate")
        config_lay.addWidget(self._wf_folds_spin, 4, 3)

        # Row 5: Stress fee multiplier + Stress slippage
        config_lay.addWidget(_lbl("Stress Fee Multiplier:"), 5, 0)
        self._stress_fee_spin = QDoubleSpinBox()
        self._stress_fee_spin.setRange(1.0, 5.0)
        self._stress_fee_spin.setSingleStep(0.1)
        self._stress_fee_spin.setValue(2.0)
        self._stress_fee_spin.setToolTip("Fee multiplier applied during stress-test gate")
        config_lay.addWidget(self._stress_fee_spin, 5, 1)

        config_lay.addWidget(_lbl("Stress Slippage (%):"), 5, 2)
        self._stress_slippage_spin = QDoubleSpinBox()
        self._stress_slippage_spin.setRange(0.0, 2.0)
        self._stress_slippage_spin.setSingleStep(0.01)
        self._stress_slippage_spin.setValue(0.1)
        self._stress_slippage_spin.setToolTip("Per-trade slippage added during stress-test gate (%)")
        config_lay.addWidget(self._stress_slippage_spin, 5, 3)

        # Row 6: Stress profit target + Consistency threshold
        config_lay.addWidget(_lbl("Stress Profit Target (%):"), 6, 0)
        self._stress_profit_spin = QDoubleSpinBox()
        self._stress_profit_spin.setRange(0.0, 100.0)
        self._stress_profit_spin.setValue(50.0)
        self._stress_profit_spin.setToolTip(
            "Minimum profit required during stress-test gate as % of main profit target"
        )
        config_lay.addWidget(self._stress_profit_spin, 6, 1)

        config_lay.addWidget(_lbl("Consistency Threshold (%):"), 6, 2)
        self._consistency_spin = QDoubleSpinBox()
        self._consistency_spin.setRange(0.0, 100.0)
        self._consistency_spin.setValue(30.0)
        self._consistency_spin.setToolTip(
            "Maximum allowed std-dev of per-fold profit as % of mean fold profit"
        )
        config_lay.addWidget(self._consistency_spin, 6, 3)

        # Row 7: Validation mode
        config_lay.addWidget(_lbl("Validation Mode:"), 7, 0)
        self._validation_mode_combo = QComboBox()
        self._validation_mode_combo.addItems(["Full Ladder", "Quick"])
        self._validation_mode_combo.setToolTip(
            "Full Ladder: all five validation gates; Quick: gates 1–2 only"
        )
        self._validation_mode_combo.currentIndexChanged.connect(self._on_validation_mode_changed)
        config_lay.addWidget(self._validation_mode_combo, 7, 1, 1, 3)

        config_group.setLayout(config_lay)
        root.addWidget(config_group)

        # ---- Advanced Filters (collapsible) ----
        adv_group = QGroupBox("Advanced Filters")
        adv_group.setCheckable(True)
        adv_group.setChecked(False)
        adv_lay = QGridLayout()
        adv_lay.setContentsMargins(12, 10, 12, 10)
        adv_lay.setSpacing(8)

        adv_lay.addWidget(_lbl("Max Profit Concentration:"), 0, 0)
        self._adv_profit_conc_spin = QDoubleSpinBox()
        self._adv_profit_conc_spin.setRange(0.10, 0.90)
        self._adv_profit_conc_spin.setSingleStep(0.05)
        self._adv_profit_conc_spin.setValue(0.50)
        self._adv_profit_conc_spin.setToolTip("Max fraction of profit from top 3 trades")
        adv_lay.addWidget(self._adv_profit_conc_spin, 0, 1)

        adv_lay.addWidget(_lbl("Min Profit Factor:"), 0, 2)
        self._adv_profit_factor_spin = QDoubleSpinBox()
        self._adv_profit_factor_spin.setRange(1.0, 3.0)
        self._adv_profit_factor_spin.setSingleStep(0.05)
        self._adv_profit_factor_spin.setValue(1.1)
        self._adv_profit_factor_spin.setToolTip("Minimum acceptable profit factor")
        adv_lay.addWidget(self._adv_profit_factor_spin, 0, 3)

        adv_lay.addWidget(_lbl("Max Single-Pair Profit Share:"), 1, 0)
        self._adv_pair_dom_spin = QDoubleSpinBox()
        self._adv_pair_dom_spin.setRange(0.10, 1.0)
        self._adv_pair_dom_spin.setSingleStep(0.05)
        self._adv_pair_dom_spin.setValue(0.60)
        self._adv_pair_dom_spin.setToolTip("Max profit share from a single pair")
        adv_lay.addWidget(self._adv_pair_dom_spin, 1, 1)

        adv_lay.addWidget(_lbl("Max Single-Period Profit Share:"), 1, 2)
        self._adv_time_dom_spin = QDoubleSpinBox()
        self._adv_time_dom_spin.setRange(0.10, 1.0)
        self._adv_time_dom_spin.setSingleStep(0.05)
        self._adv_time_dom_spin.setValue(0.40)
        self._adv_time_dom_spin.setToolTip("Max profit share from a single time period")
        adv_lay.addWidget(self._adv_time_dom_spin, 1, 3)

        adv_lay.addWidget(_lbl("Max Walk-Forward Variance CV:"), 2, 0)
        self._adv_wf_variance_spin = QDoubleSpinBox()
        self._adv_wf_variance_spin.setRange(0.1, 3.0)
        self._adv_wf_variance_spin.setSingleStep(0.1)
        self._adv_wf_variance_spin.setValue(1.0)
        self._adv_wf_variance_spin.setToolTip("Max walk-forward coefficient of variation")
        adv_lay.addWidget(self._adv_wf_variance_spin, 2, 1)

        adv_group.setLayout(adv_lay)
        root.addWidget(adv_group)

        # ---- Control row ----
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        self._start_btn = _btn("▶  Start Loop", _C_GREEN)
        self._start_btn.setToolTip("Start the automated optimization loop")
        self._start_btn.clicked.connect(self._on_start)
        ctrl_row.addWidget(self._start_btn)

        self._stop_btn = _btn("⏹  Stop", _C_RED)
        self._stop_btn.setToolTip("Stop the loop after the current iteration finishes")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        ctrl_row.addWidget(self._stop_btn)

        ctrl_row.addStretch()

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:11px;")
        ctrl_row.addWidget(self._status_lbl)

        root.addLayout(ctrl_row)

        # ---- Progress bar ----
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedHeight(14)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {_C_BORDER};
                border-radius: 7px;
                border: none;
                text-align: center;
                font-size: 9px;
                color: {_C_TEXT_DIM};
            }}
            QProgressBar::chunk {{
                background: {_C_TEAL};
                border-radius: 7px;
            }}
        """)
        root.addWidget(self._progress_bar)

        # ---- Live stats row ----
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._stat_iter   = _StatCard("ITERATION")
        self._stat_profit = _StatCard("BEST PROFIT")
        self._stat_wr     = _StatCard("BEST WIN RATE")
        self._stat_dd     = _StatCard("BEST DRAWDOWN")
        self._stat_sharpe = _StatCard("BEST SHARPE")
        for card in (self._stat_iter, self._stat_profit, self._stat_wr,
                     self._stat_dd, self._stat_sharpe):
            stats_row.addWidget(card)
        stats_row.addStretch()
        root.addLayout(stats_row)

        # ---- Splitter: history list (top) + terminal (bottom) ----
        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {_C_BORDER}; height: 4px; }}")

        # History panel
        history_widget = QWidget()
        history_widget.setStyleSheet(f"background:{_C_DARK_BG};")
        history_lay = QVBoxLayout(history_widget)
        history_lay.setContentsMargins(0, 0, 0, 0)
        history_lay.setSpacing(4)

        hist_header = QHBoxLayout()
        self._history_title = QLabel("Iteration History")
        self._history_title.setStyleSheet(f"color:{_C_TEXT};font-size:12px;font-weight:bold;")
        hist_header.addWidget(self._history_title)
        hist_header.addStretch()
        history_lay.addLayout(hist_header)

        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._history_scroll.setMinimumHeight(180)

        self._history_content = QWidget()
        self._history_content.setStyleSheet(f"background:{_C_DARK_BG};")
        self._history_vlay = QVBoxLayout(self._history_content)
        self._history_vlay.setContentsMargins(2, 2, 2, 2)
        self._history_vlay.setSpacing(4)
        self._history_vlay.addStretch()

        self._empty_history_lbl = QLabel("No iterations yet — start the loop to begin.")
        self._empty_history_lbl.setStyleSheet(
            f"color:{_C_TEXT_DIM};font-size:12px;font-style:italic;padding:16px;"
        )
        self._empty_history_lbl.setAlignment(Qt.AlignCenter)
        self._history_vlay.insertWidget(0, self._empty_history_lbl)

        self._history_scroll.setWidget(self._history_content)
        history_lay.addWidget(self._history_scroll, 1)

        splitter.addWidget(history_widget)

        # Terminal panel
        terminal_widget = QWidget()
        terminal_widget.setStyleSheet(f"background:{_C_DARK_BG};")
        terminal_lay = QVBoxLayout(terminal_widget)
        terminal_lay.setContentsMargins(0, 0, 0, 0)
        terminal_lay.setSpacing(2)

        term_header = QLabel("Live Output")
        term_header.setStyleSheet(f"color:{_C_TEXT};font-size:12px;font-weight:bold;padding:2px 0;")
        terminal_lay.addWidget(term_header)
        terminal_lay.addWidget(self._terminal, 1)

        splitter.addWidget(terminal_widget)
        splitter.setSizes([300, 200])

        root.addWidget(splitter, 1)

        # ---- Best result panel ----
        self._best_group = QGroupBox("Best Result Found")
        self._best_group.setVisible(False)
        best_lay = QVBoxLayout()
        best_lay.setContentsMargins(12, 10, 12, 10)
        best_lay.setSpacing(8)

        self._best_summary_lbl = QLabel("")
        self._best_summary_lbl.setWordWrap(True)
        self._best_summary_lbl.setStyleSheet(f"color:{_C_TEXT};font-size:12px;")
        best_lay.addWidget(self._best_summary_lbl)

        self._best_changes_lbl = QLabel("")
        self._best_changes_lbl.setWordWrap(True)
        self._best_changes_lbl.setStyleSheet(f"color:{_C_TEXT_DIM};font-size:11px;")
        best_lay.addWidget(self._best_changes_lbl)

        best_btn_row = QHBoxLayout()
        self._apply_best_btn = _btn("Apply Best Result to Strategy", _C_GREEN)
        self._apply_best_btn.setToolTip(
            "Write the best found parameters to the live strategy JSON file."
        )
        self._apply_best_btn.clicked.connect(self._on_apply_best)
        best_btn_row.addWidget(self._apply_best_btn)

        self._discard_btn = _btn("Discard", _C_BORDER, _C_TEXT, 80)
        self._discard_btn.setToolTip("Discard the loop results without changing the strategy.")
        self._discard_btn.clicked.connect(self._on_discard)
        best_btn_row.addWidget(self._discard_btn)
        best_btn_row.addStretch()
        best_lay.addLayout(best_btn_row)

        self._best_group.setLayout(best_lay)
        root.addWidget(self._best_group)

    # ------------------------------------------------------------------
    # Config guard + strategy refresh
    # ------------------------------------------------------------------

    def _check_config_guard(self) -> None:
        settings = self._settings_state.settings_service.load_settings()
        failures = check_prerequisites(settings)
        if failures:
            self._no_config_banner.setText(
                "Configuration issues:\n• " + "\n• ".join(failures)
            )
            self._no_config_banner.setVisible(True)
        else:
            self._no_config_banner.setVisible(False)
        self._update_state_machine()

    def _update_state_machine(self) -> None:
        """Update button/control states based on current loop state.

        States:
          - idle-no-strategy: no strategy selected or prerequisites fail
          - idle-strategy-selected: strategy selected, prerequisites pass, not running
          - running: loop is actively running
          - finalizing: loop finished, best result available
          - post-apply/discard: best result applied or discarded
        """
        settings = self._settings_state.settings_service.load_settings()
        failures = check_prerequisites(settings)
        prerequisites_ok = len(failures) == 0

        is_running = self._loop_service.is_running
        strategy = self._strategy_combo.currentText().strip()
        has_strategy = bool(strategy) and not strategy.startswith("(")
        has_result = self._loop_result is not None and self._loop_result.best_iteration is not None

        # Strategy combo: disabled while running
        self._strategy_combo.setEnabled(prerequisites_ok and not is_running)

        # Config spin boxes: disabled while running
        config_spins = [
            self._max_iter_spin, self._target_profit_spin, self._target_wr_spin,
            self._target_dd_spin, self._target_trades_spin, self._stop_on_target_chk,
            self._oos_split_spin, self._wf_folds_spin, self._stress_fee_spin,
            self._stress_slippage_spin, self._stress_profit_spin, self._consistency_spin,
            self._validation_mode_combo,
        ]
        for w in config_spins:
            w.setEnabled(prerequisites_ok and not is_running)

        # Start button: only when idle + prerequisites + strategy selected
        self._start_btn.setVisible(not is_running)
        self._start_btn.setEnabled(prerequisites_ok and has_strategy and not is_running)

        # Stop button: only while running
        self._stop_btn.setVisible(is_running)
        self._stop_btn.setEnabled(is_running)

        # Apply/Discard: only when loop finished with a best result
        self._apply_best_btn.setEnabled(has_result and not is_running)
        self._discard_btn.setEnabled(has_result and not is_running)

    def _refresh_strategies(self) -> None:
        strategies = self._improve_service.get_available_strategies()
        current = self._strategy_combo.currentText()
        self._strategy_combo.blockSignals(True)
        self._strategy_combo.clear()
        if strategies:
            self._strategy_combo.addItems(strategies)
            idx = self._strategy_combo.findText(current)
            if idx >= 0:
                self._strategy_combo.setCurrentIndex(idx)
        else:
            self._strategy_combo.addItem("(no strategies found)")
        self._strategy_combo.blockSignals(False)
        self._check_config_guard()

    # ------------------------------------------------------------------
    # Loop control
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        """Validate config and kick off the first iteration."""
        strategy = self._strategy_combo.currentText().strip()
        if not strategy or strategy.startswith("("):
            QMessageBox.warning(self, "No Strategy", "Please select a strategy first.")
            return

        # Load initial params from the live strategy JSON
        settings = self._settings_state.settings_service.load_settings()
        from pathlib import Path as _Path
        strategies_dir = _Path(settings.user_data_path) / "strategies"
        strategy_py = strategies_dir / f"{strategy}.py"
        if not strategy_py.exists():
            QMessageBox.warning(
                self, "Strategy Not Found",
                f"Strategy file not found: {strategy_py}\n"
                "Make sure the strategy .py file exists in your strategies directory."
            )
            return

        initial_params = self._improve_service.load_baseline_params(
            _Path(settings.user_data_path) / "backtest_results" / "_loop_seed",
            strategy,
        )

        config = LoopConfig(
            strategy=strategy,
            max_iterations=self._max_iter_spin.value(),
            target_profit_pct=self._target_profit_spin.value(),
            target_win_rate=self._target_wr_spin.value(),
            target_max_drawdown=self._target_dd_spin.value(),
            target_min_trades=self._target_trades_spin.value(),
            stop_on_first_profitable=self._stop_on_target_chk.isChecked(),
            oos_split_pct=self._oos_split_spin.value(),
            walk_forward_folds=self._wf_folds_spin.value(),
            stress_fee_multiplier=self._stress_fee_spin.value(),
            stress_slippage_pct=self._stress_slippage_spin.value(),
            stress_profit_target_pct=self._stress_profit_spin.value(),
            consistency_threshold_pct=self._consistency_spin.value(),
            validation_mode="quick" if self._validation_mode_combo.currentText() == "Quick" else "full",
            profit_concentration_threshold=self._adv_profit_conc_spin.value(),
            profit_factor_floor=self._adv_profit_factor_spin.value(),
            pair_dominance_threshold=self._adv_pair_dom_spin.value(),
            time_dominance_threshold=self._adv_time_dom_spin.value(),
            validation_variance_ceiling=self._adv_wf_variance_spin.value(),
        )

        # Reset UI
        self._clear_history()
        self._best_group.setVisible(False)
        self._loop_result = None
        self._initial_params = initial_params
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Starting…")
        self._stat_iter.set_value("0")
        self._stat_profit.set_value("—")
        self._stat_wr.set_value("—")
        self._stat_dd.set_value("—")
        self._stat_sharpe.set_value("—")

        # Wire loop service callbacks
        self._loop_service.set_callbacks(
            on_iteration_complete=self._on_iteration_complete,
            on_loop_complete=self._on_loop_complete,
            on_status=self._set_status,
        )
        self._loop_service.start(config, initial_params)

        # Update button states
        self._update_state_machine()
        self._set_status(f"Loop started — strategy: {strategy}, max iterations: {config.max_iterations}")
        # Run the first backtest (no candidate params yet — use current strategy params)
        self._run_initial_backtest(strategy, config)

    def _on_stop(self) -> None:
        """Request loop stop and kill any running process."""
        self._loop_service.stop()
        self._terminal.process_service.stop_process()
        self._set_status("Stop requested — waiting for current backtest to finish…")
        self._stop_btn.setEnabled(False)

    def _run_initial_backtest(self, strategy: str, config: LoopConfig) -> None:
        """Run the very first backtest using the current (unmodified) strategy params."""
        self._set_status("Running initial backtest with current strategy parameters…")
        self._terminal.clear_output()
        self._terminal.append_output(
            f"=== Loop Start: {strategy} ===\n"
            f"Targets: profit>{config.target_profit_pct}%, "
            f"win_rate>{config.target_win_rate}%, "
            f"drawdown<{config.target_max_drawdown}%, "
            f"trades>{config.target_min_trades}\n\n"
        )

        settings = self._settings_state.settings_service.load_settings()
        from app.core.services.process_service import ProcessService
        from app.core.backtests.results_models import BacktestResults as _BR

        # Build a plain backtest command (no sandbox — just current strategy)
        backtest_svc = BacktestService(self._settings_state.settings_service)
        try:
            command = backtest_svc.build_command(strategy_name=strategy)
        except Exception as e:
            self._set_status(f"Error building command: {e}")
            self._finish_loop(f"Command build error: {e}")
            return

        from pathlib import Path as _Path
        import time as _time
        self._run_started_at = _time.time()
        self._current_iteration = None  # initial run has no iteration object yet

        # Export dir for initial run
        from datetime import datetime as _dt
        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        export_dir = (
            _Path(settings.user_data_path)
            / "backtest_results" / "_loop" / f"{strategy}_init_{ts}"
        )
        export_dir.mkdir(parents=True, exist_ok=True)
        self._export_dir = export_dir

        # Patch command to write to our export dir
        cmd_list = command.as_list()
        if "--backtest-directory" not in cmd_list:
            cmd_list += ["--backtest-directory", str(export_dir)]

        self._terminal.append_output(f"$ {' '.join(cmd_list)}\n\n")

        env = None
        if settings.venv_path:
            env = ProcessService.build_environment(settings.venv_path)

        try:
            self._terminal.process_service.execute_command(
                command=cmd_list,
                on_output=self._terminal.append_output,
                on_error=self._terminal.append_error,
                on_finished=self._on_initial_backtest_finished,
                working_directory=command.cwd,
                env=env,
            )
        except Exception as e:
            self._set_status(f"Process error: {e}")
            self._finish_loop(f"Process error: {e}")

    def _on_initial_backtest_finished(self, exit_code: int) -> None:
        """Handle completion of the initial (seed) backtest."""
        self._terminal.append_output(f"\n[Initial backtest finished] exit_code={exit_code}\n\n")

        if exit_code != 0:
            self._set_status("Initial backtest failed — check terminal output.")
            self._finish_loop("Initial backtest failed")
            return

        try:
            results = self._improve_service.parse_candidate_run(
                self._export_dir, self._run_started_at
            )
            self._initial_results = results
            s = results.summary
            self._terminal.append_output(
                f"Initial results: profit={s.total_profit:.2f}%, "
                f"win_rate={s.win_rate:.1f}%, drawdown={s.max_drawdown:.1f}%, "
                f"trades={s.total_trades}\n\n"
            )
            # Re-start loop service with the initial results so it seeds the best score
            config = self._loop_service._config
            self._loop_service.start(config, self._initial_params, results)
            # Now run the first real improvement iteration
            self._run_next_iteration(results)
        except (FileNotFoundError, ValueError) as e:
            self._set_status(f"Could not parse initial results: {e}")
            self._finish_loop(f"Parse error: {e}")

    def _run_next_iteration(self, latest_results: BacktestResults) -> None:
        """Ask the loop service to prepare the next iteration and run it."""
        if not self._loop_service.should_continue():
            self._finish_loop()
            return

        prepared = self._loop_service.prepare_next_iteration(latest_results)
        if prepared is None:
            self._finish_loop()
            return

        iteration, suggestions = prepared
        self._current_iteration = iteration

        config = self._loop_service._config
        n = iteration.iteration_number
        total = config.max_iterations
        pct = int(n / total * 100)
        self._progress_bar.setValue(pct)
        self._progress_bar.setFormat(f"Iteration {n}/{total}")
        self._stat_iter.set_value(f"{n}/{total}")

        self._terminal.append_output(
            f"--- Iteration {n}/{total} ---\n"
            f"Changes: {', '.join(iteration.changes_summary)}\n\n"
        )

        # Prepare sandbox with candidate params
        strategy = config.strategy
        try:
            sandbox_dir = self._improve_service.prepare_sandbox(
                strategy, iteration.params_after
            )
            self._sandbox_dir = sandbox_dir
        except FileNotFoundError as e:
            self._loop_service.record_iteration_error(iteration, str(e))
            self._run_next_iteration_after_error(latest_results)
            return

        command, export_dir = self._improve_service.build_candidate_command(
            strategy, latest_results, sandbox_dir
        )
        self._export_dir = export_dir

        import time as _time
        self._run_started_at = _time.time()

        cmd_list = command.as_list()
        self._terminal.append_output(f"$ {' '.join(cmd_list)}\n\n")

        settings = self._settings_state.settings_service.load_settings()
        from app.core.services.process_service import ProcessService
        env = None
        if settings.venv_path:
            env = ProcessService.build_environment(settings.venv_path)

        try:
            self._terminal.process_service.execute_command(
                command=cmd_list,
                on_output=self._terminal.append_output,
                on_error=self._terminal.append_error,
                on_finished=self._on_iteration_backtest_finished,
                working_directory=command.cwd,
                env=env,
            )
        except Exception as e:
            self._loop_service.record_iteration_error(iteration, str(e))
            self._run_next_iteration_after_error(latest_results)

    def _run_next_iteration_after_error(self, latest_results: BacktestResults) -> None:
        """Continue the loop after a non-fatal iteration error."""
        if self._loop_service.should_continue():
            QTimer.singleShot(500, lambda: self._run_next_iteration(latest_results))
        else:
            self._finish_loop()

    def _on_iteration_backtest_finished(self, exit_code: int) -> None:
        """Handle completion of a candidate backtest within the loop."""
        iteration = self._current_iteration
        self._terminal.append_output(
            f"\n[Iteration {iteration.iteration_number} finished] exit_code={exit_code}\n\n"
        )

        if exit_code != 0:
            self._loop_service.record_iteration_error(
                iteration, f"Backtest exited with code {exit_code}"
            )
            # Continue loop with the previous best results
            best = self._loop_service.current_result.best_iteration
            fallback = self._initial_results
            if fallback and self._loop_service.should_continue():
                QTimer.singleShot(300, lambda: self._run_next_iteration(fallback))
            else:
                self._finish_loop()
            return

        try:
            results = self._improve_service.parse_candidate_run(
                self._export_dir, self._run_started_at
            )
        except (FileNotFoundError, ValueError) as e:
            self._loop_service.record_iteration_error(iteration, str(e))
            best = self._loop_service.current_result.best_iteration
            fallback = self._initial_results
            if fallback and self._loop_service.should_continue():
                QTimer.singleShot(300, lambda: self._run_next_iteration(fallback))
            else:
                self._finish_loop()
            return

        is_improvement = self._loop_service.record_iteration_result(iteration, results.summary)
        s = results.summary
        self._terminal.append_output(
            f"Result: profit={s.total_profit:.2f}%, win_rate={s.win_rate:.1f}%, "
            f"drawdown={s.max_drawdown:.1f}%, trades={s.total_trades}, "
            f"sharpe={s.sharpe_ratio or 0:.2f} "
            f"{'[IMPROVEMENT]' if is_improvement else '[no improvement]'}\n\n"
        )

        # Update live stat cards if this is the best so far
        best_it = self._loop_service.current_result.best_iteration
        if best_it and best_it.summary is not None:
            bs = best_it.summary
            profit_color = _C_GREEN_LIGHT if bs.total_profit >= 0 else _C_RED_LIGHT
            self._stat_profit.set_value(f"{bs.total_profit:+.2f}%", profit_color)
            wr_color = _C_GREEN_LIGHT if bs.win_rate >= 50 else _C_RED_LIGHT
            self._stat_wr.set_value(f"{bs.win_rate:.1f}%", wr_color)
            dd_color = _C_RED_LIGHT if bs.max_drawdown > 20 else _C_YELLOW
            self._stat_dd.set_value(f"{bs.max_drawdown:.1f}%", dd_color)
            sharpe_color = _C_GREEN_LIGHT if (bs.sharpe_ratio or 0) >= 1 else _C_TEXT_DIM
            self._stat_sharpe.set_value(f"{bs.sharpe_ratio or 0:.2f}", sharpe_color)

        # Continue or finish
        if self._loop_service.should_continue():
            QTimer.singleShot(200, lambda: self._run_next_iteration(results))
        else:
            self._finish_loop()

    def _finish_loop(self, stop_reason: str = "") -> None:
        """Finalize the loop and update the UI."""
        result = self._loop_service.finalize(stop_reason)
        self._loop_result = result

        self._update_state_machine()
        self._progress_bar.setValue(100)
        self._progress_bar.setFormat("Done")
        reason = result.stop_reason or "Loop complete"
        target_icon = "Target reached!" if result.target_reached else reason
        self._set_status(f"Loop finished — {target_icon} ({result.total_iterations} iterations)")

        self._terminal.append_output(
            f"\n=== Loop Complete ===\n"
            f"Iterations: {result.total_iterations}\n"
            f"Stop reason: {result.stop_reason}\n"
            f"Target reached: {result.target_reached}\n"
        )

        if result.best_iteration and result.best_iteration.summary is not None:
            bs = result.best_iteration.summary
            self._terminal.append_output(
                f"Best result (iteration #{result.best_iteration.iteration_number}):\n"
                f"  Profit: {bs.total_profit:.2f}%\n"
                f"  Win Rate: {bs.win_rate:.1f}%\n"
                f"  Max Drawdown: {bs.max_drawdown:.1f}%\n"
                f"  Trades: {bs.total_trades}\n"
                f"  Sharpe: {bs.sharpe_ratio or 0:.2f}\n"
            )
            self._show_best_result(result)
        else:
            self._terminal.append_output("No successful iterations completed.\n")

        # Fire the loop_complete callback
        if self._loop_service._on_loop_complete:
            self._loop_service._on_loop_complete(result)

    # ------------------------------------------------------------------
    # Iteration history UI
    # ------------------------------------------------------------------

    def _on_iteration_complete(self, iteration: LoopIteration) -> None:
        """Add a row to the history list for the completed iteration."""
        # Remove empty state label on first iteration
        if self._empty_history_lbl is not None:
            self._empty_history_lbl.setParent(None)
            self._empty_history_lbl = None

        total_gates = 2 if self._validation_mode_combo.currentText() == "Quick" else 5
        row = IterationHistoryRow(iteration, total_gates=total_gates)
        # Insert before the trailing stretch (last item)
        insert_pos = max(0, self._history_vlay.count() - 1)
        self._history_vlay.insertWidget(insert_pos, row)

        # Auto-scroll to bottom
        QTimer.singleShot(50, lambda: self._history_scroll.verticalScrollBar().setValue(
            self._history_scroll.verticalScrollBar().maximum()
        ))

        n = iteration.iteration_number
        total = self._loop_service._config.max_iterations if self._loop_service._config else 1
        self._history_title.setText(
            f"Iteration History ({n} of {total})"
        )

    def _on_loop_complete(self, result: LoopResult) -> None:
        """Called by loop service when the loop finishes (no-op — handled by _finish_loop)."""
        pass

    def _clear_history(self) -> None:
        """Remove all iteration rows from the history list."""
        while self._history_vlay.count() > 1:
            item = self._history_vlay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        self._empty_history_lbl = QLabel("No iterations yet — start the loop to begin.")
        self._empty_history_lbl.setStyleSheet(
            f"color:{_C_TEXT_DIM};font-size:12px;font-style:italic;padding:16px;"
        )
        self._empty_history_lbl.setAlignment(Qt.AlignCenter)
        self._history_vlay.insertWidget(0, self._empty_history_lbl)
        self._history_title.setText("Iteration History")

    # ------------------------------------------------------------------
    # Best result panel
    # ------------------------------------------------------------------

    def _show_best_result(self, result: LoopResult) -> None:
        """Populate and show the best result panel."""
        best = result.best_iteration
        if best is None or best.summary is None:
            return

        bs = best.summary
        profit_color = _C_GREEN_LIGHT if bs.total_profit >= 0 else _C_RED_LIGHT
        target_icon = "Target reached!" if result.target_reached else "Best found"

        self._best_summary_lbl.setText(
            f"<b style='color:{_C_GREEN}'>{target_icon}</b> — "
            f"Best result at iteration #{best.iteration_number}: "
            f"<span style='color:{profit_color}'>Profit {bs.total_profit:+.2f}%</span>, "
            f"Win Rate {bs.win_rate:.1f}%, "
            f"Max Drawdown {bs.max_drawdown:.1f}%, "
            f"Trades {bs.total_trades}, "
            f"Sharpe {bs.sharpe_ratio or 0:.2f}"
        )
        self._best_summary_lbl.setTextFormat(Qt.RichText)

        if best.changes_summary:
            changes_text = "Parameter changes from original: " + ", ".join(best.changes_summary)
        else:
            changes_text = "No parameter changes from original."
        self._best_changes_lbl.setText(changes_text)

        self._best_group.setVisible(True)

    def _on_apply_best(self) -> None:
        """Write the best found parameters to the live strategy JSON."""
        if self._loop_result is None or self._loop_result.best_iteration is None:
            return

        strategy = self._strategy_combo.currentText().strip()
        best_params = self._loop_result.best_params

        if not best_params:
            QMessageBox.information(
                self, "Nothing to Apply",
                "The best iteration had no parameter changes to apply."
            )
            return

        reply = QMessageBox.question(
            self,
            "Apply Best Result",
            f"This will overwrite the live parameter file for strategy '{strategy}' "
            f"with the best found parameters.\n\n"
            f"Changes: {', '.join(self._loop_result.best_iteration.changes_summary)}\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._improve_service.accept_candidate(strategy, best_params)
            QMessageBox.information(
                self, "Applied",
                f"Best parameters applied to '{strategy}'.\n"
                "You can now run a full backtest to verify the results."
            )
            self._best_group.setVisible(False)
            self._set_status(f"Best parameters applied to '{strategy}'.")
        except OSError as e:
            QMessageBox.critical(self, "Apply Failed", str(e))

    def _on_discard(self) -> None:
        """Discard the loop results without modifying the strategy."""
        self._loop_result = None
        self._best_group.setVisible(False)
        self._set_status("Results discarded.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        """Update the status label."""
        self._status_lbl.setText(message)
        _log.info("LoopPage status: %s", message)

    def _on_validation_mode_changed(self, index: int) -> None:
        """Enable/disable walk-forward and stress controls based on validation mode."""
        is_quick = self._validation_mode_combo.currentText() == "Quick"
        for spin in (
            self._wf_folds_spin,
            self._stress_fee_spin,
            self._stress_slippage_spin,
            self._stress_profit_spin,
            self._consistency_spin,
        ):
            spin.setEnabled(not is_quick)

    def _cleanup_stale_sandboxes(self) -> None:
        """Silently delete sandbox directories older than 24 hours.

        Runs deferred (via QTimer.singleShot) so it never blocks the UI.
        """
        import shutil
        import time as _time

        try:
            settings = self._settings_state.settings_service.load_settings()
            user_data_path = getattr(settings, "user_data_path", "") or ""
            if not str(user_data_path).strip():
                return

            sandbox_root = Path(user_data_path) / "strategies" / "_improve_sandbox"
            if not sandbox_root.exists():
                return

            cutoff = _time.time() - 24 * 3600  # 24 hours ago
            for entry in sandbox_root.iterdir():
                if not entry.is_dir():
                    continue
                try:
                    mtime = entry.stat().st_mtime
                    if mtime < cutoff:
                        shutil.rmtree(entry, ignore_errors=True)
                        _log.debug("Cleaned up stale sandbox: %s", entry)
                except OSError:
                    pass  # silently skip unreadable entries
        except Exception:
            pass  # never raise from cleanup
