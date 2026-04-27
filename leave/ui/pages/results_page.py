"""Results browser — browse, view, and analyze backtest runs."""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QFrame, QTabWidget, QScrollArea, QSizePolicy,
    QAbstractItemView, QDialog, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_index import IndexStore
from app.core.services.rollback_service import RollbackService
from app.ui import theme
from app.ui.dialogs.rollback_dialog import RollbackDialog
from app.ui.widgets.stat_card import StatCard
from app.ui.widgets.charts import EquityCurveChart, ProfitBarChart, WinRateDonut, PairProfitChart
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.results")


def _run_dir_path(br_dir: str, run: dict) -> Path:
    """Resolve the run folder path robustly regardless of OS or index format.

    The global index may store run_dir as 'Strategy\\run_...' (Windows) or
    'Strategy/run_...'. The per-strategy index stores just 'run_...'.
    We always reconstruct as {br_dir}/{strategy}/{run_id} which is canonical.
    """
    strategy = run.get("strategy", "")
    run_id   = run.get("run_id", "")
    if strategy and run_id:
        return Path(br_dir) / strategy / run_id
    # Fallback: normalise whatever run_dir contains
    raw = run.get("run_dir", "")
    return Path(br_dir) / Path(raw.replace("\\", "/"))


def _trade_profit(t: dict) -> float:
    """Return profit % from a trade dict, handling both field name variants."""
    return t.get("profit_pct", t.get("profit", 0.0))


def _trade_profit_abs(t: dict) -> float:
    return t.get("profit_abs", 0.0)


def _trade_open_date(t: dict) -> str:
    return str(t.get("entry", t.get("open_date", "")))[:16]


def _trade_close_date(t: dict) -> str:
    return str(t.get("exit", t.get("close_date", "")))[:16]


def _trade_open_rate(t: dict) -> float:
    return t.get("entry_rate", t.get("open_rate", 0.0))


def _trade_close_rate(t: dict) -> float:
    return t.get("exit_rate", t.get("close_rate", 0.0))


def _trade_duration_min(t: dict) -> int:
    """Return trade duration in minutes, handling saved and raw result fields."""
    raw = t.get("duration_min", t.get("trade_duration", t.get("duration", 0)))
    try:
        return int(float(raw or 0))
    except (TypeError, ValueError):
        return 0


def _format_duration(minutes: int) -> str:
    if minutes <= 0:
        return "—"
    hours, mins = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return " ".join(parts)


# ── Color-coding pure functions ───────────────────────────────────────────────

def _profit_color(value: float) -> str:
    """Map profit/return value to theme color."""
    if value > 0:
        return theme.GREEN
    if value < 0:
        return theme.RED
    return theme.TEXT_PRIMARY


def _win_rate_color(value: float) -> str:
    """Map win rate percentage to theme color."""
    return theme.GREEN if value >= 50.0 else theme.RED


def _sharpe_color(value: float) -> str:
    """Map Sharpe ratio to theme color."""
    if value >= 1.0:
        return theme.GREEN
    if value > 0.0:
        return theme.YELLOW
    return theme.RED


def _profit_factor_color(value: float) -> str:
    """Map profit factor to theme color."""
    return theme.GREEN if value >= 1.0 else theme.RED


def _profit_accent_color(value: float) -> str:
    """Map profit % to StatCard accent color."""
    return theme.GREEN if value >= 0 else theme.RED


def _drawdown_accent_color(value: float) -> str:
    """Map drawdown % to StatCard accent color."""
    return theme.RED if value > 20.0 else theme.YELLOW


