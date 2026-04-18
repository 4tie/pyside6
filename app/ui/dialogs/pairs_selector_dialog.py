import random
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton,
    QScrollArea, QWidget
)

from app.app_state.settings_state import SettingsState

# Comprehensive Binance USDT spot pairs list
BINANCE_USDT_PAIRS: List[str] = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "SHIB/USDT", "DOT/USDT",
    "MATIC/USDT", "LTC/USDT", "TRX/USDT", "LINK/USDT", "BCH/USDT",
    "NEAR/USDT", "UNI/USDT", "ICP/USDT", "APT/USDT", "FIL/USDT",
    "ATOM/USDT", "XLM/USDT", "ETC/USDT", "HBAR/USDT", "ARB/USDT",
    "OP/USDT", "VET/USDT", "ALGO/USDT", "GRT/USDT", "SAND/USDT",
    "MANA/USDT", "AXS/USDT", "THETA/USDT", "EOS/USDT", "AAVE/USDT",
    "MKR/USDT", "SNX/USDT", "COMP/USDT", "CRV/USDT", "1INCH/USDT",
    "SUSHI/USDT", "YFI/USDT", "BAL/USDT", "ZRX/USDT", "ENJ/USDT",
    "CHZ/USDT", "HOT/USDT", "ZIL/USDT", "IOTA/USDT", "ONT/USDT",
    "QTUM/USDT", "ZEC/USDT", "DASH/USDT", "XMR/USDT", "NEO/USDT",
    "WAVES/USDT", "BAT/USDT", "ICX/USDT", "RVN/USDT", "FTM/USDT",
    "ONE/USDT", "ROSE/USDT", "DYDX/USDT", "IMX/USDT", "LRC/USDT",
    "MASK/USDT", "AUDIO/USDT", "CTSI/USDT", "OCEAN/USDT", "ALPHA/USDT",
    "PERP/USDT", "RUNE/USDT", "FLOW/USDT", "GALA/USDT", "ILV/USDT",
    "SPELL/USDT", "MAGIC/USDT", "GMX/USDT", "STG/USDT", "LQTY/USDT",
    "CVX/USDT", "FXS/USDT", "AGIX/USDT", "FET/USDT", "NMR/USDT",
    "RLC/USDT", "STORJ/USDT", "FLUX/USDT", "AR/USDT", "HNT/USDT",
    "IOTX/USDT", "JASMY/USDT", "ACH/USDT", "PEOPLE/USDT", "CAKE/USDT",
    "XVS/USDT", "TWT/USDT", "DODO/USDT", "BOND/USDT", "QUICK/USDT",
    "SUPER/USDT", "CFX/USDT", "TORN/USDT", "BADGER/USDT", "TLM/USDT",
    "ALICE/USDT", "NULS/USDT", "ORN/USDT", "BLZ/USDT", "ARPA/USDT",
    "BNT/USDT", "ENS/USDT", "APE/USDT", "GMT/USDT", "GST/USDT",
    "BICO/USDT", "VOXEL/USDT", "HIGH/USDT", "KSM/USDT", "GLMR/USDT",
    "ASTR/USDT", "SUI/USDT", "SEI/USDT", "TIA/USDT", "PYTH/USDT",
    "JTO/USDT", "MANTA/USDT", "STRK/USDT", "DYM/USDT", "METIS/USDT",
    "ZETA/USDT", "RENDER/USDT", "WIF/USDT", "BONK/USDT", "PEPE/USDT",
    "FLOKI/USDT", "TURBO/USDT", "MEW/USDT", "BOME/USDT", "POPCAT/USDT",
    "NEIRO/USDT", "HMSTR/USDT", "CATI/USDT", "DOGS/USDT", "PNUT/USDT",
    "ACT/USDT", "GOAT/USDT", "MOODENG/USDT", "NOT/USDT", "ZK/USDT",
    "ZRO/USDT", "IO/USDT", "BB/USDT", "LISTA/USDT", "REZ/USDT",
    "OMNI/USDT", "PORTAL/USDT", "PIXEL/USDT", "ALT/USDT", "MOVR/USDT",
    "ACA/USDT", "PARA/USDT", "LOKA/USDT", "VITE/USDT", "STPT/USDT",
    "WRX/USDT", "ANKR/USDT", "CELR/USDT", "BAND/USDT", "KAVA/USDT",
    "RSR/USDT", "COTI/USDT", "DENT/USDT", "WIN/USDT", "SC/USDT",
    "DGB/USDT", "SXP/USDT", "IOST/USDT", "STEEM/USDT", "NANO/USDT",
    "ZEN/USDT", "GAS/USDT", "BTS/USDT", "KNC/USDT", "MTL/USDT",
    "ELF/USDT", "SNT/USDT", "POWR/USDT", "CVC/USDT", "FUN/USDT",
    "WAN/USDT", "AION/USDT", "TOMO/USDT", "TROY/USDT", "MDT/USDT",
    "IRIS/USDT", "XVG/USDT", "UTK/USDT", "POLS/USDT", "IDEX/USDT",
    "AUCTION/USDT", "GHST/USDT", "FARM/USDT", "PUNDIX/USDT", "COCOS/USDT",
    "DEGO/USDT", "FOR/USDT", "HARD/USDT", "UNFI/USDT", "CHESS/USDT",
    "BURGER/USDT", "BAKE/USDT", "ALPACA/USDT", "AUTO/USDT", "WING/USDT",
    "SPARTA/USDT", "LINA/USDT", "OGN/USDT", "NKN/USDT", "STMX/USDT",
    "RAY/USDT", "SRM/USDT", "JOE/USDT", "STX/USDT", "MINA/USDT",
    "EGLD/USDT", "LUNA/USDT", "LUNC/USDT", "USTC/USDT", "INJ/USDT",
    "OSMO/USDT", "JUNO/USDT", "SCRT/USDT", "EVMOS/USDT", "CRO/USDT",
    "FTT/USDT", "SFP/USDT", "BIFI/USDT", "REEF/USDT", "LOOM/USDT",
    "POWR/USDT", "ADX/USDT", "AST/USDT", "OAX/USDT", "DNT/USDT",
]


