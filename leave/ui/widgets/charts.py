"""Chart widgets using pyqtgraph for fast, interactive plots."""
from __future__ import annotations
from typing import List, Optional
import numpy as np

import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QBrush, QPen

from app.ui import theme

# Configure pyqtgraph defaults
pg.setConfigOptions(antialias=True, background=theme.CHART_BG, foreground=theme.TEXT_SECONDARY)


def _make_plot_widget(title: str = "") -> pg.PlotWidget:
    pw = pg.PlotWidget()
    pw.setBackground(theme.CHART_BG)
    pw.showGrid(x=True, y=True, alpha=0.15)
    pw.getAxis('left').setPen(pg.mkPen(color=theme.TEXT_MUTED, width=1))
    pw.getAxis('bottom').setPen(pg.mkPen(color=theme.TEXT_MUTED, width=1))
    pw.getAxis('left').setTextPen(pg.mkPen(color=theme.TEXT_SECONDARY))
    pw.getAxis('bottom').setTextPen(pg.mkPen(color=theme.TEXT_SECONDARY))
    pw.getAxis('left').setStyle(tickFont=pg.QtGui.QFont("monospace", 9))
    pw.getAxis('bottom').setStyle(tickFont=pg.QtGui.QFont("monospace", 9))
    if title:
        pw.setTitle(title, color=theme.TEXT_SECONDARY, size="11pt")
    pw.setMenuEnabled(False)
    return pw


class EquityCurveChart(QWidget):
    """Equity curve with gradient fill."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = _make_plot_widget()
        layout.addWidget(self._pw)
        self._curve = None
        self._fill = None

    def set_data(self, values: List[float], label: str = "Equity"):
        self._pw.clear()
        if not values:
            return
        x = np.arange(len(values))
        y = np.array(values, dtype=float)

        color = theme.GREEN if y[-1] >= y[0] else theme.RED
        pen = pg.mkPen(color=color, width=2)
        self._curve = self._pw.plot(x, y, pen=pen, name=label)

        # Gradient fill under curve
        fill_color = QColor(color)
        fill_color.setAlpha(40)
        fill = pg.FillBetweenItem(
            self._curve,
            pg.PlotDataItem(x, np.full_like(y, y.min())),
            brush=pg.mkBrush(fill_color),
        )
        self._pw.addItem(fill)

        # Zero line
        self._pw.addLine(y=y[0], pen=pg.mkPen(color=theme.TEXT_MUTED, style=Qt.DashLine, width=1))


class DrawdownChart(QWidget):
    """Drawdown chart (negative area filled red)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = _make_plot_widget()
        layout.addWidget(self._pw)

    def set_data(self, drawdowns: List[float]):
        self._pw.clear()
        if not drawdowns:
            return
        x = np.arange(len(drawdowns))
        y = np.array(drawdowns, dtype=float)

        pen = pg.mkPen(color=theme.RED, width=1.5)
        curve = self._pw.plot(x, y, pen=pen)

        fill_color = QColor(theme.RED)
        fill_color.setAlpha(50)
        zero_line = pg.PlotDataItem(x, np.zeros_like(y))
        fill = pg.FillBetweenItem(curve, zero_line, brush=pg.mkBrush(fill_color))
        self._pw.addItem(fill)
        self._pw.addLine(y=0, pen=pg.mkPen(color=theme.TEXT_MUTED, width=1))


class ProfitBarChart(QWidget):
    """Per-trade profit bar chart (green/red bars)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = _make_plot_widget()
        layout.addWidget(self._pw)

    def set_data(self, profits: List[float]):
        self._pw.clear()
        if not profits:
            return
        x = np.arange(len(profits))
        y = np.array(profits, dtype=float)

        brushes = [pg.mkBrush(theme.GREEN if v >= 0 else theme.RED) for v in y]
        bars = pg.BarGraphItem(x=x, height=y, width=0.7, brushes=brushes, pen=pg.mkPen(None))
        self._pw.addItem(bars)
        self._pw.addLine(y=0, pen=pg.mkPen(color=theme.TEXT_MUTED, width=1))


class PairProfitChart(QWidget):
    """Horizontal bar chart for per-pair profit."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = _make_plot_widget()
        layout.addWidget(self._pw)

    def set_data(self, pairs: List[str], profits: List[float]):
        self._pw.clear()
        if not pairs:
            return
        y = np.arange(len(pairs))
        x = np.array(profits, dtype=float)

        brushes = [pg.mkBrush(theme.GREEN if v >= 0 else theme.RED) for v in x]
        bars = pg.BarGraphItem(x0=0, y=y, height=0.6, width=x, brushes=brushes, pen=pg.mkPen(None))
        self._pw.addItem(bars)

        ax = self._pw.getAxis('left')
        ax.setTicks([list(enumerate(pairs))])
        self._pw.addLine(x=0, pen=pg.mkPen(color=theme.TEXT_MUTED, width=1))