class ResultsPage(QWidget):
    def __init__(self, settings_state: SettingsState, parent: QWidget | None = None):
        super().__init__(parent)
        self._state = settings_state
        self._current_run: Optional[dict] = None
        self._current_trades: List[dict] = []
        self._all_runs: List[dict] = []
        self._rollback_service = RollbackService()
        self._build()
        QTimer.singleShot(300, self.refresh)

    # ------------------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Results Browser")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        hdr.addWidget(title)
        hdr.addStretch()

        self._strategy_filter = QComboBox()
        self._strategy_filter.setMinimumWidth(160)
        self._strategy_filter.addItem("All Strategies")
        self._strategy_filter.currentTextChanged.connect(self._filter_runs)
        hdr.addWidget(QLabel("Strategy:"))
        hdr.addWidget(self._strategy_filter)
        hdr.addSpacing(8)

        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setObjectName("primary")
        refresh_btn.setFixedSize(100, 32)
        refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(refresh_btn)

        self._rollback_btn = QPushButton("⏪  Rollback")
        self._rollback_btn.setFixedSize(110, 32)
        self._rollback_btn.setVisible(False)
        self._rollback_btn.clicked.connect(self._on_rollback_clicked)
        hdr.addWidget(self._rollback_btn)

        root.addLayout(hdr)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {theme.BG_BORDER}; }}")

        # ── Run list ──────────────────────────────────────────────────
        list_panel = QFrame()
        list_panel.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
        """)
        list_panel.setMinimumWidth(320)
        list_panel.setMaximumWidth(420)
        ll = QVBoxLayout(list_panel)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        list_header = QWidget()
        list_header.setFixedHeight(40)
        list_header.setStyleSheet(
            f"background: {theme.BG_ELEVATED}; border-radius: 10px 10px 0 0;"
        )
        lhlay = QHBoxLayout(list_header)
        lhlay.setContentsMargins(12, 0, 12, 0)
        lhlay.addWidget(QLabel("Runs"))
        lhlay.addStretch()
        self._run_count_lbl = QLabel("0 runs")
        self._run_count_lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
        )
        lhlay.addWidget(self._run_count_lbl)
        ll.addWidget(list_header)

        self._run_table = QTableWidget()
        self._run_table.setColumnCount(4)
        self._run_table.setHorizontalHeaderLabels(["Strategy", "Profit", "WR%", "Date"])
        self._run_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._run_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._run_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._run_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._run_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._run_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._run_table.setAlternatingRowColors(True)
        self._run_table.verticalHeader().setVisible(False)
        self._run_table.setShowGrid(False)
        self._run_table.setStyleSheet(f"""
            QTableWidget {{
                background: {theme.BG_SURFACE};
                border: none;
                border-radius: 0 0 10px 10px;
                font-size: 12px;
            }}
            QTableWidget::item {{ padding: 6px 8px; border: none; }}
            QTableWidget::item:selected {{ background: {theme.ACCENT_DIM}; }}
            QHeaderView::section {{
                background: {theme.BG_ELEVATED};
                color: {theme.TEXT_MUTED};
                border: none;
                border-bottom: 1px solid {theme.BG_BORDER};
                padding: 6px 8px;
                font-size: 10px;
                font-weight: 600;
            }}
        """)
        self._run_table.currentCellChanged.connect(
            lambda row, *_: self._on_run_selected(row)
        )
        ll.addWidget(self._run_table)
        splitter.addWidget(list_panel)

        # ── Detail panel ──────────────────────────────────────────────
        detail_panel = QWidget()
        dl = QVBoxLayout(detail_panel)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(12)

        # Metric cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self._c_profit = StatCard("Total Profit",  "—", accent_color=theme.GREEN)
        self._c_wr     = StatCard("Win Rate",       "—", accent_color=theme.ACCENT)
        self._c_trades = StatCard("Trades",         "—", accent_color=theme.PURPLE)
        self._c_dd     = StatCard("Max Drawdown",   "—", accent_color=theme.YELLOW)
        self._c_sharpe = StatCard("Sharpe",         "—", accent_color=theme.ACCENT)
        self._c_pf     = StatCard("Profit Factor",  "—", accent_color=theme.GREEN)
        for c in [self._c_profit, self._c_wr, self._c_trades,
                  self._c_dd, self._c_sharpe, self._c_pf]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            c.setFixedHeight(100)
            cards_row.addWidget(c)
        dl.addLayout(cards_row)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {theme.TEXT_SECONDARY};
                padding: 8px 20px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 13px;
            }}
            QTabBar::tab:selected {{
                color: {theme.ACCENT};
                border-bottom: 2px solid {theme.ACCENT};
            }}
        """)

        # ── Charts tab ────────────────────────────────────────────────
        charts_tab = QWidget()
        ct_lay = QVBoxLayout(charts_tab)
        ct_lay.setContentsMargins(12, 12, 12, 12)
        ct_lay.setSpacing(12)

        charts_row1 = QHBoxLayout()
        eq_frame = self._card("Equity Curve")
        self._equity_chart = EquityCurveChart()
        self._equity_chart.setMinimumHeight(200)
        eq_frame.layout().addWidget(self._equity_chart)
        charts_row1.addWidget(eq_frame, 3)

        wr_frame = self._card("Win / Loss")
        self._wr_chart = WinRateDonut()
        self._wr_chart.setMinimumHeight(200)
        wr_frame.layout().addWidget(self._wr_chart)
        charts_row1.addWidget(wr_frame, 1)
        ct_lay.addLayout(charts_row1)

        charts_row2 = QHBoxLayout()
        pb_frame = self._card("Per-Trade Profit %")
        self._profit_chart = ProfitBarChart()
        self._profit_chart.setMinimumHeight(180)
        pb_frame.layout().addWidget(self._profit_chart)
        charts_row2.addWidget(pb_frame, 3)

        pair_frame = self._card("Profit by Pair")
        self._pair_chart = PairProfitChart()
        self._pair_chart.setMinimumHeight(180)
        pair_frame.layout().addWidget(self._pair_chart)
        charts_row2.addWidget(pair_frame, 2)
        ct_lay.addLayout(charts_row2)

        self._tabs.addTab(charts_tab, "📈  Charts")

        # ── Trades tab ────────────────────────────────────────────────
        trades_tab = QWidget()
        tt_lay = QVBoxLayout(trades_tab)
        tt_lay.setContentsMargins(12, 12, 12, 12)

        trades_filter_row = QHBoxLayout()
        trades_filter_row.setContentsMargins(0, 0, 0, 0)
        trades_filter_row.setSpacing(8)
        trades_filter_row.addWidget(QLabel("Pair:"))
        self._trade_pair_filter = QComboBox()
        self._trade_pair_filter.setMinimumWidth(180)
        self._trade_pair_filter.currentTextChanged.connect(lambda *_: self._render_trades_table())
        trades_filter_row.addWidget(self._trade_pair_filter)
        self._trade_filter_count = QLabel("0 trades")
        self._trade_filter_count.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
        )
        trades_filter_row.addWidget(self._trade_filter_count)
        trades_filter_row.addStretch()
        tt_lay.addLayout(trades_filter_row)

        self._trades_table = QTableWidget()
        self._trades_table.setColumnCount(9)
        self._trades_table.setHorizontalHeaderLabels(
            ["Pair", "Entry Date", "Exit Date",
             "Duration", "Entry Rate", "Exit Rate",
             "Profit %", "Profit Abs", "Exit Reason"]
        )
        self._trades_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._trades_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self._trades_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._trades_table.setAlternatingRowColors(True)
        self._trades_table.verticalHeader().setVisible(False)
        self._trades_table.setStyleSheet(f"""
            QTableWidget {{
                background: {theme.BG_SURFACE};
                border: none;
                font-size: 12px;
            }}
            QTableWidget::item {{ padding: 5px 8px; border: none; }}
            QTableWidget::item:selected {{ background: {theme.ACCENT_DIM}; }}
            QHeaderView::section {{
                background: {theme.BG_ELEVATED};
                color: {theme.TEXT_MUTED};
                border: none;
                border-bottom: 1px solid {theme.BG_BORDER};
                padding: 6px 8px;
                font-size: 10px;
                font-weight: 600;
            }}
        """)
        tt_lay.addWidget(self._trades_table)
        self._tabs.addTab(trades_tab, "📋  Trades")

        # ── Summary tab ───────────────────────────────────────────────
        summary_tab = QScrollArea()
        summary_tab.setWidgetResizable(True)
        summary_tab.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        self._summary_widget = QWidget()
        self._summary_layout = QVBoxLayout(self._summary_widget)
        self._summary_layout.setContentsMargins(16, 16, 16, 16)
        self._summary_layout.setSpacing(8)
        summary_tab.setWidget(self._summary_widget)
        self._tabs.addTab(summary_tab, "📄  Summary")

        dl.addWidget(self._tabs, 1)
        splitter.addWidget(detail_panel)
        splitter.setSizes([360, 900])

        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    def _card(self, title: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {theme.TEXT_SECONDARY};"
            " text-transform: uppercase;"
        )
        lay.addWidget(lbl)
        return f

    # ------------------------------------------------------------------
    def _balance_delta_widget(self, starting: float, final: float) -> QLabel | None:
        """Return a delta QLabel for the balance change, or None if equal."""
        if final > starting:
            delta = final - starting
            lbl = QLabel(f"+{delta:.2f} USDT")
            lbl.setStyleSheet(
                f"color: {theme.GREEN}; font-size: 12px; font-weight: 600;"
            )
            return lbl
        if final < starting:
            delta = starting - final
            lbl = QLabel(f"\u2212{delta:.2f} USDT")
            lbl.setStyleSheet(
                f"color: {theme.RED}; font-size: 12px; font-weight: 600;"
            )
            return lbl
        return None

    # ------------------------------------------------------------------
    def _build_pairs_widget(self, pairs: list) -> QWidget:
        """Return a flow-wrap badge widget for pairs, or a plain dash label."""
        from PySide6.QtWidgets import QGridLayout
        if not pairs:
            lbl = QLabel("—")
            lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
            return lbl

        container = QWidget()
        badge_style = (
            f"background: {theme.ACCENT_DIM}; color: {theme.ACCENT}; "
            "border-radius: 10px; padding: 2px 8px; "
            "font-size: 11px; font-weight: 600;"
        )
        badges: list = []
        for pair in pairs:
            badge = QLabel(pair)
            badge.setStyleSheet(badge_style)
            badge.setParent(container)
            badges.append(badge)

        def _reflow(event=None):
            """Reposition badge labels in a flow-wrap pattern."""
            if event is not None:
                QWidget.resizeEvent(container, event)
            x, y = 0, 0
            h_gap, v_gap = 6, 4
            row_height = 0
            w = container.width() or 400
            for badge in badges:
                badge.adjustSize()
                bw = badge.sizeHint().width()
                bh = badge.sizeHint().height()
                if x + bw > w and x > 0:
                    x = 0
                    y += row_height + v_gap
                    row_height = 0
                badge.setGeometry(x, y, bw, bh)
                x += bw + h_gap
                row_height = max(row_height, bh)
            total_h = y + row_height + v_gap
            container.setMinimumHeight(max(total_h, 28))

        container.resizeEvent = _reflow  # type: ignore[method-assign]
        _reflow()
        return container

    # ------------------------------------------------------------------
    def _summary_section(
        self,
        title: str,
        fields: list,
    ) -> QFrame:
        """Build a titled, bordered section card with a two-column grid of fields.

        Each field is a tuple of (label_text, value_text_or_widget, color_hex).
        The value element may be a plain str or a QWidget for inline composites.
        """
        from PySide6.QtWidgets import QGridLayout

        outer = QFrame()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(6)

        # Section header
        header = QLabel(title.upper())
        header.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px; font-weight: 600;"
        )
        outer_lay.addWidget(header)

        # Card body
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 8px;
            }}
        """)
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(1, 200)
        grid.setColumnMinimumWidth(3, 200)

        for i, field in enumerate(fields):
            label_text, value_item, color_hex = field
            col_offset = (i % 2) * 2  # 0 or 2
            row = i // 2

            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
            )
            grid.addWidget(lbl, row, col_offset)

            if isinstance(value_item, QWidget):
                grid.addWidget(value_item, row, col_offset + 1)
            else:
                val = QLabel(str(value_item))
                val.setStyleSheet(
                    f"color: {color_hex}; font-size: 13px; font-weight: 500;"
                )
                grid.addWidget(val, row, col_offset + 1)

        outer_lay.addWidget(card)
        return outer

    # ------------------------------------------------------------------
    def _build_kpi_row(self, run: dict) -> QWidget:
        """Return a QWidget containing a horizontal row of six StatCards."""
        container = QWidget()
        hlay = QHBoxLayout(container)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(10)

        profit_v = run.get("profit_total_pct", 0.0) or 0.0
        wr_v = run.get("win_rate_pct", 0.0) or 0.0
        trades_v = run.get("trades_count", 0)
        dd_v = run.get("max_drawdown_pct", 0.0) or 0.0
        sharpe_v = run.get("sharpe", None)
        pf_v = run.get("profit_factor", 0.0) or 0.0

        cards_def = [
            ("Total Profit %",  f"{profit_v:+.2f}%",                    _profit_accent_color(profit_v)),
            ("Win Rate",        f"{wr_v:.1f}%",                          theme.ACCENT),
            ("Total Trades",    str(trades_v),                           theme.PURPLE),
            ("Max Drawdown %",  f"{dd_v:.2f}%",                          _drawdown_accent_color(dd_v)),
            ("Sharpe Ratio",    f"{sharpe_v:.3f}" if sharpe_v is not None else "—", theme.ACCENT),
            ("Profit Factor",   f"{pf_v:.3f}" if pf_v else "—",          theme.GREEN),
        ]

        for label, value, accent in cards_def:
            card = StatCard(label, value, accent_color=accent)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            card.setFixedHeight(100)
            hlay.addWidget(card)

        return container

    # ------------------------------------------------------------------
    def _clear_summary_layout(self) -> None:
        """Remove all widgets from _summary_layout."""
        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ------------------------------------------------------------------
    def refresh(self):
        settings = self._state.current_settings
        if not settings or not settings.user_data_path:
            return
        try:
            br_dir = str(Path(settings.user_data_path) / "backtest_results")
            index = IndexStore.load(br_dir)
            self._all_runs = []
            strategies: set = set()
            for strat, sdata in index.get("strategies", {}).items():
                strategies.add(strat)
                for run in sdata.get("runs", []):
                    run = dict(run)          # don't mutate the cached index
                    run["_br_dir"] = br_dir
                    self._all_runs.append(run)

            self._all_runs.sort(
                key=lambda r: r.get("saved_at", ""), reverse=True
            )

            # Deduplicate by run_id (global index may list same run twice)
            seen: set = set()
            deduped = []
            for r in self._all_runs:
                rid = r.get("run_id", "")
                if rid and rid in seen:
                    continue
                seen.add(rid)
                deduped.append(r)
            self._all_runs = deduped

            # Update strategy filter
            current = self._strategy_filter.currentText()
            self._strategy_filter.blockSignals(True)
            self._strategy_filter.clear()
            self._strategy_filter.addItem("All Strategies")
            for s in sorted(strategies):
                self._strategy_filter.addItem(s)
            idx = self._strategy_filter.findText(current)
            self._strategy_filter.setCurrentIndex(max(0, idx))
            self._strategy_filter.blockSignals(False)

            self._filter_runs(self._strategy_filter.currentText())
        except Exception as e:
            _log.warning("Results refresh error: %s", e)

    # ------------------------------------------------------------------
    def _filter_runs(self, strategy: str):
        if strategy == "All Strategies":
            runs = self._all_runs
        else:
            runs = [r for r in self._all_runs if r.get("strategy") == strategy]

        self._run_count_lbl.setText(f"{len(runs)} runs")
        self._run_table.blockSignals(True)
        self._run_table.setRowCount(0)
        for run in runs:
            row = self._run_table.rowCount()
            self._run_table.insertRow(row)
            profit = run.get("profit_total_pct", 0)
            profit_color = theme.GREEN if profit >= 0 else theme.RED

            items = [
                (run.get("strategy", "—"),       theme.TEXT_PRIMARY),
                (f"{profit:+.2f}%",              profit_color),
                (f"{run.get('win_rate_pct', 0):.1f}%", theme.TEXT_PRIMARY),
                (run.get("saved_at", "")[:10],   theme.TEXT_MUTED),
            ]
            for col, (text, color) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                item.setData(Qt.UserRole, run)
                self._run_table.setItem(row, col, item)

        self._run_table.blockSignals(False)
        if runs:
            self._run_table.selectRow(0)
            self._on_run_selected(0)

    # ------------------------------------------------------------------
    def _on_run_selected(self, row: int):
        if row < 0:
            self._rollback_btn.setVisible(False)
            return
        item = self._run_table.item(row, 0)
        if not item:
            self._rollback_btn.setVisible(False)
            return
        run = item.data(Qt.UserRole)
        if run:
            self._load_run_detail(run)
            self._update_rollback_button(run)

    # ------------------------------------------------------------------
    def _update_rollback_button(self, run: dict) -> None:
        """Show/enable/disable the rollback button based on run and settings state."""
        settings = self._state.current_settings
        br_dir = run.get("_br_dir", "")
        run_dir = _run_dir_path(br_dir, run)

        self._rollback_btn.setVisible(True)

        user_data_path = settings.user_data_path if settings else None
        if not user_data_path:
            self._rollback_btn.setEnabled(False)
            self._rollback_btn.setToolTip("user_data path not configured")
            return

        has_params = (run_dir / "params.json").exists()
        has_config = (run_dir / "config.snapshot.json").exists()

        if not has_params and not has_config:
            self._rollback_btn.setEnabled(False)
            self._rollback_btn.setToolTip("No restorable files found")
            return

        self._rollback_btn.setEnabled(True)
        self._rollback_btn.setToolTip("")

    # ------------------------------------------------------------------
    def _on_rollback_clicked(self) -> None:
        """Handle Rollback button click — open dialog, call service, show feedback."""
        if self._current_run is None:
            return

        settings = self._state.current_settings
        if not settings or not settings.user_data_path:
            return

        run = self._current_run
        br_dir = run.get("_br_dir", "")
        run_dir = _run_dir_path(br_dir, run)
        strategy_name = run.get("strategy", "")
        run_id = run.get("run_id", run_dir.name)
        user_data_path = Path(settings.user_data_path)

        has_params = (run_dir / "params.json").exists()
        has_config = (run_dir / "config.snapshot.json").exists()
        params_path = user_data_path / "strategies" / f"{strategy_name}.json"
        config_path = user_data_path / "config.json"

        dlg = RollbackDialog(
            strategy_name=strategy_name,
            run_id=run_id,
            has_params=has_params,
            has_config=has_config,
            params_path=params_path,
            config_path=config_path,
            parent=self,
        )

        if dlg.exec() != QDialog.Accepted:
            _log.debug("Rollback cancelled by user")
            return

        try:
            result = self._rollback_service.rollback(
                run_dir=run_dir,
                user_data_path=user_data_path,
                strategy_name=strategy_name,
                restore_params=dlg.restore_params,
                restore_config=dlg.restore_config,
            )

            # Build success message
            restored_files = []
            if result.params_restored and result.params_path:
                restored_files.append(str(result.params_path))
            if result.config_restored and result.config_path:
                restored_files.append(str(result.config_path))

            files_str = "\n".join(f"  • {f}" for f in restored_files)
            msg = (
                f"Rollback successful!\n\n"
                f"Rolled back to: {result.rolled_back_to}\n\n"
                f"Restored files:\n{files_str}"
            )
            QMessageBox.information(self, "Rollback Complete", msg)

        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Rollback Failed", f"Run directory not found: {exc}")
        except ValueError as exc:
            QMessageBox.critical(self, "Rollback Failed", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Rollback Failed", f"Unexpected error: {exc}")

    # ------------------------------------------------------------------
    def _load_run_detail(self, run: dict):
        self._current_run = run
        br_dir = run.get("_br_dir", "")
        run_dir = _run_dir_path(br_dir, run)

        _log.debug("Loading run detail from: %s  (exists=%s)", run_dir, run_dir.exists())

        # ── Stat cards ────────────────────────────────────────────────
        profit = run.get("profit_total_pct", 0)
        self._c_profit.set_value(f"{profit:+.2f}%", positive=profit >= 0)
        self._c_wr.set_value(f"{run.get('win_rate_pct', 0):.1f}%")
        self._c_trades.set_value(str(run.get("trades_count", 0)))
        self._c_dd.set_value(f"{run.get('max_drawdown_pct', 0):.2f}%")
        sharpe = run.get("sharpe")
        self._c_sharpe.set_value(f"{sharpe:.3f}" if sharpe is not None else "—")
        pf = run.get("profit_factor", 0)
        self._c_pf.set_value(f"{pf:.3f}" if pf else "—")

        # ── Load trades ───────────────────────────────────────────────
        trades = []
        trades_file = run_dir / "trades.json"
        if trades_file.exists():
            try:
                from app.core.parsing.json_parser import parse_json_file
                trades = parse_json_file(trades_file)
                _log.debug("Loaded %d trades from %s", len(trades), trades_file)
            except Exception as exc:
                _log.warning("Failed to load trades: %s", exc)
        else:
            _log.warning("trades.json not found at %s", trades_file)

        # ── Charts ────────────────────────────────────────────────────
        if trades:
            profits = [_trade_profit(t) for t in trades]
            equity  = [sum(profits[:i + 1]) for i in range(len(profits))]
            self._equity_chart.set_data(equity)
            self._profit_chart.set_data(profits)

            wins   = sum(1 for p in profits if p > 0)
            losses = sum(1 for p in profits if p < 0)
            draws  = len(profits) - wins - losses
            self._wr_chart.set_data(wins, losses, draws)

            pair_profits: Dict[str, float] = {}
            for t in trades:
                pair = t.get("pair", "?")
                pair_profits[pair] = pair_profits.get(pair, 0) + _trade_profit(t)
            sorted_pairs = sorted(pair_profits.items(), key=lambda x: x[1])
            if sorted_pairs:
                pairs_list, pvals = zip(*sorted_pairs)
                self._pair_chart.set_data(list(pairs_list), list(pvals))

        self._current_trades = trades
        self._populate_trade_pair_filter(trades)
        self._render_trades_table()

        # ── Summary ───────────────────────────────────────────────────
        self._build_summary(run)

    # ------------------------------------------------------------------
    def _populate_trade_pair_filter(self, trades: List[dict]) -> None:
        """Refresh the per-pair filter for the currently loaded run."""
        pairs = sorted({str(t.get("pair", "")) for t in trades if t.get("pair")})

        self._trade_pair_filter.blockSignals(True)
        self._trade_pair_filter.clear()
        self._trade_pair_filter.addItem("All Pairs")
        for pair in pairs:
            self._trade_pair_filter.addItem(pair)
        self._trade_pair_filter.setCurrentIndex(0)
        self._trade_pair_filter.blockSignals(False)

    # ------------------------------------------------------------------
    def _filtered_trades(self) -> List[dict]:
        selected_pair = self._trade_pair_filter.currentText()
        if not selected_pair or selected_pair == "All Pairs":
            return list(self._current_trades)
        return [
            trade for trade in self._current_trades
            if str(trade.get("pair", "")) == selected_pair
        ]

    # ------------------------------------------------------------------
    def _render_trades_table(self) -> None:
        """Render the trades table for the selected pair filter."""
        trades = self._filtered_trades()
        self._trades_table.setRowCount(0)
        for t in trades:
            profit_pct = _trade_profit(t)
            profit_abs = _trade_profit_abs(t)
            duration = _trade_duration_min(t)
            color = theme.GREEN if profit_pct >= 0 else theme.RED

            row = self._trades_table.rowCount()
            self._trades_table.insertRow(row)
            cells = [
                (t.get("pair", ""),                    theme.TEXT_PRIMARY),
                (_trade_open_date(t),                  theme.TEXT_SECONDARY),
                (_trade_close_date(t),                 theme.TEXT_SECONDARY),
                (_format_duration(duration),            theme.TEXT_SECONDARY),
                (f"{_trade_open_rate(t):.6f}",         theme.TEXT_PRIMARY),
                (f"{_trade_close_rate(t):.6f}",        theme.TEXT_PRIMARY),
                (f"{profit_pct:+.4f}%",                color),
                (f"{profit_abs:+.4f}",                 color),
                (t.get("exit_reason", ""),             theme.TEXT_MUTED),
            ]
            for col, (text, c) in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(c))
                self._trades_table.setItem(row, col, item)

        total = len(self._current_trades)
        shown = len(trades)
        self._trade_filter_count.setText(
            f"{shown} of {total} trades" if shown != total else f"{total} trades"
        )

    # ------------------------------------------------------------------
    def _build_summary(self, run: dict) -> None:
        """Rebuild the Summary tab content for the given run dict."""
        self._clear_summary_layout()
        try:
            # ── Overview section ──────────────────────────────────────
            overview_fields = [
                ("Strategy",      run.get("strategy", "—"),                          theme.TEXT_PRIMARY),
                ("Timeframe",     run.get("timeframe", "—"),                         theme.TEXT_PRIMARY),
                ("Timerange",     run.get("timerange", "—"),                         theme.TEXT_PRIMARY),
                ("Backtest Start",run.get("backtest_start", "—"),                    theme.TEXT_PRIMARY),
                ("Backtest End",  run.get("backtest_end", "—"),                      theme.TEXT_PRIMARY),
                ("Pairs",         self._build_pairs_widget(run.get("pairs", [])),    theme.TEXT_PRIMARY),
                ("Run ID",        run.get("run_id", "—"),                            theme.TEXT_PRIMARY),
                ("Saved At",      run.get("saved_at", "—")[:19].replace("T", " "),  theme.TEXT_PRIMARY),
            ]
            self._summary_layout.addWidget(self._summary_section("Overview", overview_fields))

            # ── Performance section ───────────────────────────────────
            starting = run.get("starting_balance", 0.0) or 0.0
            final    = run.get("final_balance", 0.0) or 0.0
            profit_pct = run.get("profit_total_pct", 0.0) or 0.0
            profit_abs = run.get("profit_total_abs", 0.0) or 0.0
            pf_v       = run.get("profit_factor", 0.0) or 0.0
            exp_v      = run.get("expectancy", 0.0) or 0.0

            # Build Final Balance composite widget (value + optional delta)
            delta_lbl = self._balance_delta_widget(starting, final)
            if delta_lbl is not None:
                final_container = QWidget()
                final_hlay = QHBoxLayout(final_container)
                final_hlay.setContentsMargins(0, 0, 0, 0)
                final_hlay.setSpacing(8)
                final_val_lbl = QLabel(f"{final:.2f} USDT")
                final_val_lbl.setStyleSheet(
                    f"color: {theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 500;"
                )
                final_hlay.addWidget(final_val_lbl)
                final_hlay.addWidget(delta_lbl)
                final_hlay.addStretch()
                final_value: object = final_container
            else:
                final_value = f"{final:.2f} USDT"

            perf_fields = [
                ("Starting Balance", f"{starting:.2f} USDT",                    theme.TEXT_PRIMARY),
                ("Final Balance",    final_value,                                theme.TEXT_PRIMARY),
                ("Total Profit %",   f"{profit_pct:+.2f}%",                     _profit_color(profit_pct)),
                ("Total Profit Abs", f"{profit_abs:+.4f}",                      _profit_color(profit_abs)),
                ("Profit Factor",    f"{pf_v:.3f}",                             _profit_factor_color(pf_v)),
                ("Expectancy",       f"{exp_v:.4f}",                            _profit_color(exp_v)),
            ]
            self._summary_layout.addWidget(self._summary_section("Performance", perf_fields))

            # ── Trade Statistics section ──────────────────────────────
            wr_v = run.get("win_rate_pct", 0.0) or 0.0
            trade_fields = [
                ("Total Trades", str(run.get("trades_count", 0)),  theme.TEXT_PRIMARY),
                ("Wins",         str(run.get("wins", 0)),           theme.TEXT_PRIMARY),
                ("Losses",       str(run.get("losses", 0)),         theme.TEXT_PRIMARY),
                ("Win Rate",     f"{wr_v:.1f}%",                    _win_rate_color(wr_v)),
            ]
            self._summary_layout.addWidget(self._summary_section("Trade Statistics", trade_fields))

            # ── Risk Metrics section ──────────────────────────────────
            sharpe_v  = run.get("sharpe", None)
            sortino_v = run.get("sortino", None)
            calmar_v  = run.get("calmar", None)
            dd_pct    = run.get("max_drawdown_pct", 0.0) or 0.0
            dd_abs    = run.get("max_drawdown_abs", 0.0) or 0.0

            risk_fields = [
                ("Max Drawdown %",   f"{dd_pct:.2f}%",                                          theme.RED),
                ("Max Drawdown Abs", f"{dd_abs:.4f}",                                           theme.RED),
                ("Sharpe Ratio",     f"{sharpe_v:.3f}" if sharpe_v is not None else "—",        _sharpe_color(sharpe_v) if sharpe_v is not None else theme.TEXT_PRIMARY),
                ("Sortino Ratio",    f"{sortino_v:.3f}" if sortino_v is not None else "—",      _sharpe_color(sortino_v) if sortino_v is not None else theme.TEXT_PRIMARY),
                ("Calmar Ratio",     f"{calmar_v:.3f}" if calmar_v is not None else "—",        theme.TEXT_PRIMARY),
            ]
            self._summary_layout.addWidget(self._summary_section("Risk Metrics", risk_fields))

            self._summary_layout.addStretch()

        except Exception as exc:
            _log.warning("_build_summary failed: %s", exc)
