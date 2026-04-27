"""Compare page — side-by-side comparison of two backtest runs."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QScrollArea, QSizePolicy, QGridLayout
)
from PySide6.QtCore import Qt

from app.app_state.settings_state import SettingsState
from app.core.backtests.results_index import IndexStore
from app.ui import theme
from app.ui.widgets.stat_card import StatCard
from app.ui.widgets.charts import ComparisonBarChart, EquityCurveChart
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.compare")


class ComparePage(QWidget):
    def __init__(self, settings_state: SettingsState, parent: QWidget | None = None):
        super().__init__(parent)
        self._state = settings_state
        self._runs: list = []
        self._loaded = False
        self._build()

    def showEvent(self, event):
        """Auto-load runs the first time the page becomes visible."""
        super().showEvent(event)
        if not self._loaded:
            self._load_runs()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Compare Runs")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        hdr.addWidget(title)
        hdr.addStretch()
        load_btn = QPushButton("↻  Reload Runs")
        load_btn.setObjectName("primary")
        load_btn.setFixedSize(120, 32)
        load_btn.clicked.connect(self._force_reload)
        hdr.addWidget(load_btn)
        root.addLayout(hdr)

        # Run selectors
        sel_frame = QFrame()
        sel_frame.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
        """)
        sl = QHBoxLayout(sel_frame)
        sl.setContentsMargins(16, 12, 16, 12)
        sl.setSpacing(16)

        sl.addWidget(QLabel("Run A:"))
        self._combo_a = QComboBox()
        self._combo_a.setMinimumWidth(300)
        sl.addWidget(self._combo_a)

        sl.addWidget(QLabel("vs"))

        sl.addWidget(QLabel("Run B:"))
        self._combo_b = QComboBox()
        self._combo_b.setMinimumWidth(300)
        sl.addWidget(self._combo_b)

        sl.addStretch()
        compare_btn = QPushButton("⇄  Compare")
        compare_btn.setObjectName("primary")
        compare_btn.setFixedSize(100, 32)
        compare_btn.clicked.connect(self._compare)
        sl.addWidget(compare_btn)
        root.addWidget(sel_frame)

        # Results area (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(16)
        scroll.setWidget(self._results_widget)
        root.addWidget(scroll, 1)

        self._placeholder = QLabel("Select two runs above and click Compare")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 14px;")
        self._results_layout.addWidget(self._placeholder)
        self._results_layout.addStretch()

    def _load_runs(self):
        settings = self._state.current_settings
        if not settings or not settings.user_data_path:
            return
        try:
            br_dir = str(Path(settings.user_data_path) / "backtest_results")
            index = IndexStore.load(br_dir)
            self._runs = []
            seen: set = set()
            for strat, sdata in index.get("strategies", {}).items():
                for run in sdata.get("runs", []):
                    run_id = run.get("run_id", "")
                    if run_id and run_id in seen:
                        continue
                    seen.add(run_id)
                    run = dict(run)
                    run["_br_dir"] = br_dir
                    self._runs.append(run)

            self._runs.sort(key=lambda r: r.get("saved_at", ""), reverse=True)
            self._loaded = True

            def run_label(r: dict) -> str:
                profit = r.get("profit_total_pct", 0)
                date   = r.get("saved_at", "")[:10]
                strat  = r.get("strategy", "?")
                return f"{strat}  |  {profit:+.2f}%  |  {date}"

            self._combo_a.clear()
            self._combo_b.clear()
            for r in self._runs:
                lbl = run_label(r)
                self._combo_a.addItem(lbl)
                self._combo_b.addItem(lbl)
            if len(self._runs) > 1:
                self._combo_b.setCurrentIndex(1)

            # Update placeholder
            self._placeholder.setText(
                f"{len(self._runs)} runs loaded — select two and click Compare"
            )
        except Exception as e:
            _log.warning("Load runs error: %s", e)

    def _force_reload(self):
        self._loaded = False
        self._load_runs()

    def _compare(self):
        idx_a = self._combo_a.currentIndex()
        idx_b = self._combo_b.currentIndex()
        if idx_a < 0 or idx_b < 0 or idx_a >= len(self._runs) or idx_b >= len(self._runs):
            return
        run_a = self._runs[idx_a]
        run_b = self._runs[idx_b]
        self._render_comparison(run_a, run_b)

    def _render_comparison(self, run_a: dict, run_b: dict):
        # Clear
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Header row
        hdr = QHBoxLayout()
        hdr.addStretch()
        for run, color in [(run_a, theme.ACCENT), (run_b, theme.GREEN)]:
            lbl = QLabel(f"{run.get('strategy','?')} — {run.get('saved_at','')[:10]}")
            lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")
            lbl.setAlignment(Qt.AlignCenter)
            hdr.addWidget(lbl, 1)
        self._results_layout.addLayout(hdr)

        # Metric comparison grid
        metrics = [
            ("Total Profit %",  "profit_total_pct",  True,  "{:+.4f}%"),
            ("Win Rate %",      "win_rate_pct",       True,  "{:.2f}%"),
            ("Max Drawdown %",  "max_drawdown_pct",   False, "{:.4f}%"),
            ("Total Trades",    "trades_count",       None,  "{}"),
            ("Wins",            "wins",               True,  "{}"),
            ("Losses",          "losses",             False, "{}"),
            ("Sharpe Ratio",    "sharpe",             True,  "{:.4f}"),
            ("Sortino Ratio",   "sortino",            True,  "{:.4f}"),
            ("Calmar Ratio",    "calmar",             True,  "{:.4f}"),
            ("Profit Factor",   "profit_factor",      True,  "{:.4f}"),
            ("Expectancy",      "expectancy",         True,  "{:.4f}"),
            ("Final Balance",   "final_balance",      True,  "{:.2f}"),
        ]

        grid_frame = QFrame()
        grid_frame.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
        """)
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setSpacing(0)

        # Column headers
        for col, (text, color) in enumerate([("Metric", theme.TEXT_MUTED), ("Run A", theme.ACCENT), ("Run B", theme.GREEN), ("Delta", theme.TEXT_PRIMARY)]):
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 700; padding: 6px 12px; letter-spacing: 1px;")
            grid.addWidget(lbl, 0, col)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {theme.BG_BORDER};")
        grid.addWidget(sep, 1, 0, 1, 4)

        for row_idx, (label, key, higher_better, fmt) in enumerate(metrics):
            val_a = run_a.get(key) or 0
            val_b = run_b.get(key) or 0
            try:
                str_a = fmt.format(val_a)
                str_b = fmt.format(val_b)
                delta = val_b - val_a
                str_delta = f"{delta:+.4f}" if isinstance(delta, float) else f"{delta:+d}"
            except Exception:
                str_a = str(val_a)
                str_b = str(val_b)
                str_delta = "—"
                delta = 0

            bg = theme.BG_ELEVATED if row_idx % 2 == 0 else "transparent"

            def cell(text, color, bold=False):
                lbl = QLabel(text)
                lbl.setStyleSheet(f"color: {color}; font-size: 12px; {'font-weight: 600;' if bold else ''} padding: 7px 12px; background: {bg};")
                return lbl

            grid.addWidget(cell(label, theme.TEXT_SECONDARY), row_idx + 2, 0)
            grid.addWidget(cell(str_a, theme.ACCENT, bold=True), row_idx + 2, 1)
            grid.addWidget(cell(str_b, theme.GREEN, bold=True), row_idx + 2, 2)

            if higher_better is not None:
                improved = (delta > 0) == higher_better
                delta_color = theme.GREEN if improved else theme.RED
            else:
                delta_color = theme.TEXT_PRIMARY
            grid.addWidget(cell(str_delta, delta_color, bold=True), row_idx + 2, 3)

        self._results_layout.addWidget(grid_frame)

        # Comparison bar chart
        chart_frame = QFrame()
        chart_frame.setStyleSheet(f"""
            QFrame {{
                background: {theme.BG_SURFACE};
                border: 1px solid {theme.BG_BORDER};
                border-radius: 10px;
            }}
        """)
        cl = QVBoxLayout(chart_frame)
        cl.setContentsMargins(12, 10, 12, 12)
        cl.addWidget(QLabel("Key Metrics Comparison"))
        chart = ComparisonBarChart()
        chart.setMinimumHeight(240)
        chart.set_data(
            labels=["Profit %", "Win Rate %", "Profit Factor", "Expectancy"],
            values_a=[run_a.get("profit_total_pct", 0), run_a.get("win_rate_pct", 0),
                      run_a.get("profit_factor", 0), run_a.get("expectancy", 0)],
            values_b=[run_b.get("profit_total_pct", 0), run_b.get("win_rate_pct", 0),
                      run_b.get("profit_factor", 0), run_b.get("expectancy", 0)],
            name_a=f"Run A ({run_a.get('strategy','?')})",
            name_b=f"Run B ({run_b.get('strategy','?')})",
        )
        cl.addWidget(chart)
        self._results_layout.addWidget(chart_frame)
        self._results_layout.addStretch()