class PairsSelectorDialog(QDialog):
    """Dialog for selecting multiple trading pairs with favorites support."""

    def __init__(
        self,
        favorites: List[str],
        selected: List[str],
        settings_state: SettingsState,
        max_open_trades: int = 1,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Trading Pairs")
        self.setGeometry(100, 100, 480, 560)
        self.setModal(True)

        self.settings_state = settings_state
        self.favorites: set[str] = set(favorites or [])
        self.all_pairs: List[str] = sorted(set(BINANCE_USDT_PAIRS) | set(favorites or []))
        self.selected: set[str] = set(selected) if selected else set()
        self.max_open_trades: int = max(1, max_open_trades)
        self.locked_pairs: set[str] = set()
        self.lock_buttons: dict[str, QPushButton] = {}

        self.checkboxes: dict[str, QCheckBox] = {}
        self.fav_buttons: dict[str, QPushButton] = {}
        self.row_widgets: dict[str, QWidget] = {}

        self.init_ui()

    def init_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout()

        title = QLabel("Select Trading Pairs")
        title_font = title.font()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Search filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter pairs...")
        self.search_input.textChanged.connect(self._filter_pairs)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Scrollable rows area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.checkboxes_widget = QWidget()
        self.checkboxes_layout = QVBoxLayout()
        self.checkboxes_layout.setContentsMargins(10, 0, 0, 0)
        self.checkboxes_layout.setSpacing(2)

        self._build_rows()

        self.checkboxes_widget.setLayout(self.checkboxes_layout)
        self.scroll.setWidget(self.checkboxes_widget)
        layout.addWidget(self.scroll)

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

        # Select all / Deselect all / Randomize
        action_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        action_layout.addWidget(select_all_btn)
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all)
        action_layout.addWidget(deselect_all_btn)
        self.randomize_btn = QPushButton(f"🎲 Randomize ({self.max_open_trades})")
        self.randomize_btn.clicked.connect(self._randomize_pairs)
        action_layout.addWidget(self.randomize_btn)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        self.count_label = QLabel("Selected: 0 pairs")
        self.count_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        layout.addWidget(self.count_label)

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

    def _build_rows(self):
        """Build one row widget (LockButton + FavoriteButton + QCheckBox) per pair and apply initial sort."""
        for pair in self.all_pairs:
            lock_btn = self._make_lock_button(pair)
            self.lock_buttons[pair] = lock_btn

            btn = self._make_favorite_button(pair)
            checkbox = QCheckBox(pair)
            checkbox.setChecked(pair in self.selected)
            checkbox.stateChanged.connect(self._on_checkbox_changed)

            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            row_layout.addWidget(lock_btn)
            row_layout.addWidget(btn)
            row_layout.addWidget(checkbox)

            row_widget = QWidget()
            row_widget.setLayout(row_layout)

            self.checkboxes[pair] = checkbox
            self.fav_buttons[pair] = btn
            self.row_widgets[pair] = row_widget

            self.checkboxes_layout.addWidget(row_widget)

        self.checkboxes_layout.addStretch()
        self._sort_rows()

    def _make_lock_button(self, pair: str) -> QPushButton:
        """Create and return a flat lock-toggle button for the given pair."""
        btn = QPushButton()
        btn.setFlat(True)
        btn.setFixedWidth(28)
        btn.setStyleSheet("border: none;")
        btn.setText("🔒" if pair in self.locked_pairs else "🔓")
        btn.clicked.connect(lambda checked, p=pair: self._on_lock_clicked(p))
        return btn

    def _on_lock_clicked(self, pair: str) -> None:
        """Toggle lock state for a pair, update icon, ensure pair is checked when locked."""
        if pair in self.locked_pairs:
            self.locked_pairs.discard(pair)
            self.lock_buttons[pair].setText("🔓")
        else:
            self.locked_pairs.add(pair)
            self.lock_buttons[pair].setText("🔒")
            self.checkboxes[pair].setChecked(True)
        self._update_count()

    def _make_favorite_button(self, pair: str) -> QPushButton:
        """Create and return a flat heart-toggle button for the given pair."""
        btn = QPushButton()
        btn.setFlat(True)
        btn.setFixedWidth(28)
        btn.setStyleSheet("border: none;")
        btn.setText("♥" if pair in self.favorites else "♡")
        btn.clicked.connect(lambda checked, p=pair: self._on_favorite_clicked(p))
        return btn

    def _on_favorite_clicked(self, pair: str):
        """Toggle favorite state for a pair, update UI, persist, and re-sort."""
        if pair in self.favorites:
            self.favorites.discard(pair)
        else:
            self.favorites.add(pair)
        self.fav_buttons[pair].setText("♥" if pair in self.favorites else "♡")
        self.settings_state.toggle_favorite_pair(pair)
        self._sort_rows()

    def _sort_rows(self):
        """Re-order visible rows: sorted favorites first, then sorted non-favorites."""
        visible = [p for p in self.all_pairs if p in self.row_widgets and self.row_widgets[p].isVisible()]
        ordered = sorted(p for p in visible if p in self.favorites) + \
                  sorted(p for p in visible if p not in self.favorites)

        # Remove all items from layout (widgets + stretch)
        while self.checkboxes_layout.count():
            item = self.checkboxes_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Re-insert in computed order
        for pair in ordered:
            self.checkboxes_layout.addWidget(self.row_widgets[pair])

        # Re-add hidden rows so they remain in the layout (just invisible)
        hidden = [p for p in self.all_pairs if p in self.row_widgets and not self.row_widgets[p].isVisible()]
        for pair in hidden:
            self.checkboxes_layout.addWidget(self.row_widgets[pair])

        self.checkboxes_layout.addStretch()

    def _filter_pairs(self, text: str):
        """Show/hide row widgets based on search text, then re-sort."""
        text = text.strip().upper()
        for pair, row_widget in self.row_widgets.items():
            row_widget.setVisible(not text or text in pair)
        self._sort_rows()

    def _on_checkbox_changed(self):
        self._update_selected()

    def _on_add_custom(self):
        """Add custom pairs from the text input, creating full row widgets for each."""
        text = self.custom_input.text().strip()
        if not text:
            return
        pairs = [p.strip() for p in text.split(",") if p.strip()]
        for pair in pairs:
            if pair not in self.checkboxes:
                lock_btn = self._make_lock_button(pair)
                self.lock_buttons[pair] = lock_btn

                btn = self._make_favorite_button(pair)
                checkbox = QCheckBox(pair)
                checkbox.setChecked(True)
                checkbox.stateChanged.connect(self._on_checkbox_changed)

                row_layout = QHBoxLayout()
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)
                row_layout.addWidget(lock_btn)
                row_layout.addWidget(btn)
                row_layout.addWidget(checkbox)

                row_widget = QWidget()
                row_widget.setLayout(row_layout)

                self.checkboxes[pair] = checkbox
                self.fav_buttons[pair] = btn
                self.row_widgets[pair] = row_widget
                self.all_pairs.append(pair)

                # Insert before the stretch (last item)
                self.checkboxes_layout.insertWidget(self.checkboxes_layout.count() - 1, row_widget)

        self.custom_input.clear()
        self._update_selected()

    def _randomize_pairs(self) -> None:
        """Randomly select up to max_open_trades pairs, preserving locked visible pairs."""
        effective_budget = max(1, self.max_open_trades)

        # Step 1: Determine visible pairs
        visible_pairs = [p for p in self.all_pairs if p in self.row_widgets and self.row_widgets[p].isVisible()]

        # Step 2: Partition into locked and unlocked pool
        locked_visible = [p for p in visible_pairs if p in self.locked_pairs]
        pool = [p for p in visible_pairs if p not in self.locked_pairs]

        # Step 3: Calculate remaining slots
        slots_needed = effective_budget - len(locked_visible)

        # Step 4: Sample from pool
        if slots_needed <= 0:
            sampled = []
        elif len(pool) <= slots_needed:
            sampled = pool
        else:
            sampled = random.sample(pool, slots_needed)

        # Step 5: Build new selection
        new_selection = set(locked_visible) | set(sampled)

        # Step 6: Apply to checkboxes with signal blocking
        for pair, checkbox in self.checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(pair in new_selection)
            checkbox.blockSignals(False)

        # Step 7: Sync internal state and count label
        self._update_selected()

    def _select_all(self):
        """Check all visible pair checkboxes."""
        for pair, checkbox in self.checkboxes.items():
            if pair in self.row_widgets and self.row_widgets[pair].isVisible():
                checkbox.setChecked(True)

    def _deselect_all(self):
        """Uncheck all visible pair checkboxes."""
        for pair, checkbox in self.checkboxes.items():
            if pair in self.row_widgets and self.row_widgets[pair].isVisible():
                checkbox.setChecked(False)

    def _update_selected(self):
        self.selected = {pair for pair, cb in self.checkboxes.items() if cb.isChecked()}
        self._update_count()

    def _update_count(self):
        count = len(self.selected)
        self.count_label.setText(f"Selected: {count} pair{'s' if count != 1 else ''}")

    def get_selected_pairs(self) -> List[str]:
        """Return sorted list of selected pair strings."""
        return sorted(list(self.selected))