class WinRateDonut(QWidget):
    """Simple win/loss/draw donut using pyqtgraph."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = pg.PlotWidget()
        self._pw.setBackground(theme.CHART_BG)
        self._pw.setAspectLocked(True)
        self._pw.hideAxis('left')
        self._pw.hideAxis('bottom')
        self._pw.setMenuEnabled(False)
        layout.addWidget(self._pw)

    def set_data(self, wins: int, losses: int, draws: int = 0):
        self._pw.clear()
        total = wins + losses + draws
        if total == 0:
            return

        import math
        from PySide6.QtGui import QPolygonF, QPainterPath, QColor as QC
        from PySide6.QtCore import QPointF
        from PySide6.QtWidgets import QGraphicsPathItem

        data = [
            (wins / total, theme.GREEN),
            (losses / total, theme.RED),
            (draws / total, theme.YELLOW),
        ]

        start = -math.pi / 2
        for frac, color in data:
            if frac <= 0:
                continue
            end = start + 2 * math.pi * frac
            n = max(3, int(frac * 120))
            angles = np.linspace(start, end, n)
            outer = 1.0
            inner = 0.55

            path = QPainterPath()
            # Start at outer arc beginning
            path.moveTo(outer * math.cos(angles[0]), outer * math.sin(angles[0]))
            # Outer arc
            for a in angles[1:]:
                path.lineTo(outer * math.cos(a), outer * math.sin(a))
            # Inner arc (reversed)
            for a in angles[::-1]:
                path.lineTo(inner * math.cos(a), inner * math.sin(a))
            path.closeSubpath()

            item = QGraphicsPathItem(path)
            c = QC(color)
            item.setBrush(QBrush(c))
            item.setPen(QPen(Qt.NoPen))
            self._pw.addItem(item)
            start = end

        # Center text
        pct = round(wins / total * 100) if total else 0
        text = pg.TextItem(f"{pct}%\nWin", anchor=(0.5, 0.5), color=theme.TEXT_PRIMARY)
        text.setFont(pg.QtGui.QFont("sans-serif", 10, pg.QtGui.QFont.Bold))
        text.setPos(0, 0)
        self._pw.addItem(text)


class ComparisonBarChart(QWidget):
    """Side-by-side bar chart for comparing two runs."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = _make_plot_widget()
        layout.addWidget(self._pw)

    def set_data(self, labels: List[str], values_a: List[float], values_b: List[float],
                 name_a: str = "Run A", name_b: str = "Run B"):
        self._pw.clear()
        if not labels:
            return
        x = np.arange(len(labels))
        w = 0.35

        bars_a = pg.BarGraphItem(x=x - w/2, height=values_a, width=w,
                                  brush=pg.mkBrush(theme.ACCENT + "cc"), pen=pg.mkPen(None))
        bars_b = pg.BarGraphItem(x=x + w/2, height=values_b, width=w,
                                  brush=pg.mkBrush(theme.GREEN + "cc"), pen=pg.mkPen(None))
        self._pw.addItem(bars_a)
        self._pw.addItem(bars_b)

        ax = self._pw.getAxis('bottom')
        ax.setTicks([list(enumerate(labels))])
        self._pw.addLine(y=0, pen=pg.mkPen(color=theme.TEXT_MUTED, width=1))

        legend = self._pw.addLegend(offset=(10, 10))
        legend.addItem(bars_a, name_a)
        legend.addItem(bars_b, name_b)
