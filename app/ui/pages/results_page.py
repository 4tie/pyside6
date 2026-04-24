"""Results browser — browse, view, and analyze backtest runs."""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QFrame, QTabWidget, QScrollArea, QSizePolicy,
    QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_index import IndexStore
from app.ui import theme
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


class ResultsPage(QWidget):
    def __init__(self, settings_state: SettingsState, parent: QWidget | None = None):
        super().__init__(parent)
        self._state = settings_state
        self._current_run: Optional[dict] = None
        self._all_runs: List[dict] = []
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
        self._trades_table = QTableWidget()
        self._trades_table.setColumnCount(8)
        self._trades_table.setHorizontalHeaderLabels(
            ["Pair", "Entry Date", "Exit Date",
             "Entry Rate", "Exit Rate", "Profit %", "Profit Abs", "Exit Reason"]
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
            return
        item = self._run_table.item(row, 0)
        if not item:
            return
        run = item.data(Qt.UserRole)
        if run:
            self._load_run_detail(run)

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

        # ── Trades table ──────────────────────────────────────────────
        self._trades_table.setRowCount(0)
        for t in trades:
            profit_pct = _trade_profit(t)
            profit_abs = _trade_profit_abs(t)
            color = theme.GREEN if profit_pct >= 0 else theme.RED

            row = self._trades_table.rowCount()
            self._trades_table.insertRow(row)
            cells = [
                (t.get("pair", ""),                    theme.TEXT_PRIMARY),
                (_trade_open_date(t),                  theme.TEXT_SECONDARY),
                (_trade_close_date(t),                 theme.TEXT_SECONDARY),
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

        # ── Summary ───────────────────────────────────────────────────
        self._build_summary(run)

    # ------------------------------------------------------------------
    def _build_summary(self, run: dict):
        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        fields = [
            ("Strategy",         run.get("strategy", "—")),
            ("Timeframe",        run.get("timeframe", "—")),
            ("Timerange",        run.get("timerange", "—")),
            ("Backtest Start",   run.get("backtest_start", "—")),
            ("Backtest End",     run.get("backtest_end", "—")),
            ("Starting Balance", f"{run.get('starting_balance', 0):.2f} USDT"),
            ("Final Balance",    f"{run.get('final_balance', 0):.2f} USDT"),
            ("Total Profit %",   f"{run.get('profit_total_pct', 0):+.4f}%"),
            ("Total Profit Abs", f"{run.get('profit_total_abs', 0):+.4f}"),
            ("Max Drawdown %",   f"{run.get('max_drawdown_pct', 0):.4f}%"),
            ("Max Drawdown Abs", f"{run.get('max_drawdown_abs', 0):.4f}"),
            ("Total Trades",     str(run.get("trades_count", 0))),
            ("Wins",             str(run.get("wins", 0))),
            ("Losses",           str(run.get("losses", 0))),
            ("Win Rate",         f"{run.get('win_rate_pct', 0):.2f}%"),
            ("Sharpe Ratio",     f"{run.get('sharpe', 0) or 0:.4f}"),
            ("Sortino Ratio",    f"{run.get('sortino', 0) or 0:.4f}"),
            ("Calmar Ratio",     f"{run.get('calmar', 0) or 0:.4f}"),
            ("Profit Factor",    f"{run.get('profit_factor', 0):.4f}"),
            ("Expectancy",       f"{run.get('expectancy', 0):.4f}"),
            ("Pairs",            ", ".join(run.get("pairs", []))),
            ("Run ID",           run.get("run_id", "—")),
            ("Saved At",         run.get("saved_at", "—")[:19].replace("T", " ")),
        ]

        for label, value in fields:
            row_lay = QHBoxLayout()
            lbl = QLabel(label + ":")
            lbl.setFixedWidth(160)
            lbl.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 12px;"
            )
            val = QLabel(value)
            val.setStyleSheet(
                f"color: {theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 500;"
            )
            val.setWordWrap(True)
            row_lay.addWidget(lbl)
            row_lay.addWidget(val, 1)
            self._summary_layout.addLayout(row_lay)

        self._summary_layout.addStretch()
