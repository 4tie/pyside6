import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QGroupBox,
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

_log = get_logger("ui.data_status")

_GREEN  = QColor("#4ec9a0")   # mint-green — OK / up to date
_YELLOW = QColor("#ce9178")   # VS Code orange-brown — stale
_RED    = QColor("#f44747")   # VS Code red — gaps / errors
_GRAY   = QColor("#555558")   # disabled — no data

# Candles older than this many days are considered stale
_STALE_DAYS = 3

# Timeframe → expected seconds between candles
_TF_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800,
    "12h": 43200, "1d": 86400, "3d": 259200, "1w": 604800,
}


def _tf_seconds(tf: str) -> int:
    return _TF_SECONDS.get(tf, 300)


def _fmt_ts(ts_ms: int) -> str:
    """Format a millisecond timestamp to a readable date string."""
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


def _days_ago(ts_ms: int) -> float:
    """Return how many days ago a millisecond timestamp was."""
    now_ms = datetime.now(tz=timezone.utc).timestamp() * 1000
    return (now_ms - ts_ms) / (1000 * 86400)


def _read_candle_meta(path: Path, tf: str) -> Optional[dict]:
    """
    Read a freqtrade OHLCV JSON file and return metadata:
      first_ts, last_ts, candle_count, gap_count, stale
    Returns None if file is unreadable or empty.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not raw or not isinstance(raw, list):
            return None

        # Each candle: [timestamp_ms, open, high, low, close, volume]
        timestamps = [c[0] for c in raw if isinstance(c, list) and len(c) >= 1]
        if not timestamps:
            return None

        timestamps.sort()
        first_ts = timestamps[0]
        last_ts  = timestamps[-1]
        count    = len(timestamps)

        # Detect gaps: consecutive candles more than 2× expected interval apart
        expected = _tf_seconds(tf) * 1000  # ms
        gaps = sum(
            1 for a, b in zip(timestamps, timestamps[1:])
            if (b - a) > expected * 2
        )

        stale = _days_ago(last_ts) > _STALE_DAYS

        return {
            "first_ts": first_ts,
            "last_ts":  last_ts,
            "count":    count,
            "gaps":     gaps,
            "stale":    stale,
        }
    except Exception as e:
        _log.warning("Could not read %s: %s", path.name, e)
        return None


class DataStatusWidget(QWidget):
    """Shows downloaded OHLCV data with from/to dates, candle counts, gaps and staleness."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user_data_path: Optional[str] = None
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

                pair_ok = True
                for f in sorted(files):
                    parts = f.stem.rsplit("-", 1)
                    tf = parts[1] if len(parts) == 2 else ""

                    meta = _read_candle_meta(f, tf)

                    if meta:
                        from_str   = _fmt_ts(meta["first_ts"])
                        to_str     = _fmt_ts(meta["last_ts"])
                        candles    = f"{meta['count']:,}"
                        gaps_str   = str(meta["gaps"]) if meta["gaps"] > 0 else "—"
                        stale      = meta["stale"]
                        has_gaps   = meta["gaps"] > 0

                        if has_gaps:
                            status = "⚠ Has gaps"
                            color  = _RED
                            pair_ok = False
                            gap_count += 1
                        elif stale:
                            status = f"⚠ Stale ({int(_days_ago(meta['last_ts']))}d ago)"
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
                        pair_ok = False

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
