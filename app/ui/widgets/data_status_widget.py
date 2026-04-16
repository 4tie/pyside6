from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QSizePolicy,
)
from PySide6.QtGui import QColor, QFont


class DataStatusWidget(QWidget):
    """Displays downloaded OHLCV data files grouped by exchange and pair."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user_data_path: Optional[str] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.addWidget(QLabel("Downloaded Data Files:"))
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setMaximumWidth(70)
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self._refresh_btn)
        header.addStretch()
        layout.addLayout(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Pair / Exchange", "Timeframe", "Size"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._tree)

        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet("color: #555; font-size: 9pt;")
        layout.addWidget(self._summary_label)

    def set_user_data_path(self, path: Optional[str]):
        """Set the user_data path and refresh the view.

        Args:
            path: Absolute path to the user_data directory.
        """
        self._user_data_path = path
        self.refresh()

    def refresh(self):
        """Scan user_data/data/ and repopulate the tree."""
        self._tree.clear()

        if not self._user_data_path:
            self._summary_label.setText("user_data_path not configured.")
            return

        data_dir = Path(self._user_data_path).expanduser().resolve() / "data"
        if not data_dir.exists():
            self._summary_label.setText(f"Data directory not found: {data_dir}")
            return

        total_files = 0
        total_size  = 0

        bold = QFont()
        bold.setBold(True)

        for exchange_dir in sorted(data_dir.iterdir()):
            if not exchange_dir.is_dir():
                continue
            json_files = sorted(exchange_dir.glob("*.json"))
            if not json_files:
                continue

            exchange_item = QTreeWidgetItem([exchange_dir.name, "", ""])
            exchange_item.setFont(0, bold)

            # Group by pair
            pairs_map: dict[str, list[Path]] = {}
            for f in json_files:
                parts = f.stem.rsplit("-", 1)
                pair = parts[0].replace("_", "/") if len(parts) == 2 else f.stem
                pairs_map.setdefault(pair, []).append(f)

            for pair, files in sorted(pairs_map.items()):
                pair_item = QTreeWidgetItem([pair, "", ""])
                for f in sorted(files):
                    parts = f.stem.rsplit("-", 1)
                    timeframe  = parts[1] if len(parts) == 2 else ""
                    size_bytes = f.stat().st_size
                    size_kb    = size_bytes / 1024
                    size_str   = (
                        f"{size_kb / 1024:.2f} MB" if size_kb >= 1024
                        else f"{size_kb:.1f} KB"
                    )
                    file_item = QTreeWidgetItem(["", timeframe, size_str])
                    file_item.setForeground(1, QColor("#0a7"))
                    pair_item.addChild(file_item)
                    total_files += 1
                    total_size  += size_bytes

                exchange_item.addChild(pair_item)

            self._tree.addTopLevelItem(exchange_item)
            exchange_item.setExpanded(True)
            for i in range(exchange_item.childCount()):
                exchange_item.child(i).setExpanded(True)

        size_mb = total_size / (1024 * 1024)
        self._summary_label.setText(
            f"{total_files} file(s) — {size_mb:.1f} MB total"
        )
