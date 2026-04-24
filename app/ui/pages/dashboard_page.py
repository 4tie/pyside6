"""Dashboard page — overview of recent runs and key metrics."""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_index import IndexStore
from app.ui import theme
from app.ui.widgets.stat_card import StatCard
from app.ui.widgets.charts import EquityCurveChart, ProfitBarChart
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.dashboard")


class DashboardPage(QWidget):
    def __init__(self, settings_state: SettingsState, parent: QWidget | None = None):
        super().__init__(parent)
        self._state = settings_state
        self._build()
        QTimer.singleShot(200, self.refresh)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        hdr.addWidget(title)
        hdr.addStretch()
        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setObjectName("primary")
        refresh_btn.setFixedSize(100, 32)
        refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(refresh_btn)
        root.addLayout(hdr)

        # Stat cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self._card_runs    = StatCard("Total Runs",    "—", accent_color=theme.ACCENT)
        self._card_profit  = StatCard("Best Profit",   "—", accent_color=theme.GREEN)
        self._card_wr      = StatCard("Best Win Rate", "—", accent_color=theme.PURPLE)
        self._card_dd      = StatCard("Min Drawdown",  "—", accent_color=theme.YELLOW)
        for c in [self._card_runs, self._card_profit, self._card_wr, self._card_dd]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            c.setFixedHeight(110)
            cards_row.addWidget(c)
        root.addLayout(cards_row)

        # Charts row
        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)

        # Equity curve
        eq_frame = self._make_card("Equity Curve (latest run)")
        self._equity_chart = EquityCurveChart()
        self._equity_chart.setMinimumHeight(220)
        eq_frame.layout().addWidget(self._equity_chart)
        charts_row.addWidget(eq_frame, 3)

        # Profit bars
        pb_frame = self._make_card("Per-Trade Profit (latest run)")
        self._profit_chart = ProfitBarChart()
        self._profit_chart.setMinimumHeight(220)
        pb_frame.layout().addWidget(self._profit_chart)
        charts_row.addWidget(pb_frame, 2)

        root.addLayout(charts_row)

        # Recent runs table
        recent_frame = self._make_card("Recent Runs")
        self._recent_layout = QVBoxLayout()
        self._recent_layout.setSpacing(4)
        recent_frame.layout().addLayout(self._recent_layout)
        root.addWidget(recent_frame)

        root.addStretch()

    def _make_card(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("surface")
        frame.setStyleSheet(f"""
            QFrame#surface {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 16)
        lay.setSpacing(10)
        lbl = QLabel(title)
        lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme.TEXT_SECONDARY}; text-transform: uppercase; letter-spacing: 1px;")
        lay.addWidget(lbl)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {theme.BG_BORDER};")
        lay.addWidget(sep)
        return frame

    def refresh(self):
        settings = self._state.current_settings
        if not settings or not settings.user_data_path:
            return
        try:
            br_dir = str(Path(settings.user_data_path) / "backtest_results")
            index = IndexStore.load(br_dir)
            all_runs = []
            for strat, sdata in index.get("strategies", {}).items():
                all_runs.extend(sdata.get("runs", []))

            if not all_runs:
                return

            all_runs.sort(key=lambda r: r.get("saved_at", ""), reverse=True)

            # Update stat cards
            self._card_runs.set_value(str(len(all_runs)))
            profits = [r.get("profit_total_pct", 0) for r in all_runs]
            best_profit = max(profits)
            self._card_profit.set_value(
                f"{best_profit:+.2f}%",
                positive=best_profit >= 0
            )
            win_rates = [r.get("win_rate_pct", 0) for r in all_runs]
            self._card_wr.set_value(f"{max(win_rates):.1f}%")
            drawdowns = [r.get("max_drawdown_pct", 0) for r in all_runs]
            self._card_dd.set_value(f"{min(drawdowns):.2f}%")

            # Load latest run trades for charts
            latest = all_runs[0]
            strategy = latest.get("strategy", "")
            run_id   = latest.get("run_id", "")
            run_dir  = Path(br_dir) / strategy / run_id if (strategy and run_id) else \
                       Path(br_dir) / Path(latest.get("run_dir", "").replace("\\", "/"))
            trades_file = run_dir / "trades.json"
            if trades_file.exists():
                from app.core.parsing.json_parser import parse_json_file
                trades = parse_json_file(trades_file)
                # Support both field name variants: profit_pct (new) and profit (old)
                profits_list = [t.get("profit_pct", t.get("profit", 0)) for t in trades]
                if profits_list:
                    equity = [sum(profits_list[:i+1]) for i in range(len(profits_list))]
                    self._equity_chart.set_data(equity)
                    self._profit_chart.set_data(profits_list)

            # Recent runs list
            self._clear_layout(self._recent_layout)
            header = self._make_row_header()
            self._recent_layout.addWidget(header)
            for run in all_runs[:10]:
                row = self._make_run_row(run)
                self._recent_layout.addWidget(row)

        except Exception as e:
            _log.warning("Dashboard refresh error: %s", e)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _make_row_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {theme.BG_ELEVATED}; border-radius: 4px;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 6, 10, 6)
        for col, width in [("Strategy", 140), ("Timeframe", 80), ("Profit", 90), ("Win Rate", 80), ("Trades", 70), ("Drawdown", 90), ("Date", 140)]:
            lbl = QLabel(col.upper())
            lbl.setFixedWidth(width)
            lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10px; font-weight: 600; letter-spacing: 0.5px;")
            lay.addWidget(lbl)
        lay.addStretch()
        return w

    def _make_run_row(self, run: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"""
            QWidget {{ background: transparent; border-radius: 4px; }}
            QWidget:hover {{ background: {theme.BG_ELEVATED}; }}
        """)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 6, 10, 6)

        profit = run.get("profit_total_pct", 0)
        profit_color = theme.GREEN if profit >= 0 else theme.RED

        def cell(text, width, color=theme.TEXT_PRIMARY, bold=False):
            lbl = QLabel(str(text))
            lbl.setFixedWidth(width)
            lbl.setStyleSheet(f"color: {color}; font-size: 12px; {'font-weight: 600;' if bold else ''}")
            return lbl

        lay.addWidget(cell(run.get("strategy", "—"), 140, bold=True))
        lay.addWidget(cell(run.get("timeframe", "—"), 80, theme.TEXT_SECONDARY))
        lay.addWidget(cell(f"{profit:+.2f}%", 90, profit_color, bold=True))
        lay.addWidget(cell(f"{run.get('win_rate_pct', 0):.1f}%", 80))
        lay.addWidget(cell(str(run.get("trades_count", 0)), 70, theme.TEXT_SECONDARY))
        lay.addWidget(cell(f"{run.get('max_drawdown_pct', 0):.2f}%", 90, theme.YELLOW))
        saved = run.get("saved_at", "")[:16].replace("T", " ")
        lay.addWidget(cell(saved, 140, theme.TEXT_MUTED))
        lay.addStretch()
        return w
