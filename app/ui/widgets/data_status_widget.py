from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app.core.services.data_status_service import DataStatusService
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.utils.app_logger import get_logger

_LOG = get_logger("ui.data_status")

_GREEN  = QColor("#4ec9a0")   # mint-green — OK / up to date
_YELLOW = QColor("#ce9178")   # VS Code orange-brown — stale
_RED    = QColor("#f44747")   # VS Code red — gaps / errors
_GRAY   = QColor("#555558")   # disabled — no data


class DataStatusWidget(QWidget):
    """Shows downloaded OHLCV data with from/to dates, candle counts, gaps and staleness."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user_data_path: Optional[str] = None
        self._data_status_service = DataStatusService()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Data Coverage")
        bold = QFont()
        bold.setBold(True)
        title.setFont(bold)
        header.addWidget(title)
        header.addStretch()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setMaximumWidth(70)
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self._refresh_btn)
        layout.addLayout(header)

        # Legend
        legend = QHBoxLayout()
        for _, label in [
            (_GREEN,  "● Up to date"),
            (_YELLOW, "● Stale (>3d old)"),
            (_RED,    "● Has gaps"),
            (_GRAY,   "● No data"),
        ]:
            lbl = QLabel(label)
            lbl.setObjectName("hint_label")
            legend.addWidget(lbl)
        legend.addStretch()
        layout.addLayout(legend)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([
            "Pair", "Timeframe", "From", "To", "Candles", "Gaps", "Status"
        ])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(6, QHeaderView.Stretch)
        self._tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree)

        # Summary bar
        self._summary_label = QLabel("")
        self._summary_label.setObjectName("hint_label")
        layout.addWidget(self._summary_label)

    def set_user_data_path(self, path: Optional[str]):
        self._user_data_path = path
        self.refresh()

    def refresh(self):
        """Scan data directory and rebuild the tree with real candle metadata."""
        self._tree.clear()

        if not self._user_data_path:
            self._summary_label.setText("user_data path not configured.")
            return

        data_dir = Path(self._user_data_path).expanduser().resolve() / "data"
        if not data_dir.exists():
            self._summary_label.setText(f"Data directory not found: {data_dir}")
            return

        bold = QFont()
        bold.setBold(True)

        total_files = 0
        total_candles = 0
        stale_count = 0
        gap_count = 0

        for exchange_dir in sorted(data_dir.iterdir()):
            if not exchange_dir.is_dir():
                continue
            json_files = sorted(exchange_dir.glob("*.json"))
            if not json_files:
                continue

            exchange_item = QTreeWidgetItem([exchange_dir.name, "", "", "", "", "", ""])
            exchange_item.setFont(0, bold)

            # Group files by pair
            pairs_map: dict[str, list[Path]] = {}
            for f in json_files:
                parts = f.stem.rsplit("-", 1)
                pair = parts[0].replace("_", "/") if len(parts) == 2 else f.stem
                pairs_map.setdefault(pair, []).append(f)

            for pair, files in sorted(pairs_map.items()):
                pair_item = QTreeWidgetItem([pair, "", "", "", "", "", ""])
                pair_item.setFont(0, bold)

                for f in sorted(files):
                    parts = f.stem.rsplit("-", 1)
                    tf = parts[1] if len(parts) == 2 else ""

                    meta = self._data_status_service.read_candle_meta(f, tf)

                    if meta:
                        from_str   = self._data_status_service.format_timestamp(meta["first_ts"])
                        to_str     = self._data_status_service.format_timestamp(meta["last_ts"])
                        candles    = f"{meta['count']:,}"
                        gaps_str   = str(meta["gaps"]) if meta["gaps"] > 0 else "—"
                        stale      = meta["stale"]
                        has_gaps   = meta["gaps"] > 0

                        if has_gaps:
                            status = "⚠ Has gaps"
                            color  = _RED
                            gap_count += 1
                        elif stale:
                            status = f"⚠ Stale ({int(meta['days_ago'])}d ago)"
                            color  = _YELLOW
                            stale_count += 1
                        else:
                            status = "✓ OK"
                            color  = _GREEN

                        total_candles += meta["count"]
                    else:
                        from_str = to_str = candles = gaps_str = "—"
                        status = "No data"
                        color  = _GRAY

                    row = QTreeWidgetItem(["", tf, from_str, to_str, candles, gaps_str, status])
                    row.setForeground(6, color)
                    row.setForeground(1, QColor("#4ec9a0"))
                    pair_item.addChild(row)
                    total_files += 1

                exchange_item.addChild(pair_item)

            self._tree.addTopLevelItem(exchange_item)
            exchange_item.setExpanded(True)
            for i in range(exchange_item.childCount()):
                exchange_item.child(i).setExpanded(True)

        # Summary
        parts = [f"{total_files} file(s)", f"{total_candles:,} candles"]
        if stale_count:
            parts.append(f"{stale_count} stale")
        if gap_count:
            parts.append(f"{gap_count} with gaps")
        self._summary_label.setText("  |  ".join(parts))
