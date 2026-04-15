from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton,
    QScrollArea, QWidget
)


class PairsSelectorDialog(QDialog):
    """Dialog for selecting multiple trading pairs."""

    def __init__(self, favorites: List[str], selected: List[str], parent=None):
        """Initialize pairs selector dialog.

        Args:
            favorites: List of favorite pairs to show as checkboxes
            selected: List of currently selected pairs
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Select Trading Pairs")
        self.setGeometry(100, 100, 400, 400)
        self.setModal(True)

        self.favorites = favorites or ["BTC/USDT", "ETH/USDT", "ADA/USDT"]
        self.selected = set(selected) if selected else set()
        self.custom_pairs: set[str] = set()

        # Store checkboxes for easy access
        self.checkboxes: dict[str, QCheckBox] = {}

        self.init_ui()

    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Select Trading Pairs")
        title_font = title.font()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Favorites section
        layout.addWidget(QLabel("Favorites:"))

        # Scrollable checkboxes area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        checkboxes_widget = QWidget()
        checkboxes_layout = QVBoxLayout()
        checkboxes_layout.setContentsMargins(10, 0, 0, 0)

        # Add checkboxes for each favorite
        for pair in self.favorites:
            checkbox = QCheckBox(pair)
            checkbox.setChecked(pair in self.selected)
            checkbox.stateChanged.connect(self._on_checkbox_changed)
            checkboxes_layout.addWidget(checkbox)
            self.checkboxes[pair] = checkbox

        checkboxes_layout.addStretch()
        checkboxes_widget.setLayout(checkboxes_layout)
        scroll.setWidget(checkboxes_widget)
        layout.addWidget(scroll)

        # Custom pairs section
        layout.addWidget(QLabel("Add Custom Pairs:"))

        custom_layout = QHBoxLayout()
        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("e.g., SOL/USDT, XRP/USDT")
        self.custom_input.setToolTip("Comma-separated pairs")
        custom_layout.addWidget(self.custom_input)

        add_btn = QPushButton("Add")
        add_btn.setMaximumWidth(60)
        add_btn.clicked.connect(self._on_add_custom)
        custom_layout.addWidget(add_btn)
        layout.addLayout(custom_layout)

        # Select all / Deselect all buttons
        action_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        action_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all)
        action_layout.addWidget(deselect_all_btn)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        # Selected count
        self.count_label = QLabel("Selected: 0 pairs")
        self.count_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        layout.addWidget(self.count_label)

        # OK / Cancel buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.setMinimumWidth(80)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self._update_count()

    def _on_checkbox_changed(self):
        """Handle checkbox state changes."""
        self._update_selected()

    def _on_add_custom(self):
        """Handle adding custom pairs."""
        text = self.custom_input.text().strip()
        if not text:
            return

        # Parse comma-separated pairs
        pairs = [p.strip() for p in text.split(",") if p.strip()]

        for pair in pairs:
            if pair not in self.checkboxes and pair not in self.custom_pairs:
                # Create checkbox for custom pair
                checkbox = QCheckBox(pair)
                checkbox.setChecked(True)
                checkbox.stateChanged.connect(self._on_checkbox_changed)
                self.checkboxes[pair] = checkbox
                self.custom_pairs.add(pair)

                # Insert before the stretch item (find parent layout)
                parent = checkbox.parent()
                if parent:
                    layout = parent.layout()
                    if layout:
                        layout.insertWidget(layout.count() - 1, checkbox)

        self.custom_input.clear()
        self._update_selected()

    def _select_all(self):
        """Select all pairs."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all(self):
        """Deselect all pairs."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)

    def _update_selected(self):
        """Update selected pairs from checkboxes."""
        self.selected = set()
        for pair, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                self.selected.add(pair)
        self._update_count()

    def _update_count(self):
        """Update the count label."""
        count = len(self.selected)
        self.count_label.setText(f"Selected: {count} pair{'s' if count != 1 else ''}")

    def get_selected_pairs(self) -> List[str]:
        """Get list of selected pairs.

        Returns:
            List of selected pair strings
        """
        return sorted(list(self.selected))
